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
