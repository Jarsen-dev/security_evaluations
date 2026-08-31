'use client';

import { useEffect, useState } from 'react';

import { ListaHallazgos } from '@/components/controles/ModalCierreHallazgo';
import { Modal } from '@/components/ui/Modal';
import { ErrorDeApi, obtenerCierre, urlFotoControl } from '@/lib/api';
import { bilingue, useIdioma, useTraduccion } from '@/lib/i18n';
import type { CierreHallazgo, DetalleCierre } from '@/lib/types';
import { formatearFechaIso } from '@/lib/utils';

interface ModalDetalleRegistroProps {
  abierto: boolean;
  control: string;
  registroId: string | null;
  onCerrar: () => void;
  onError: (mensaje: string) => void;
  /**
   * Lo propio de cada control —encabezado, lecturas, áreas—, que la tabla ya
   * tiene a la mano y no vale la pena volver a pedir.
   */
  children?: React.ReactNode;
}

/**
 * La hoja completa y, al final, su cierre de hallazgo.
 *
 * Los hallazgos y el cierre se piden a la misma ruta que usa el modal de
 * cierre: es la única que sabe traducir los tres controles a la misma forma.
 */
export function ModalDetalleRegistro({
  abierto,
  control,
  registroId,
  onCerrar,
  onError,
  children,
}: ModalDetalleRegistroProps) {
  const { t, locale } = useIdioma();

  const [detalle, setDetalle] = useState<DetalleCierre | null>(null);
  const [cargando, setCargando] = useState(false);

  useEffect(() => {
    if (!abierto || registroId === null) {
      return;
    }

    let cancelado = false;
    setCargando(true);
    setDetalle(null);

    obtenerCierre(control, registroId)
      .then((datos) => {
        if (!cancelado) {
          setDetalle(datos);
        }
      })
      .catch((error: unknown) => {
        if (!cancelado) {
          onError(error instanceof ErrorDeApi ? error.message : t('comun.errorGenerico'));
        }
      })
      .finally(() => {
        if (!cancelado) {
          setCargando(false);
        }
      });

    return () => {
      cancelado = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [abierto, control, registroId]);

  return (
    <Modal
      abierto={abierto}
      onCerrar={onCerrar}
      titulo={t('cierre.detalleTitulo')}
      descripcion={
        detalle ? formatearFechaIso(detalle.fecha, locale) : undefined
      }
      ancho="lg"
    >
      {cargando ? (
        <p className="text-sm text-texto-suave">{bilingue(t('comun.cargando'))}</p>
      ) : (
        <div className="flex flex-col gap-5">
          {children}

          <ListaHallazgos hallazgos={detalle?.hallazgos ?? []} />

          {detalle?.cierre ? (
            <BloqueCierre cierre={detalle.cierre} />
          ) : (
            (detalle?.hallazgos.length ?? 0) > 0 && (
              <p className="rounded-md border border-alerta bg-alerta-suave px-3 py-2 text-sm text-texto-suave">
                {bilingue(t('cierre.sinCierre'))}
              </p>
            )
          )}
        </div>
      )}
    </Modal>
  );
}

/** El cierre ya guardado, en solo lectura, al final del detalle. */
function BloqueCierre({ cierre }: { cierre: CierreHallazgo }) {
  const t = useTraduccion();

  const campos: Array<[string, string]> = [
    [t('cierre.horaHallazgo'), cierre.hora_hallazgo],
    [t('cierre.ubicacion'), cierre.ubicacion],
    [t('cierre.responsableAccion'), cierre.responsable_accion],
    [t('cierre.horaCierre'), cierre.hora_cierre],
  ];

  return (
    <section className="flex flex-col gap-3 rounded-md border border-exito bg-exito-suave/30 p-4">
      <h3 className="text-sm font-semibold text-texto">
        ✓ {bilingue(t('cierre.titulo'))}
        <span className="ml-2 font-normal text-texto-tenue">
          {bilingue(t('cierre.registradoPor', { responsable: cierre.responsable }))}
        </span>
      </h3>

      <dl className="grid gap-3 sm:grid-cols-2">
        {campos.map(([etiqueta, valor]) => (
          <div key={etiqueta}>
            <dt className="text-sm text-texto-tenue">{bilingue(etiqueta)}</dt>
            <dd className="text-sm text-texto">{valor}</dd>
          </div>
        ))}
      </dl>

      <div>
        <dt className="text-sm text-texto-tenue">{bilingue(t('cierre.accionInmediata'))}</dt>
        <dd className="whitespace-pre-line text-sm text-texto">
          {cierre.accion_inmediata}
        </dd>
      </div>

      {cierre.accion_pendiente && (
        <div className="rounded-md border border-alerta bg-alerta-suave px-3 py-2">
          <dt className="text-sm font-medium text-alerta">
            {bilingue(t('cierre.accionPendiente'))}
          </dt>
          <dd className="whitespace-pre-line text-sm text-texto-suave">
            {cierre.accion_pendiente}
          </dd>
        </div>
      )}

      {cierre.fotos.length > 0 && (
        <div className="flex flex-col gap-2">
          <span className="text-sm text-texto-tenue">{bilingue(t('cierre.verificacion'))}</span>
          <ul className="flex flex-wrap gap-2">
            {cierre.fotos.map((id, indice) => (
              <li key={id}>
                <a href={urlFotoControl(id)} target="_blank" rel="noreferrer">
                  {/* eslint-disable-next-line @next/next/no-img-element -- la
                      sirve la API con la cookie de sesión. */}
                  <img
                    src={urlFotoControl(id)}
                    alt={t('fotos.numero', { numero: indice + 1 })}
                    className="h-20 w-20 rounded-md border border-borde object-cover"
                  />
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}