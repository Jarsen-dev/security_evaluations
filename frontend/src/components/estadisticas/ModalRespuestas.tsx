'use client';

import { useEffect, useState } from 'react';

import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { ErrorDeApi, obtenerDetalleIntento } from '@/lib/api';
import type { DetalleIntento } from '@/lib/types';
import { cn } from '@/lib/utils';

interface ModalRespuestasProps {
  /** Id del intento a mostrar; `null` mantiene el modal cerrado. */
  intentoId: string | null;
  onCerrar: () => void;
}

function formatearFecha(iso: string | null): string {
  if (iso === null) {
    return 'Sin finalizar';
  }
  return new Date(iso).toLocaleString('es-MX', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatearDuracion(segundos: number | null): string {
  if (segundos === null) {
    return '—';
  }
  return `${Math.floor(segundos / 60)}:${String(segundos % 60).padStart(2, '0')}`;
}

/** Muestra lo que contestó una persona, marcando aciertos y errores. */
export function ModalRespuestas({ intentoId, onCerrar }: ModalRespuestasProps) {
  const [detalle, setDetalle] = useState<DetalleIntento | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (intentoId === null) {
      return;
    }

    let cancelado = false;
    setCargando(true);
    setError('');
    setDetalle(null);

    obtenerDetalleIntento(intentoId)
      .then((datos) => {
        if (!cancelado) {
          setDetalle(datos);
        }
      })
      .catch((problema) => {
        if (!cancelado) {
          setError(
            problema instanceof ErrorDeApi
              ? problema.message
              : 'No se pudieron cargar las respuestas.',
          );
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
  }, [intentoId]);

  return (
    <Modal
      abierto={intentoId !== null}
      onCerrar={onCerrar}
      ancho="lg"
      titulo={detalle ? detalle.nombre : 'Respuestas del intento'}
      descripcion={
        detalle
          ? `${detalle.numero_empleado} · ${detalle.area_label} · ${detalle.cuestionario_nombre}`
          : undefined
      }
      pie={
        <Button variante="fantasma" onClick={onCerrar}>
          Cerrar
        </Button>
      }
    >
      {cargando && <p className="py-8 text-center text-texto-suave">Cargando respuestas…</p>}

      {error && (
        <p
          role="alert"
          className="rounded-md border border-error bg-error-suave px-3 py-2 text-sm text-error"
        >
          {error}
        </p>
      )}

      {detalle && (
        <div className="flex flex-col gap-5">
          {/* --- Resumen del intento --- */}
          <div className="grid grid-cols-2 gap-4 rounded-tarjeta border border-borde bg-fondo p-4 sm:grid-cols-4">
            <div>
              <p className="text-xs text-texto-tenue">Puntaje</p>
              <p
                className={cn(
                  'text-2xl font-semibold',
                  detalle.aprobado ? 'text-exito' : 'text-error',
                )}
              >
                {detalle.puntaje === null
                  ? '—'
                  : `${Number(detalle.puntaje).toFixed(0)}%`}
              </p>
            </div>

            <div>
              <p className="text-xs text-texto-tenue">Aciertos</p>
              <p className="text-2xl font-semibold text-texto">
                {detalle.correctas}
                <span className="text-base text-texto-tenue">
                  /{detalle.total_preguntas}
                </span>
              </p>
            </div>

            <div>
              <p className="text-xs text-texto-tenue">Duración</p>
              <p className="text-2xl font-semibold text-texto">
                {formatearDuracion(detalle.duracion_segundos)}
              </p>
            </div>

            <div>
              <p className="text-xs text-texto-tenue">Resultado</p>
              <div className="mt-1.5">
                <Badge tono={detalle.aprobado ? 'exito' : 'error'}>
                  {detalle.aprobado ? 'Aprobado' : 'No aprobado'}
                </Badge>
              </div>
            </div>
          </div>

          <p className="text-sm text-texto-tenue">
            Contestado el {formatearFecha(detalle.finalizado_at)} · umbral de
            aprobación {detalle.umbral_aprobacion}%
            {detalle.sin_responder > 0 &&
              ` · ${detalle.sin_responder} pregunta(s) sin responder`}
          </p>

          {/* --- Preguntas --- */}
          <ol className="flex flex-col gap-3">
            {detalle.preguntas.map((pregunta, indice) => (
              <li
                key={pregunta.pregunta_id}
                className={cn(
                  'rounded-tarjeta border p-4',
                  pregunta.acerto
                    ? 'border-exito/40 bg-exito-suave/30'
                    : 'border-error/40 bg-error-suave/30',
                )}
              >
                <div className="mb-3 flex items-start justify-between gap-3">
                  <p className="font-medium text-texto">
                    {indice + 1}. {pregunta.texto}
                  </p>

                  <Badge
                    tono={
                      pregunta.acerto ? 'exito' : pregunta.respondida ? 'error' : 'alerta'
                    }
                  >
                    {pregunta.acerto
                      ? 'Correcta'
                      : pregunta.respondida
                        ? 'Incorrecta'
                        : 'Sin responder'}
                  </Badge>
                </div>

                <ul className="flex flex-col gap-1.5">
                  {pregunta.opciones.map((opcion) => {
                    // Tres estados posibles por opción: la que eligió y era
                    // correcta, la que eligió y estaba mal, y la correcta que
                    // no eligió (para que se vea qué debió contestar).
                    const acierto = opcion.elegida && opcion.es_correcta;
                    const fallo = opcion.elegida && !opcion.es_correcta;
                    const correctaNoElegida = !opcion.elegida && opcion.es_correcta;

                    return (
                      <li
                        key={opcion.id}
                        className={cn(
                          'flex items-start gap-2 rounded-md px-3 py-2 text-sm',
                          acierto && 'bg-exito-suave font-medium text-exito',
                          fallo && 'bg-error-suave font-medium text-error',
                          correctaNoElegida && 'text-exito',
                          !opcion.elegida && !opcion.es_correcta && 'text-texto-suave',
                        )}
                      >
                        <span aria-hidden="true" className="w-4 shrink-0">
                          {acierto ? '✓' : fallo ? '✕' : correctaNoElegida ? '✓' : '·'}
                        </span>

                        <span className="flex-1">{opcion.texto}</span>

                        {opcion.elegida && (
                          <span className="shrink-0 text-xs uppercase tracking-wide">
                            Su respuesta
                          </span>
                        )}
                        {correctaNoElegida && (
                          <span className="shrink-0 text-xs uppercase tracking-wide">
                            Correcta
                          </span>
                        )}
                      </li>
                    );
                  })}
                </ul>
              </li>
            ))}
          </ol>
        </div>
      )}
    </Modal>
  );
}
