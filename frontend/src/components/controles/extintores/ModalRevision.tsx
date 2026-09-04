'use client';

import { useEffect, useState } from 'react';

import { CampoFotos } from '@/components/controles/CampoFotos';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { Textarea } from '@/components/ui/Textarea';
import { bilingue, useTraduccion } from '@/lib/i18n';
import type {
  FilaExtintor,
  PuntoControl,
  PuntoRevisionPayload,
  RevisionExtintor,
} from '@/lib/types';
import { cn } from '@/lib/utils';

type Valor = 'ok' | 'no_ok';

const SELECCIONADO: Record<Valor, string> = {
  ok: 'border-exito bg-exito-suave text-exito',
  no_ok: 'border-error bg-error-suave text-error',
};

interface Respuesta {
  valor: Valor | null;
  observaciones: string;
}

/**
 * La revisión diaria de un extintor: los doce puntos, uno por uno.
 *
 * Un punto INCONFORME exige observación **y** al menos una foto, y volver a
 * CONFORME limpia las dos: el servidor rechaza fotos sobre un punto sin
 * hallazgo, así que dejarlas puestas convertiría un cambio de opinión en un
 * error incomprensible al guardar.
 */
export function ModalRevision({
  fila,
  puntos,
  maxFotos,
  revision,
  guardando,
  onGuardar,
  onError,
  onCerrar,
}: {
  fila: FilaExtintor | null;
  puntos: PuntoControl[];
  maxFotos: number;
  /** La de hoy, cuando se está corrigiendo. */
  revision: RevisionExtintor | null;
  guardando: boolean;
  onGuardar: (
    puntos: PuntoRevisionPayload[],
    fotos: Record<number, File[]>,
    corrigiendo: boolean,
  ) => Promise<void>;
  onError: (mensaje: string) => void;
  onCerrar: () => void;
}) {
  const t = useTraduccion();

  const [respuestas, setRespuestas] = useState<Record<number, Respuesta>>({});
  const [fotos, setFotos] = useState<Record<number, File[]>>({});
  const [intentado, setIntentado] = useState(false);

  const corrigiendo = revision !== null;

  // Se recarga al abrir: el modal vive en el árbol y sin esto arrastraría lo
  // capturado del extintor anterior.
  useEffect(() => {
    if (fila === null) {
      return;
    }
    setIntentado(false);
    setFotos({});
    setRespuestas(
      revision === null
        ? {}
        : Object.fromEntries(
            revision.puntos.map((punto) => [
              punto.orden,
              { valor: punto.valor, observaciones: punto.observaciones ?? '' },
            ]),
          ),
    );
  }, [fila, revision]);

  function responder(orden: number, valor: Valor) {
    setRespuestas((previas) => ({
      ...previas,
      // Volver a CONFORME descarta la observación: el hallazgo dejó de existir.
      [orden]: { valor, observaciones: valor === 'ok' ? '' : (previas[orden]?.observaciones ?? '') },
    }));
    if (valor === 'ok') {
      setFotos((previas) => {
        const { [orden]: _descartada, ...resto } = previas;
        return resto;
      });
    }
  }

  const sinContestar = puntos.filter((p) => respuestas[p.orden]?.valor === undefined).length;
  const sinObservaciones = puntos.filter(
    (p) => respuestas[p.orden]?.valor === 'no_ok' && !respuestas[p.orden]?.observaciones.trim(),
  ).length;
  const sinFotos = puntos.filter(
    (p) => respuestas[p.orden]?.valor === 'no_ok' && (fotos[p.orden]?.length ?? 0) === 0,
  ).length;

  const puedeGuardar = sinContestar + sinObservaciones + sinFotos === 0;
  const anomalias = puntos.filter((p) => respuestas[p.orden]?.valor === 'no_ok').length;

  async function enviar() {
    setIntentado(true);
    if (!puedeGuardar) {
      return;
    }
    await onGuardar(
      puntos.map((punto) => ({
        orden: punto.orden,
        valor: respuestas[punto.orden]?.valor ?? 'ok',
        observaciones: respuestas[punto.orden]?.observaciones ?? '',
      })),
      fotos,
      corrigiendo,
    );
  }

  return (
    <Modal
      abierto={fila !== null}
      onCerrar={onCerrar}
      titulo={corrigiendo ? t('extintores.corregirRevision') : t('extintores.revisionTitulo')}
      ancho="lg"
      pie={
        <>
          <Button variante="fantasma" onClick={onCerrar} disabled={guardando}>
            {bilingue(t('comun.cancelar'))}
          </Button>
          <Button onClick={() => void enviar()} cargando={guardando} disabled={!puedeGuardar}>
            {bilingue(t('comun.guardar'))}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {fila !== null && (
          <p className="text-sm text-texto">
            {/* Datos del aparato: no se traducen. */}
            <span className="font-semibold">{fila.extintor.folio}</span>
            <span className="text-texto-suave">
              {' '}
              · {fila.extintor.tipo} · {fila.extintor.capacidad} · {fila.extintor.ubicacion}
            </span>
          </p>
        )}

        {/* El aviso que pidió el área: nada de marcar por inercia. */}
        <p className="rounded-md border border-alerta bg-alerta-suave px-3 py-2 text-sm text-alerta">
          {bilingue(t('extintores.revisionAviso'))}
        </p>

        <div className="flex flex-col gap-3">
          {puntos.map((punto) => {
            const respuesta = respuestas[punto.orden];
            const esHallazgo = respuesta?.valor === 'no_ok';
            const faltaObservacion =
              intentado && esHallazgo && !respuesta.observaciones.trim();
            const faltaFoto = intentado && esHallazgo && (fotos[punto.orden]?.length ?? 0) === 0;

            return (
              <div
                key={punto.orden}
                className={cn(
                  'rounded-tarjeta border p-3',
                  esHallazgo ? 'border-error' : 'border-borde',
                  intentado && respuesta?.valor === undefined && 'border-error',
                )}
              >
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <span className="text-sm text-texto">
                    <span className="text-texto-tenue">{punto.orden + 1}. </span>
                    {/* Del catálogo del backend: es dato, no interfaz. */}
                    {punto.etiqueta}
                  </span>

                  <div
                    role="radiogroup"
                    aria-label={punto.etiqueta}
                    className="flex gap-2"
                  >
                    {(['ok', 'no_ok'] as const).map((valor) => (
                      <button
                        key={valor}
                        type="button"
                        role="radio"
                        aria-checked={respuesta?.valor === valor}
                        onClick={() => responder(punto.orden, valor)}
                        className={cn(
                          'min-h-8 rounded-md border px-3 py-1 text-sm font-medium',
                          respuesta?.valor === valor
                            ? SELECCIONADO[valor]
                            : 'border-borde text-texto-suave hover:border-borde-fuerte',
                        )}
                      >
                        {bilingue(
                          t(valor === 'ok' ? 'checklist.conforme' : 'checklist.inconforme'),
                        )}
                      </button>
                    ))}
                  </div>
                </div>

                {esHallazgo && (
                  <div className="mt-3 flex flex-col gap-3">
                    <Textarea
                      etiqueta={t('comun.observaciones')}
                      value={respuesta.observaciones}
                      rows={2}
                      onChange={(evento) =>
                        setRespuestas((previas) => ({
                          ...previas,
                          [punto.orden]: {
                            valor: 'no_ok',
                            observaciones: evento.target.value,
                          },
                        }))
                      }
                      error={faltaObservacion ? t('comun.obligatorio') : undefined}
                    />

                    <CampoFotos
                      id={`fotos-extintor-${punto.orden}`}
                      fotos={fotos[punto.orden] ?? []}
                      onCambiar={(nuevas) =>
                        setFotos((previas) => ({ ...previas, [punto.orden]: nuevas }))
                      }
                      onError={onError}
                      maximo={maxFotos}
                      deshabilitado={guardando}
                    />
                    {faltaFoto && (
                      <p role="alert" className="text-sm text-error">
                        {bilingue(t('extintores.faltaFoto'))}
                      </p>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        <p className="text-sm text-texto-suave">
          {bilingue(
            t('extintores.resumenRevision', {
              contestados: puntos.length - sinContestar,
              total: puntos.length,
              anomalias,
            }),
          )}
        </p>
      </div>
    </Modal>
  );
}
