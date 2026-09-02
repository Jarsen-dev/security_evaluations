'use client';

import type { ReactNode } from 'react';

import { cn } from '@/lib/utils';

interface BotonIconoProps {
  /** Va como `aria-label` y como `title`: el icono solo no dice nada. */
  etiqueta: string;
  icono: ReactNode;
  onClick: () => void;
  deshabilitado?: boolean;
  /** Color del icono; por omisión el gris de la tabla. */
  tono?: 'neutro' | 'exito' | 'error';
  cargando?: boolean;
}

const TONOS = {
  neutro: 'text-texto-suave hover:text-texto',
  exito: 'text-exito hover:text-exito',
  error: 'text-texto-suave hover:text-error',
} as const;

/**
 * Botón de solo icono para la columna de Acciones.
 *
 * **Es el único diseño de acción de tabla del panel.** Nació en los
 * historiales de Controles y vive aquí desde que lo usan todas las tablas
 * —usuarios, catálogo, estudios, puntos de rondín, intentos y recepciones—:
 * con botones de texto en unas y de icono en otras, la misma acción cambiaba
 * de forma y de ancho según la pestaña, y la columna de Acciones se comía el
 * espacio de los datos.
 *
 * No usa `ui/Button` porque ese componente reserva espacio horizontal para
 * texto y aquí caben cuatro acciones en una celda. Lo que sí conserva es el
 * objetivo táctil: 32 px de lado, que es lo mínimo cómodo con guantes.
 *
 * **Siempre lleva `aria-label` y `title`.** Sin texto visible, esa es la única
 * forma de saber qué hace el botón: el `title` para quien lo ve y duda, el
 * `aria-label` para quien no lo ve. Por eso `etiqueta` es obligatoria y recibe
 * el texto ya traducido, no un icono suelto.
 */
export function BotonIcono({
  etiqueta,
  icono,
  onClick,
  deshabilitado,
  tono = 'neutro',
  cargando,
}: BotonIconoProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={deshabilitado || cargando}
      aria-label={etiqueta}
      title={etiqueta}
      className={cn(
        'inline-flex h-8 w-8 items-center justify-center rounded-md',
        'border border-transparent transition-colors',
        'hover:border-borde hover:bg-fondo-sutil',
        'disabled:cursor-not-allowed disabled:opacity-50',
        TONOS[tono],
      )}
    >
      {cargando ? (
        <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
      ) : (
        icono
      )}
    </button>
  );
}

/**
 * La fila de acciones de una celda: los iconos juntos y pegados a la derecha.
 *
 * Existe para que la separación entre iconos sea la misma en todas las tablas
 * sin que cada una repita las clases.
 */
export function FilaAcciones({
  children,
  alineacion = 'derecha',
}: {
  children: ReactNode;
  /** Estudios centra toda su tabla; el resto alinea a la derecha. */
  alineacion?: 'derecha' | 'centro';
}) {
  return (
    <div
      className={cn(
        'flex items-center gap-1',
        alineacion === 'centro' ? 'justify-center' : 'justify-end',
      )}
    >
      {children}
    </div>
  );
}
