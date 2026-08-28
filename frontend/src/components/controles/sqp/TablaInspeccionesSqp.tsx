'use client';

import { Badge } from '@/components/ui/Badge';
import { AccionesRegistro } from '@/components/controles/AccionesRegistro';
import { useIdioma } from '@/lib/i18n';
import type { InspeccionSqpResumen } from '@/lib/types';
import { formatearFechaIso } from '@/lib/utils';

interface TablaInspeccionesSqpProps {
  inspecciones: InspeccionSqpResumen[];
  onDescargar: (inspeccion: InspeccionSqpResumen) => void;
  onVerDetalle: (inspeccion: InspeccionSqpResumen) => void;
  onCerrarHallazgo: (inspeccion: InspeccionSqpResumen) => void;
  /** Ids de las inspecciones que ya tienen cierre. */
  cerrados: ReadonlySet<string>;
  descargandoId: string | null;
}

export function TablaInspeccionesSqp({
  inspecciones,
  onDescargar,
  onVerDetalle,
  onCerrarHallazgo,
  cerrados,
  descargandoId,
}: TablaInspeccionesSqpProps) {
  const { t, locale } = useIdioma();

  if (inspecciones.length === 0) {
    return (
      <p className="rounded-tarjeta border border-borde bg-fondo-elevado px-4 py-8 text-center text-sm text-texto-suave">
        {t('sqp.historialVacio')}
      </p>
    );
  }

  return (
    <div className="overflow-x-auto rounded-tarjeta border border-borde">
      <table className="w-full min-w-[44rem] border-collapse text-sm">
        <thead className="bg-fondo-sutil text-left text-texto-suave">
          <tr>
            <th className="px-3 py-2 font-medium">{t('comun.fecha')}</th>
            <th className="px-3 py-2 font-medium">{t('comun.area')}</th>
            <th className="px-3 py-2 font-medium">{t('sqp.encargado')}</th>
            <th className="px-3 py-2 font-medium">{t('comun.responsable')}</th>
            <th className="px-3 py-2 font-medium">{t('sqp.hallazgos')}</th>
            <th className="px-3 py-2 text-right font-medium">
              {t('comun.acciones')}
            </th>
          </tr>
        </thead>

        <tbody>
          {inspecciones.map((inspeccion) => (
            <tr key={inspeccion.id} className="border-t border-borde">
              <td className="whitespace-nowrap px-3 py-2 text-texto">
                {formatearFechaIso(inspeccion.fecha, locale)}
              </td>
              <td className="px-3 py-2 text-texto-suave">{inspeccion.area_label}</td>
              <td className="px-3 py-2 text-texto-suave">{inspeccion.encargado}</td>
              <td className="px-3 py-2 text-texto-suave">{inspeccion.responsable}</td>
              <td className="px-3 py-2">
                <Badge tono={inspeccion.total_no > 0 ? 'error' : 'exito'}>
                  {t('sqp.hallazgosDetalle', { total: inspeccion.total_no })}
                </Badge>
              </td>
              <td className="px-3 py-2 text-right">
                <AccionesRegistro
                  onDescargar={() => onDescargar(inspeccion)}
                  descargando={descargandoId === inspeccion.id}
                  onVerDetalle={() => onVerDetalle(inspeccion)}
                  // El hallazgo de SQP es cada punto contestado con NO.
                  onCerrarHallazgo={
                    inspeccion.total_no > 0
                      ? () => onCerrarHallazgo(inspeccion)
                      : undefined
                  }
                  cerrado={cerrados.has(inspeccion.id)}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
