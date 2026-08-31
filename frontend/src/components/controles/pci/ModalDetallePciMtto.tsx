'use client';

import { Modal } from '@/components/ui/Modal';
import { urlFotoControl } from '@/lib/api';
import { bilingue, useIdioma } from '@/lib/i18n';
import type { RegistroPciMtto } from '@/lib/types';
import { formatearFechaIso } from '@/lib/utils';

/**
 * Detalle de un registro del control.
 *
 * Modal propio y no `ModalDetalleRegistro`: aquel pide siempre
 * `/controles/cierres/{control}/{id}` y espera la forma `DetalleCierre`. Este
 * control no participa del sistema de hallazgos y cierres, así que forzarlo
 * saldría más caro que estas líneas.
 */
interface ModalDetallePciMttoProps {
  registro: RegistroPciMtto | null;
  onCerrar: () => void;
}

export function ModalDetallePciMtto({
  registro,
  onCerrar,
}: ModalDetallePciMttoProps) {
  const { t, locale } = useIdioma();

  const nombreMes =
    registro === null
      ? ''
      : new Intl.DateTimeFormat(locale, {
          month: 'long',
          year: 'numeric',
        }).format(new Date(registro.anio, registro.mes - 1, 1));

  return (
    <Modal
      abierto={registro !== null}
      onCerrar={onCerrar}
      titulo={t('pciMtto.titulo')}
      descripcion={nombreMes}
      ancho="md"
    >
      {registro !== null && (
        <div className="flex flex-col gap-5">
          <dl className="grid gap-3 sm:grid-cols-2">
            <div>
              <dt className="text-sm text-texto-tenue">
                {bilingue(t('pciMtto.mtto'))}
              </dt>
              <dd
                className={
                  registro.realizado
                    ? 'text-sm font-semibold text-exito'
                    : 'text-sm font-semibold text-error'
                }
              >
                {bilingue(registro.realizado ? t('comun.si') : t('comun.no'))}
              </dd>
            </div>

            <div>
              <dt className="text-sm text-texto-tenue">
                {bilingue(t('comun.fecha'))}
              </dt>
              <dd className="text-sm text-texto">
                {registro.fecha === null
                  ? '—'
                  : formatearFechaIso(registro.fecha, locale)}
              </dd>
            </div>

            <div>
              <dt className="text-sm text-texto-tenue">
                {bilingue(t('comun.responsable'))}
              </dt>
              <dd className="text-sm text-texto">{registro.responsable}</dd>
            </div>

            <div>
              <dt className="text-sm text-texto-tenue">
                {bilingue(t('pciMtto.reporte'))}
              </dt>
              <dd className="text-sm text-texto">
                {registro.reporte_nombre ?? (
                  <span className="text-texto-tenue">
                    {bilingue(t('pciMtto.sinReporte'))}
                  </span>
                )}
              </dd>
            </div>
          </dl>

          {!registro.realizado && (
            <div>
              <dt className="text-sm text-texto-tenue">
                {bilingue(t('pciMtto.motivo'))}
              </dt>
              <dd className="whitespace-pre-line text-sm text-texto">
                {registro.motivo ?? (
                  <span className="italic text-error">
                    {bilingue(t('pciMtto.sinMotivo'))}
                  </span>
                )}
              </dd>
            </div>
          )}

          {registro.automatico && (
            <p className="rounded-md border border-alerta bg-alerta-suave px-3 py-2 text-sm text-texto-suave">
              {bilingue(t('pciMtto.cerradoPorSistema'))}
            </p>
          )}

          {registro.fotos.length > 0 && (
            <div className="flex flex-col gap-2">
              <span className="text-sm text-texto-tenue">
                {bilingue(t('pciMtto.evidencia'))}
              </span>
              <ul className="flex flex-wrap gap-2">
                {registro.fotos.map((id, indice) => (
                  <li key={id}>
                    <a href={urlFotoControl(id)} target="_blank" rel="noreferrer">
                      {/* eslint-disable-next-line @next/next/no-img-element -- la
                          sirve la API con la cookie de sesión. */}
                      <img
                        src={urlFotoControl(id)}
                        alt={t('fotos.numero', { numero: indice + 1 })}
                        className="h-24 w-24 rounded-md border border-borde object-cover"
                      />
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}
