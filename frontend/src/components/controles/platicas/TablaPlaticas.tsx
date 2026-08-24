'use client';

import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { urlFotoControl } from '@/lib/api';
import { useIdioma } from '@/lib/i18n';
import type { Platica } from '@/lib/types';
import { formatearFechaIso } from '@/lib/utils';

interface TablaPlaticasProps {
  platicas: Platica[];
  onEliminar: (platica: Platica) => void;
}

export function TablaPlaticas({ platicas, onEliminar }: TablaPlaticasProps) {
  const { t, locale } = useIdioma();

  if (platicas.length === 0) {
    return (
      <p className="rounded-tarjeta border border-borde bg-fondo-elevado px-4 py-8 text-center text-sm text-texto-suave">
        {t('platicas.historialVacio')}
      </p>
    );
  }

  return (
    <div className="overflow-x-auto rounded-tarjeta border border-borde">
      <table className="w-full min-w-[46rem] border-collapse text-sm">
        <thead className="bg-fondo-sutil text-left text-texto-suave">
          <tr>
            <th className="px-3 py-2 font-medium">{t('comun.fecha')}</th>
            <th className="px-3 py-2 font-medium">{t('platicas.tema')}</th>
            <th className="px-3 py-2 font-medium">{t('platicas.areas')}</th>
            <th className="px-3 py-2 font-medium">{t('fotos.titulo')}</th>
            <th className="px-3 py-2 font-medium">{t('comun.responsable')}</th>
            <th className="px-3 py-2 font-medium">
              <span className="sr-only">{t('comun.acciones')}</span>
            </th>
          </tr>
        </thead>

        <tbody>
          {platicas.map((platica) => (
            <tr key={platica.id} className="border-t border-borde align-top">
              <td className="whitespace-nowrap px-3 py-2 text-texto">
                {formatearFechaIso(platica.fecha, locale)}
              </td>

              <td className="max-w-sm px-3 py-2 text-texto">{platica.tema}</td>

              <td className="px-3 py-2">
                <span className="flex flex-wrap gap-1">
                  {platica.areas.map((area) => (
                    <Badge key={area.clave} tono="neutro">
                      {area.etiqueta}
                    </Badge>
                  ))}
                </span>
              </td>

              <td className="px-3 py-2">
                <span className="flex flex-wrap gap-1">
                  {platica.fotos.map((foto) => (
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
              </td>

              <td className="whitespace-nowrap px-3 py-2 text-texto-suave">
                {platica.responsable}
              </td>

              <td className="px-3 py-2 text-right">
                <Button
                  variante="fantasma"
                  tamano="sm"
                  onClick={() => onEliminar(platica)}
                >
                  {t('comun.eliminar')}
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
