'use client';

import { BotonIcono, FilaAcciones } from '@/components/ui/BotonIcono';
import {
  IconoBote,
  IconoDescargar,
  IconoOjo,
  IconoPalomita,
  IconoPortapapeles,
} from '@/components/ui/Iconos';
import { useTraduccion } from '@/lib/i18n';

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
    <FilaAcciones>
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
    </FilaAcciones>
  );
}
