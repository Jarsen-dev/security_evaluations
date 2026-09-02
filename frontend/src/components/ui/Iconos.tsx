/**
 * Iconos de la interfaz, como SVG en línea.
 *
 * Sin librería: son media docena de trazos y una dependencia de iconos pesa
 * más que esto. Van con `stroke="currentColor"`, así que heredan el color del
 * botón que los contiene y funcionan igual en cualquier variante.
 *
 * `aria-hidden` en todos a propósito: el botón que los envuelve lleva el
 * `aria-label` con el texto traducido, y anunciar el icono además sería
 * repetir la misma acción dos veces al lector de pantalla.
 */

interface IconoProps {
  /** Lado del cuadro, en píxeles. Por omisión el de un botón `sm`. */
  tamano?: number;
  className?: string;
}

function Svg({
  tamano = 16,
  className,
  children,
}: IconoProps & { children: React.ReactNode }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={tamano}
      height={tamano}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      className={className}
    >
      {children}
    </svg>
  );
}

/** Ver el detalle de un registro. */
export function IconoOjo(props: IconoProps) {
  return (
    <Svg {...props}>
      <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z" />
      <circle cx="12" cy="12" r="3" />
    </Svg>
  );
}

/** Corregir un registro ya guardado. */
export function IconoLapiz(props: IconoProps) {
  return (
    <Svg {...props}>
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" />
    </Svg>
  );
}

/** Capturar el cierre de un hallazgo: portapapeles con una nota. */
export function IconoPortapapeles(props: IconoProps) {
  return (
    <Svg {...props}>
      <path d="M9 3h6a1 1 0 0 1 1 1v1H8V4a1 1 0 0 1 1-1Z" />
      <path d="M8 5H6a1 1 0 0 0-1 1v14a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V6a1 1 0 0 0-1-1h-2" />
      <path d="M9 12h6M9 16h4" />
    </Svg>
  );
}

/** El hallazgo ya está cerrado. */
export function IconoPalomita(props: IconoProps) {
  return (
    <Svg {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="m8.5 12.5 2.5 2.5 4.5-5" />
    </Svg>
  );
}

/** Eliminar un registro. */
export function IconoBote(props: IconoProps) {
  return (
    <Svg {...props}>
      <path d="M4 7h16" />
      <path d="M10 4h4a1 1 0 0 1 1 1v2H9V5a1 1 0 0 1 1-1Z" />
      <path d="M6 7v13a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1V7" />
      <path d="M10 11v6M14 11v6" />
    </Svg>
  );
}

/** Descargar un archivo. */
export function IconoDescargar(props: IconoProps) {
  return (
    <Svg {...props}>
      <path d="M12 3v12" />
      <path d="m7 11 5 5 5-5" />
      <path d="M4 20h16" />
    </Svg>
  );
}

/** Activar o desactivar algo que sigue existiendo: una cuenta, un punto. */
export function IconoEncender(props: IconoProps) {
  return (
    <Svg {...props}>
      <path d="M12 3v9" />
      <path d="M18.4 6.6a9 9 0 1 1-12.8 0" />
    </Svg>
  );
}

/** Ver el código QR de un punto de rondín. */
export function IconoQr(props: IconoProps) {
  return (
    <Svg {...props}>
      <rect x="3" y="3" width="7" height="7" rx="1" />
      <rect x="14" y="3" width="7" height="7" rx="1" />
      <rect x="3" y="14" width="7" height="7" rx="1" />
      <path d="M14 14h3v3h-3z" />
      <path d="M21 14v3" />
      <path d="M14 21h7" />
    </Svg>
  );
}

/** Girar 90° en contra de las manecillas. */
export function IconoGirarIzquierda(props: IconoProps) {
  return (
    <Svg {...props}>
      <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
      <path d="M3 3v5h5" />
    </Svg>
  );
}

/** Girar 90° a favor de las manecillas. */
export function IconoGirarDerecha(props: IconoProps) {
  return (
    <Svg {...props}>
      <path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8" />
      <path d="M21 3v5h-5" />
    </Svg>
  );
}

/** Acercar la imagen. */
export function IconoZoomMas(props: IconoProps) {
  return (
    <Svg {...props}>
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.6-3.6" />
      <path d="M11 8v6M8 11h6" />
    </Svg>
  );
}

/** Alejar la imagen. */
export function IconoZoomMenos(props: IconoProps) {
  return (
    <Svg {...props}>
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.6-3.6" />
      <path d="M8 11h6" />
    </Svg>
  );
}

/** Ver a pantalla completa. */
export function IconoPantallaCompleta(props: IconoProps) {
  return (
    <Svg {...props}>
      <path d="M8 3H5a2 2 0 0 0-2 2v3" />
      <path d="M21 8V5a2 2 0 0 0-2-2h-3" />
      <path d="M3 16v3a2 2 0 0 0 2 2h3" />
      <path d="M16 21h3a2 2 0 0 0 2-2v-3" />
    </Svg>
  );
}

/** Salir de pantalla completa. */
export function IconoSalirPantallaCompleta(props: IconoProps) {
  return (
    <Svg {...props}>
      <path d="M8 3v3a2 2 0 0 1-2 2H3" />
      <path d="M21 8h-3a2 2 0 0 1-2-2V3" />
      <path d="M3 16h3a2 2 0 0 1 2 2v3" />
      <path d="M16 21v-3a2 2 0 0 1 2-2h3" />
    </Svg>
  );
}
