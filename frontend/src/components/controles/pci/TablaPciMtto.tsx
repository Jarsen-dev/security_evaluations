'use client';

import { BotonIcono } from '@/components/controles/AccionesRegistro';
import { IconoDescargar, IconoLapiz, IconoOjo } from '@/components/ui/Iconos';
import { urlFotoControl } from '@/lib/api';
import { bilingue, useIdioma } from '@/lib/i18n';
import type { RegistroPciMtto } from '@/lib/types';
import { cn, formatearFechaIso } from '@/lib/utils';

interface TablaPciMttoProps {
  registros: RegistroPciMtto[];
  onVerDetalle: (registro: RegistroPciMtto) => void;
  onCorregir: (registro: RegistroPciMtto) => void;
  onDescargar: (registro: RegistroPciMtto) => void;
  descargando: string | null;
  puedeEditar: boolean;
}

export function TablaPciMtto({
  registros,
  onVerDetalle,
  onCorregir,
  onDescargar,
  descargando,
  puedeEditar,
}: TablaPciMttoProps) {
  const { t, locale } = useIdioma();

  if (registros.length === 0) {
    return <p className="text-sm text-texto-suave">{bilingue(t('pciMtto.vacio'))}</p>;
  }

  return (
    <div className="overflow-x-auto rounded-tarjeta border border-borde">
      <table className="w-full min-w-[56rem] border-collapse text-sm">
        <thead className="bg-fondo-sutil text-left text-texto-suave">
          <tr>
            <th className="px-3 py-2 font-medium">{bilingue(t('pciMtto.anio'))}</th>
            <th className="px-3 py-2 font-medium">{bilingue(t('pciMtto.mes'))}</th>
            <th className="px-3 py-2 font-medium">{bilingue(t('comun.fecha'))}</th>
            <th className="px-3 py-2 font-medium">{bilingue(t('pciMtto.mtto'))}</th>
            <th className="px-3 py-2 font-medium">{bilingue(t('pciMtto.motivo'))}</th>
            <th className="px-3 py-2 font-medium">
              {bilingue(t('pciMtto.evidencia'))}
            </th>
            <th className="px-3 py-2 text-right font-medium">
              {bilingue(t('comun.acciones'))}
            </th>
          </tr>
        </thead>

        <tbody>
          {registros.map((registro) => {
            const nombreMes = new Intl.DateTimeFormat(locale, {
              month: 'long',
            }).format(new Date(registro.anio, registro.mes - 1, 1));

            return (
              <tr
                key={registro.id}
                className={cn(
                  'border-t border-borde align-top',
                  // La fila entera dice el resultado de un vistazo; el texto de
                  // la columna MTTO lo repite, así que el color no va solo.
                  registro.realizado ? 'bg-exito-suave/30' : 'bg-error-suave/30',
                )}
              >
                <td className="whitespace-nowrap px-3 py-2 text-texto">
                  {registro.anio}
                </td>
                <td className="whitespace-nowrap px-3 py-2 capitalize text-texto">
                  {nombreMes}
                </td>
                <td className="whitespace-nowrap px-3 py-2 text-texto-suave">
                  {registro.fecha === null
                    ? '—'
                    : formatearFechaIso(registro.fecha, locale)}
                </td>
                <td className="px-3 py-2">
                  <span
                    className={cn(
                      'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold',
                      registro.realizado
                        ? 'bg-exito-suave text-exito'
                        : 'bg-error-suave text-error',
                    )}
                  >
                    {bilingue(registro.realizado ? t('comun.si') : t('comun.no'))}
                  </span>
                </td>
                <td className="max-w-[20rem] px-3 py-2 text-texto-suave">
                  {registro.realizado ? (
                    '—'
                  ) : registro.motivo === null ? (
                    <span className="italic text-error">
                      {bilingue(t('pciMtto.sinMotivo'))}
                    </span>
                  ) : (
                    <span className="whitespace-pre-line">{registro.motivo}</span>
                  )}
                </td>
                <td className="px-3 py-2">
                  {registro.fotos.length === 0 ? (
                    <span className="text-texto-tenue">—</span>
                  ) : (
                    <ul className="flex flex-wrap gap-1">
                      {registro.fotos.map((id, indice) => (
                        <li key={id}>
                          <a href={urlFotoControl(id)} target="_blank" rel="noreferrer">
                            {/* eslint-disable-next-line @next/next/no-img-element -- la
                                sirve la API con la cookie de sesión. */}
                            <img
                              src={urlFotoControl(id)}
                              alt={t('fotos.numero', { numero: indice + 1 })}
                              className="h-10 w-10 rounded border border-borde object-cover"
                            />
                          </a>
                        </li>
                      ))}
                    </ul>
                  )}
                </td>
                <td className="px-3 py-2">
                  <div className="flex items-center justify-end gap-1">
                    <BotonIcono
                      etiqueta={t('pciMtto.reporteDescargar')}
                      icono={<IconoDescargar />}
                      onClick={() => onDescargar(registro)}
                      cargando={descargando === registro.id}
                      deshabilitado={!registro.tiene_reporte}
                    />
                    <BotonIcono
                      etiqueta={t('cierre.verDetalle')}
                      icono={<IconoOjo />}
                      onClick={() => onVerDetalle(registro)}
                    />
                    {puedeEditar && (
                      <BotonIcono
                        etiqueta={t('pciMtto.corregir')}
                        icono={<IconoLapiz />}
                        onClick={() => onCorregir(registro)}
                      />
                    )}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
