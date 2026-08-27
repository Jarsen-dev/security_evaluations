/**
 * Reducción de imágenes antes de subirlas.
 *
 * Se hace con `<canvas>`, que **sí** existe fuera de un contexto seguro: por
 * la IP de la LAN el navegador no considera segura la página y varias APIs
 * modernas ni siquiera están definidas (regla 5 del CLAUDE.md). Por lo mismo
 * la captura se hace con `<input type="file" capture>` y nunca con
 * `getUserMedia`, que además Nginx bloquea con `Permissions-Policy: camera=()`.
 *
 * Una foto de celular pesa varios MB; reducirla en el navegador baja la
 * subida a unos cientos de KB y evita que el servidor la rechace por tamaño.
 */

export interface OpcionesReduccion {
  /** Lado mayor al que se reduce la imagen. */
  ladoMaximo: number;
  /** Calidad del JPEG resultante, de 0 a 1. */
  calidad: number;
  /** Si la imagen ya es JPEG y no pasa de esto, se deja tal cual. */
  maxBytes: number;
  /** Nombre del archivo resultante. */
  nombre: string;
}

/** Evidencia de los controles ESH: basta con que se vea qué pasó. */
export const REDUCCION_EVIDENCIA: OpcionesReduccion = {
  ladoMaximo: 1600,
  calidad: 0.8,
  maxBytes: 2 * 1024 * 1024,
  nombre: 'evidencia.jpg',
};

/**
 * Foto de una remisión: la lee un OCR, no una persona.
 *
 * Va a más resolución que la evidencia porque de esos píxeles salen los
 * códigos y las cantidades: recortar de más se paga en campos que la IA no
 * puede leer y que alguien tiene que teclear.
 */
export const REDUCCION_DOCUMENTO: OpcionesReduccion = {
  ladoMaximo: 2000,
  calidad: 0.85,
  maxBytes: 2 * 1024 * 1024,
  nombre: 'remision.jpg',
};

/**
 * Carga la imagen conservando la orientación del EXIF.
 *
 * `createImageBitmap` con `imageOrientation: 'from-image'` es lo que respeta
 * la rotación que graba la cámara del celular. Sin eso el canvas la descarta y
 * la foto llega acostada al servidor — justo lo que el detector de
 * orientación de Tesseract tendría que adivinar después.
 *
 * No todos los navegadores admiten esa opción, así que hay un camino de
 * respaldo con `<img>`.
 */
async function cargar(
  archivo: File,
): Promise<{ fuente: CanvasImageSource; ancho: number; alto: number; liberar: () => void }> {
  if (typeof createImageBitmap === 'function') {
    try {
      const mapa = await createImageBitmap(archivo, {
        imageOrientation: 'from-image',
      });
      return {
        fuente: mapa,
        ancho: mapa.width,
        alto: mapa.height,
        liberar: () => mapa.close(),
      };
    } catch {
      // Navegador sin soporte para la opción: se sigue por el camino de abajo.
    }
  }

  const url = URL.createObjectURL(archivo);
  const elemento = await new Promise<HTMLImageElement>((resolver, rechazar) => {
    const imagen = new Image();
    imagen.onload = () => resolver(imagen);
    imagen.onerror = () => rechazar(new Error('imagen ilegible'));
    imagen.src = url;
  });

  return {
    fuente: elemento,
    ancho: elemento.width,
    alto: elemento.height,
    liberar: () => URL.revokeObjectURL(url),
  };
}

/**
 * Reduce una imagen. **Nunca lanza**: si algo falla devuelve el archivo tal
 * como llegó.
 *
 * Subir de más es molesto; no poder subir la evidencia es perder el viaje al
 * almacén, así que ante la duda se manda el original.
 */
export async function reducirImagen(
  archivo: File,
  opciones: OpcionesReduccion,
): Promise<File> {
  let liberar = () => {};

  try {
    const imagen = await cargar(archivo);
    liberar = imagen.liberar;

    const escala = Math.min(
      1,
      opciones.ladoMaximo / Math.max(imagen.ancho, imagen.alto),
    );

    // Ya es lo bastante chica: recomprimirla solo perdería calidad.
    if (
      escala === 1 &&
      archivo.type === 'image/jpeg' &&
      archivo.size <= opciones.maxBytes
    ) {
      return archivo;
    }

    const lienzo = document.createElement('canvas');
    lienzo.width = Math.round(imagen.ancho * escala);
    lienzo.height = Math.round(imagen.alto * escala);

    const contexto = lienzo.getContext('2d');
    if (contexto === null) {
      return archivo;
    }

    contexto.drawImage(imagen.fuente, 0, 0, lienzo.width, lienzo.height);

    const blob = await new Promise<Blob | null>((resolver) => {
      lienzo.toBlob(resolver, 'image/jpeg', opciones.calidad);
    });

    if (blob === null) {
      return archivo;
    }

    return new File([blob], opciones.nombre, { type: 'image/jpeg' });
  } catch {
    return archivo;
  } finally {
    liberar();
  }
}
