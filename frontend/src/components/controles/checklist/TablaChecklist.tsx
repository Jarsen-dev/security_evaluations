'use client';

import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { urlFotoControl } from '@/lib/api';
import { useIdioma } from '@/lib/i18n';
import type { CatalogoChecklist, PuntoChecklist, RegistroChecklist } from '@/lib/types';
import { cn, formatearFechaIso } from '@/lib/utils';

interface TablaChecklistProps {
  catalogo: CatalogoChecklist;
  registros: RegistroChecklist[];
  onEliminar: (registro: RegistroChecklist) => void;
  /** Solo en los formatos por inspección: descarga esa hoja en Excel. */
  onDescargar?: (registro: RegistroChecklist) => void;
  descargandoId?: string | null;
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
  onDescargar,
  descargandoId,
}: TablaChecklistProps) {
  const { t, locale, idioma } = useIdioma();

  if (registros.length === 0) {
    return (
      <p className="rounded-tarjeta border border-borde bg-fondo-elevado px-4 py-8 text-center text-sm text-texto-suave">
        {t('checklist.historialVacio')}
      </p>
    );
  }

  const etiquetaValor = (valor: PuntoChecklist['valor']) =>
    valor === 'ok' ? t('checklist.conforme') : t('checklist.inconforme');

  /** Los hallazgos, con su texto y sus fotos: el resto de la hoja no aporta. */
  function hallazgos(registro: RegistroChecklist) {
    return registro.puntos.filter((punto) => punto.valor === 'no_ok');
  }

  function celdaHallazgos(registro: RegistroChecklist) {
    const puntos = hallazgos(registro);

    if (puntos.length === 0) {
      return <span className="text-texto-tenue">—</span>;
    }

    return (
      <ul className="flex flex-col gap-2">
        {puntos.map((punto) => (
          <li key={punto.orden}>
            <span className="font-medium text-texto">
              {idioma === 'ko' && punto.etiqueta_ko ? punto.etiqueta_ko : punto.etiqueta}:
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
                    {/* eslint-disable-next-line @next/next/no-img-element -- la
                        sirve la API con la cookie de sesión. */}
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
    );
  }

  // Los formatos por inspección no caben como rejilla: en su lugar se listan
  // los datos que identifican cada hoja y sus hallazgos.
  const columnasEncabezado = catalogo.por_inspeccion
    ? catalogo.encabezado.filter((campo) => campo.tipo !== 'texto_largo')
    : [];

  return (
    <div className="overflow-x-auto rounded-tarjeta border border-borde">
      <table className="w-full min-w-[50rem] border-collapse text-sm">
        <thead className="bg-fondo-sutil text-left text-texto-suave">
          <tr>
            <th className="px-3 py-2 font-medium">{t('comun.fecha')}</th>

            {columnasEncabezado.map((campo) => (
              <th key={campo.clave} className="px-3 py-2 font-medium">
                {idioma === 'ko' && campo.etiqueta_ko ? campo.etiqueta_ko : campo.etiqueta}
              </th>
            ))}

            {catalogo.por_inspeccion ? (
              <th className="px-3 py-2 font-medium">{t('checklist.hallazgos')}</th>
            ) : (
              catalogo.puntos.map((punto) => (
                <th key={punto.orden} className="px-3 py-2 text-center font-medium">
                  {punto.etiqueta}
                </th>
              ))
            )}

            <th className="px-3 py-2 font-medium">{t('comun.observaciones')}</th>
            <th className="px-3 py-2 font-medium">{t('comun.responsable')}</th>
            <th className="px-3 py-2 font-medium">
              <span className="sr-only">{t('comun.acciones')}</span>
            </th>
          </tr>
        </thead>

        <tbody>
          {registros.map((registro) => (
            <tr key={registro.id} className="border-t border-borde align-top">
              <td className="whitespace-nowrap px-3 py-2 text-texto">
                {formatearFechaIso(registro.fecha, locale)}
              </td>

              {columnasEncabezado.map((campo) => (
                <td
                  key={campo.clave}
                  className="whitespace-nowrap px-3 py-2 text-texto-suave"
                >
                  {registro.encabezado[campo.clave] ?? '—'}
                </td>
              ))}

              {catalogo.por_inspeccion ? (
                <td className="px-3 py-2">
                  <Badge tono={registro.hay_hallazgos ? 'error' : 'exito'}>
                    {t('checklist.hallazgosDetalle', {
                      total: hallazgos(registro).length,
                    })}
                  </Badge>
                </td>
              ) : (
                registro.puntos.map((punto) => (
                  <td key={punto.orden} className="px-2 py-2 text-center">
                    <span
                      className={cn(
                        'inline-block rounded-md border px-2 py-1 text-xs font-medium',
                        CELDA[punto.valor],
                      )}
                    >
                      {etiquetaValor(punto.valor)}
                    </span>
                  </td>
                ))
              )}

              <td className="max-w-sm px-3 py-2 text-texto-suave">
                {celdaHallazgos(registro)}
              </td>

              <td className="whitespace-nowrap px-3 py-2 text-texto-suave">
                {registro.responsable}
              </td>

              <td className="px-3 py-2 text-right">
                <span className="flex justify-end gap-2">
                  {onDescargar && (
                    <Button
                      variante="secundario"
                      tamano="sm"
                      onClick={() => onDescargar(registro)}
                      cargando={descargandoId === registro.id}
                    >
                      {t('comun.descargarExcel')}
                    </Button>
                  )}
                  <Button
                    variante="fantasma"
                    tamano="sm"
                    onClick={() => onEliminar(registro)}
                  >
                    {t('comun.eliminar')}
                  </Button>
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
