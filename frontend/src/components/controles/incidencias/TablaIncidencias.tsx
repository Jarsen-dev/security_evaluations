'use client';

import { AccionesRegistro } from '@/components/controles/AccionesRegistro';
import { Badge } from '@/components/ui/Badge';
import { useIdioma, type ClaveTraduccion } from '@/lib/i18n';
import type { Incidencia } from '@/lib/types';
import { formatearFechaIso } from '@/lib/utils';

/**
 * Nombre de cada control, desde el diccionario.
 *
 * El backend manda la clave; el rótulo es interfaz y se traduce (regla 6).
 * Las claves son las mismas que ya usa la barra de pestañas.
 */
const NOMBRE_CONTROL: Record<string, ClaveTraduccion> = {
  sqp: 'controles.sqp',
  rayser: 'controles.rayser',
  almacen_rp: 'controles.almacenRp',
  recorridos: 'controles.recorridos',
  muro: 'controles.muro',
  silos: 'controles.silos',
  tableros: 'controles.tableros',
};

interface TablaIncidenciasProps {
  incidencias: Incidencia[];
  onVerDetalle: (incidencia: Incidencia) => void;
}

export function TablaIncidencias({
  incidencias,
  onVerDetalle,
}: TablaIncidenciasProps) {
  const { t, locale } = useIdioma();

  if (incidencias.length === 0) {
    return <p className="text-sm text-texto-suave">{t('incidencias.vacio')}</p>;
  }

  return (
    <div className="overflow-x-auto rounded-tarjeta border border-borde">
      <table className="w-full min-w-[52rem] border-collapse text-sm">
        <thead className="bg-fondo-sutil text-left text-texto-suave">
          <tr>
            <th className="px-3 py-2 font-medium">{t('comun.fecha')}</th>
            <th className="px-3 py-2 font-medium">{t('incidencias.control')}</th>
            <th className="px-3 py-2 font-medium">
              {t('incidencias.identificacion')}
            </th>
            <th className="px-3 py-2 font-medium">{t('incidencias.problemas')}</th>
            <th className="px-3 py-2 font-medium">{t('incidencias.estado')}</th>
            <th className="px-3 py-2 font-medium">{t('comun.responsable')}</th>
            <th className="px-3 py-2 text-right font-medium">
              {t('comun.acciones')}
            </th>
          </tr>
        </thead>

        <tbody>
          {incidencias.map((incidencia) => {
            const clave = NOMBRE_CONTROL[incidencia.control];
            // Un cierre con acción pendiente está resuelto pero arrastra algo:
            // se distingue del cerrado limpio para que no se pierda de vista.
            const conPendiente = Boolean(incidencia.cierre?.accion_pendiente);

            return (
              <tr
                key={`${incidencia.control}-${incidencia.registro_id}`}
                className="border-t border-borde align-top"
              >
                <td className="whitespace-nowrap px-3 py-2 text-texto">
                  {formatearFechaIso(incidencia.fecha, locale)}
                </td>

                <td className="px-3 py-2 text-texto">
                  {clave ? t(clave) : incidencia.control}
                </td>

                <td className="px-3 py-2 text-texto-suave">
                  {incidencia.identificacion || '—'}
                </td>

                <td className="whitespace-nowrap px-3 py-2 text-texto-suave">
                  {incidencia.total_hallazgos}
                </td>

                <td className="px-3 py-2">
                  {incidencia.estado === 'cerrado' ? (
                    <Badge tono={conPendiente ? 'alerta' : 'exito'}>
                      {conPendiente
                        ? t('incidencias.conPendiente')
                        : t('cierre.cerrado')}
                    </Badge>
                  ) : (
                    <Badge tono="error">{t('cierre.pendiente')}</Badge>
                  )}
                </td>

                <td className="whitespace-nowrap px-3 py-2 text-texto-suave">
                  {incidencia.responsable}
                </td>

                <td className="px-3 py-2 text-right">
                  {/* Aquí solo el detalle: el cierre se captura desde la
                      pestaña del control al que pertenece la hoja. */}
                  <AccionesRegistro onVerDetalle={() => onVerDetalle(incidencia)} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
