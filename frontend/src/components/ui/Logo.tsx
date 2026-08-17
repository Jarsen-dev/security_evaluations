import { cn } from '@/lib/utils';

interface LogoProps {
  /** Alto en píxeles. El ancho se calcula solo para no deformarlo. */
  alto?: number;
  /**
   * Coloca el logo sobre una base clara.
   *
   * El logo institucional es azul marino: sobre el fondo oscuro del panel
   * casi desaparece. En esos casos se apoya en una base blanca para que
   * conserve contraste.
   */
  sobreFondoOscuro?: boolean;
  className?: string;
}

// Proporción del archivo original (668 × 424).
const PROPORCION = 668 / 424;

/**
 * Logo de la empresa.
 *
 * La imagen la sirve el backend desde `backend/static`, así que existe una
 * sola copia: cambiar ese archivo actualiza el panel, el formulario público,
 * el PDF y el PowerPoint a la vez.
 */
export function Logo({ alto = 32, sobreFondoOscuro = false, className }: LogoProps) {
  const imagen = (
    // Se usa <img> y no next/image porque el archivo lo sirve el backend en
    // tiempo de ejecución, no forma parte del build del frontend.
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src="/api/static/Logo.png"
      alt="Logo de la empresa"
      height={alto}
      width={Math.round(alto * PROPORCION)}
      style={{ height: alto, width: 'auto' }}
      className="block"
    />
  );

  if (!sobreFondoOscuro) {
    return <span className={cn('inline-flex items-center', className)}>{imagen}</span>;
  }

  return (
    <span
      className={cn(
        'inline-flex items-center rounded-md bg-white px-2 py-1.5',
        className,
      )}
    >
      {imagen}
    </span>
  );
}
