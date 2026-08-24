'use client';

import { useEffect, useRef, useState } from 'react';

import { Button } from '@/components/ui/Button';
import { useTraduccion } from '@/lib/i18n';

/**
 * Captura de la foto de evidencia.
 *
 * Se usa un `<input type="file" capture>`, **no** `getUserMedia`: por la IP de
 * la LAN el navegador no está en contexto seguro y esa API sencillamente no
 * existe (ver la regla 5 del CLAUDE.md). Además, Nginx manda
 * `Permissions-Policy: camera=()`, así que tampoco funcionaría por HTTPS.
 * El input abre la cámara del celular igual, y en la laptop abre el
 * explorador de archivos.
 */

/** Lado mayor al que se reduce la foto antes de subirla. */
const LADO_MAXIMO = 1600;
const CALIDAD_JPEG = 0.8;

interface CampoFotoProps {
  foto: File | null;
  onCambiar: (foto: File | null) => void;
  onError: (mensaje: string) => void;
  deshabilitado?: boolean;
}

/**
 * Reduce la imagen con `<canvas>`, que sí está disponible fuera de un contexto
 * seguro. Una foto de celular pesa varios MB y el servidor rechaza todo lo que
 * pase de 2 MB.
 */
async function reducir(archivo: File): Promise<File> {
  const url = URL.createObjectURL(archivo);

  try {
    const imagen = await new Promise<HTMLImageElement>((resolver, rechazar) => {
      const elemento = new Image();
      elemento.onload = () => resolver(elemento);
      elemento.onerror = () => rechazar(new Error('imagen ilegible'));
      elemento.src = url;
    });

    const escala = Math.min(1, LADO_MAXIMO / Math.max(imagen.width, imagen.height));

    // Ya es lo bastante chica: no tiene caso recomprimirla y perder calidad.
    if (escala === 1 && archivo.type === 'image/jpeg') {
      return archivo;
    }

    const lienzo = document.createElement('canvas');
    lienzo.width = Math.round(imagen.width * escala);
    lienzo.height = Math.round(imagen.height * escala);

    const contexto = lienzo.getContext('2d');
    if (contexto === null) {
      return archivo;
    }

    contexto.drawImage(imagen, 0, 0, lienzo.width, lienzo.height);

    const blob = await new Promise<Blob | null>((resolver) => {
      lienzo.toBlob(resolver, 'image/jpeg', CALIDAD_JPEG);
    });

    if (blob === null) {
      return archivo;
    }

    return new File([blob], 'evidencia.jpg', { type: 'image/jpeg' });
  } finally {
    URL.revokeObjectURL(url);
  }
}

export function CampoFoto({ foto, onCambiar, onError, deshabilitado }: CampoFotoProps) {
  const t = useTraduccion();
  const entrada = useRef<HTMLInputElement>(null);
  const [vistaPrevia, setVistaPrevia] = useState<string | null>(null);
  const [procesando, setProcesando] = useState(false);

  useEffect(() => {
    if (foto === null) {
      setVistaPrevia(null);
      return;
    }

    const url = URL.createObjectURL(foto);
    setVistaPrevia(url);

    // Sin esto, cada foto elegida deja su blob en memoria hasta recargar.
    return () => URL.revokeObjectURL(url);
  }, [foto]);

  async function alElegir(archivo: File | undefined) {
    if (archivo === undefined) {
      return;
    }

    if (!archivo.type.startsWith('image/')) {
      onError(t('rayser.fotoInvalida'));
      return;
    }

    setProcesando(true);
    try {
      const reducida = await reducir(archivo);

      if (reducida.size > 2 * 1024 * 1024) {
        onError(t('rayser.fotoPesada'));
        return;
      }

      onCambiar(reducida);
    } catch {
      onError(t('rayser.fotoInvalida'));
    } finally {
      setProcesando(false);
      // Permite volver a elegir el mismo archivo después de quitarlo.
      if (entrada.current) {
        entrada.current.value = '';
      }
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <span className="text-sm font-medium text-texto">{t('rayser.foto')}</span>

      <input
        ref={entrada}
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        onChange={(evento) => void alElegir(evento.target.files?.[0])}
        disabled={deshabilitado}
      />

      <div className="flex flex-wrap items-center gap-3">
        <Button
          variante="secundario"
          onClick={() => entrada.current?.click()}
          cargando={procesando}
          disabled={deshabilitado}
        >
          {foto ? t('rayser.cambiarFoto') : t('rayser.tomarFoto')}
        </Button>

        {foto && (
          <Button
            variante="fantasma"
            onClick={() => onCambiar(null)}
            disabled={deshabilitado}
          >
            {t('rayser.quitarFoto')}
          </Button>
        )}
      </div>

      {vistaPrevia && (
        // eslint-disable-next-line @next/next/no-img-element -- es un blob local,
        // next/image no puede optimizar una URL de objeto.
        <img
          src={vistaPrevia}
          alt={t('rayser.foto')}
          className="max-h-48 w-auto rounded-md border border-borde object-contain"
        />
      )}
    </div>
  );
}
