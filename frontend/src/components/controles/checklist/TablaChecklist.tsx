'use client';

import { Button } from '@/components/ui/Button';
import { urlFotoControl } from '@/lib/api';
import { useIdioma } from '@/lib/i18n';
import type { CatalogoChecklist, RegistroChecklist } from '@/lib/types';
import { cn, formatearFechaIso } from '@/lib/utils';

interface TablaChecklistProps {
  catalogo: CatalogoChecklist;
  registros: RegistroChecklist[];
  onEliminar: (registro: RegistroChecklist) => void;
}

/** Colores de cada resultado. El texto va siempre, el color solo acompaña. */
const CELDA = {
  ok: 'border-exito bg-exito-suave text-exito',
  no_ok: 'border-error bg-error-suave text-error',
} as const;

export function TablaChecklist({
  catalogo,
  registros,
  onEliminar,
}: TablaChecklistProps) {
  const { t, locale } = useIdioma();

  if (registros.length === 0) {
    return (
      <p className="rounded-tarjeta border border-borde bg-fondo-elevado px-4 py-8 text-center text-sm text-texto-suave">
        {t('checklist.historialVacio')}
      </p>
    );
  }

  return (
    <div className="overflow-x-auto rounded-tarjeta border border-borde">
      <table className="w-full min-w-[50rem] border-collapse text-sm">
        <thead className="bg-fondo-sutil text-left text-texto-suave">
          <tr>
            <th className="px-3 py-2 font-medium">{t('comun.fecha')}</th>
            {catalogo.puntos.map((punto) => (
              <th key={punto.orden} className="px-3 py-2 text-center font-medium">
                {punto.etiqueta}
              </th>
            ))}
            <th className="px-3 py-2 font-medium">{t('comun.observaciones')}</th>
            <th className="px-3 py-2 font-medium">{t('comun.responsable')}</th>
            <th className="px-3 py-2 font-medium">
              <span className="sr-only">{t('comun.acciones')}</span>
            </th>
          </tr>
        </thead>

        <tbody>
          {registros.map((registro) => {
            const hallazgos = registro.puntos.filter(
              (punto) => punto.valor === 'no_ok',
            );

            return (
              <tr key={registro.id} className="border-t border-borde align-top">
                <td className="whitespace-nowrap px-3 py-2 text-texto">
                  {formatearFechaIso(registro.fecha, locale)}
                </td>

                {registro.puntos.map((punto) => (
                  <td key={punto.orden} className="px-2 py-2 text-center">
                    <span
                      className={cn(
                        'inline-block rounded-md border px-2 py-1 text-xs font-medium',
                        CELDA[punto.valor],
                      )}
                    >
                      {punto.valor === 'ok' ? t('checklist.ok') : t('checklist.noOk')}
                    </span>
                  </td>
                ))}

                <td className="max-w-sm px-3 py-2 text-texto-suave">
                  {hallazgos.length === 0 ? (
                    '—'
                  ) : (
                    <ul className="flex flex-col gap-2">
                      {hallazgos.map((punto) => (
                        <li key={punto.orden}>
                          <span className="font-medium text-texto">
                            {punto.etiqueta}:
                          </span>{' '}
                          {punto.observaciones}
                          {punto.fotos.length > 0 && (
                            <span className="mt-1 flex flex-wrap gap-1">
                              {punto.fotos.map((foto) => (
                                <a
                                  key={foto}
                                  href={urlFotoControl(foto)}
                                  target="_blank"
                                  rel="noreferrer"
                                  title={t('fotos.ver')}
                                  className="inline-block overflow-hidden rounded border border-borde"
                                >
                                  {/* eslint-disable-next-line @next/next/no-img-element --
                                      la sirve la API con la cookie de sesión. */}
                                  <img
                                    src={urlFotoControl(foto)}
                                    alt={t('fotos.ver')}
                                    className="h-12 w-16 object-cover"
                                  />
                                </a>
                              ))}
                            </span>
                          )}
                        </li>
                      ))}
                    </ul>
                  )}
                </td>

                <td className="whitespace-nowrap px-3 py-2 text-texto-suave">
                  {registro.responsable}
                </td>

                <td className="px-3 py-2 text-right">
                  <Button
                    variante="fantasma"
                    tamano="sm"
                    onClick={() => onEliminar(registro)}
                  >
                    {t('comun.eliminar')}
                  </Button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
