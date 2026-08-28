'use client';

import type { ReactNode } from 'react';

import {
  IconoBote,
  IconoDescargar,
  IconoOjo,
  IconoPalomita,
  IconoPortapapeles,
} from '@/components/ui/Iconos';
import { useTraduccion } from '@/lib/i18n';
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
 * No usa `ui/Button` porque ese componente reserva espacio horizontal para
 * texto y aquí caben cuatro acciones en una celda. Lo que sí conserva es el
 * objetivo táctil: 32 px de lado, que es lo mínimo cómodo con guantes.
 *
 * **Siempre lleva `aria-label` y `title`.** Sin texto visible, esa es la única
 * forma de saber qué hace el botón: el `title` para quien lo ve y duda, el
 * `aria-label` para quien no lo ve.
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

interface AccionesRegistroProps {
  /** Opcional: Pláticas no tiene detalle que mostrar, solo su renglón. */
  onVerDetalle?: () => void;
  /**
   * Solo se pasa cuando la hoja tiene hallazgos: en una inspección limpia no
   * hay nada que cerrar y el botón sería ruido. Pláticas nunca lo lleva.
   */
  onCerrarHallazgo?: () => void;
  /** Ya tiene cierre guardado: el icono lo dice en vez de invitar a crearlo. */
  cerrado?: boolean;
  onEliminar?: () => void;
  /** Descarga esa hoja en Excel; solo donde existe la exportación suelta. */
  onDescargar?: () => void;
  descargando?: boolean;
  deshabilitado?: boolean;
}

/**
 * La columna de Acciones, igual en las cinco tablas de registros.
 *
 * Vive aquí y no en cada tabla porque son cinco historiales con la misma
 * botonera y distinto tipo de fila; repetirla llevaría a que se separen.
 */
export function AccionesRegistro({
  onVerDetalle,
  onCerrarHallazgo,
  cerrado = false,
  onEliminar,
  onDescargar,
  descargando,
  deshabilitado,
}: AccionesRegistroProps) {
  const t = useTraduccion();

  return (
    <div className="flex items-center justify-end gap-1">
      {onDescargar && (
        <BotonIcono
          etiqueta={t('comun.descargarExcel')}
          icono={<IconoDescargar />}
          onClick={onDescargar}
          cargando={descargando}
          deshabilitado={deshabilitado}
        />
      )}

      {onVerDetalle && (
        <BotonIcono
          etiqueta={t('cierre.verDetalle')}
          icono={<IconoOjo />}
          onClick={onVerDetalle}
          deshabilitado={deshabilitado}
        />
      )}

      {onCerrarHallazgo && (
        <BotonIcono
          // Cerrado va con palomita y en verde; pendiente, con el
          // portapapeles que invita a capturarlo.
          etiqueta={cerrado ? t('cierre.cerrado') : t('cierre.abrir')}
          icono={cerrado ? <IconoPalomita /> : <IconoPortapapeles />}
          onClick={onCerrarHallazgo}
          tono={cerrado ? 'exito' : 'neutro'}
          deshabilitado={deshabilitado}
        />
      )}

      {onEliminar && (
        <BotonIcono
          etiqueta={t('comun.eliminar')}
          icono={<IconoBote />}
          onClick={onEliminar}
          tono="error"
          deshabilitado={deshabilitado}
        />
      )}
    </div>
  );
}
