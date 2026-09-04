'use client';

import { bilingue, useIdioma } from '@/lib/i18n';
import type { RegistroControlInsumo } from '@/lib/types';
import { formatearFechaIso } from '@/lib/utils';

/**
 * Historial de salidas.
 *
 * **Sin columna de acciones, a propósito:** el registro es un histórico y no se
 * edita ni se borra. Un error se corrige ajustando la existencia desde
 * Catálogo, que deja su propio rastro en la bitácora.
 */
export function TablaInsumos({ registros }: { registros: RegistroControlInsumo[] }) {
  const { t, locale } = useIdioma();

  if (registros.length === 0) {
    return (
      <p className="text-sm text-texto-suave">
        {bilingue(t('controlInsumos.historialVacio'))}
      </p>
    );
  }

  return (
    <div className="overflow-x-auto rounded-tarjeta border border-borde">
      <table className="w-full min-w-[60rem] border-collapse text-sm">
        <thead className="bg-fondo-sutil text-left text-texto-suave">
          <tr>
            <th className="px-3 py-2 font-medium">{bilingue(t('comun.fecha'))}</th>
            <th className="px-3 py-2 font-medium">
              {bilingue(t('controlInsumos.colInsumo'))}
            </th>
            <th className="px-3 py-2 font-medium">
              {bilingue(t('controlInsumos.colEntregadoA'))}
            </th>
            <th className="px-3 py-2 font-medium">{bilingue(t('comun.area'))}</th>
            <th className="px-3 py-2 text-right font-medium">
              {bilingue(t('controlInsumos.colConsumo'))}
            </th>
            <th className="px-3 py-2 text-right font-medium">
              {bilingue(t('controlInsumos.colDescontado'))}
            </th>
            <th className="px-3 py-2 font-medium">
              {bilingue(t('controlInsumos.colTermino'))}
            </th>
            <th className="px-3 py-2 font-medium">
              {bilingue(t('comun.responsable'))}
            </th>
          </tr>
        </thead>
        <tbody>
          {registros.map((registro) => (
            <tr key={registro.id} className="border-t border-borde">
              <td className="whitespace-nowrap px-3 py-2 text-texto-suave">
                {formatearFechaIso(registro.fecha, locale)}
              </td>
              <td className="px-3 py-2 text-texto">
                {/* Dato del catálogo: no se traduce ni se envuelve. */}
                <span className="font-medium">{registro.codigo}</span>
                <span className="text-texto-suave"> · {registro.descripcion}</span>
              </td>
              <td className="px-3 py-2 text-texto-suave">{registro.entregado_a}</td>
              <td className="px-3 py-2 text-texto-suave">{registro.area_etiqueta}</td>
              <td className="px-3 py-2 text-right text-texto">
                {registro.consumo} {registro.unidad_medida}
              </td>
              {/* Un cero aquí no es un error: el producto se usó pero no se
                  terminó, así que el inventario no bajó ninguna pieza. */}
              <td className="px-3 py-2 text-right text-texto">{registro.descontado}</td>
              <td className="px-3 py-2 text-texto-suave">
                {registro.termino === null
                  ? t('controlInsumos.noAplica')
                  : bilingue(registro.termino ? t('comun.si') : t('comun.no'))}
              </td>
              <td className="px-3 py-2 text-texto-suave">{registro.responsable}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
