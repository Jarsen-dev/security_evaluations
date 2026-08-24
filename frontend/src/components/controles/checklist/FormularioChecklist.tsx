'use client';

import { useState } from 'react';

import { CampoFotos } from '@/components/controles/CampoFotos';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Textarea } from '@/components/ui/Textarea';
import { useTraduccion } from '@/lib/i18n';
import type { CatalogoChecklist, ValorChecklist } from '@/lib/types';
import { cn } from '@/lib/utils';

interface FormularioChecklistProps {
  catalogo: CatalogoChecklist;
  fecha: string;
  onGuardar: (datos: {
    puntos: Array<{ orden: number; valor: ValorChecklist; observaciones: string }>;
    fotos: Record<number, File[]>;
  }) => Promise<void>;
  guardando: boolean;
  onError: (mensaje: string) => void;
}

interface EstadoPunto {
  valor: ValorChecklist | null;
  observaciones: string;
  fotos: File[];
}

/** Clases del botón elegido. El NO OK resalta: es el hallazgo. */
const SELECCIONADO: Record<ValorChecklist, string> = {
  ok: 'border-exito bg-exito-suave text-exito',
  no_ok: 'border-error bg-error-suave text-error',
};

const VACIO: EstadoPunto = { valor: null, observaciones: '', fotos: [] };

export function FormularioChecklist({
  catalogo,
  fecha,
  onGuardar,
  guardando,
  onError,
}: FormularioChecklistProps) {
  const t = useTraduccion();
  const [estado, setEstado] = useState<Record<number, EstadoPunto>>({});

  function actualizar(orden: number, cambios: Partial<EstadoPunto>) {
    setEstado((previo) => ({
      ...previo,
      [orden]: { ...(previo[orden] ?? VACIO), ...cambios },
    }));
  }

  function responder(orden: number, valor: ValorChecklist) {
    // Al volver a OK se descartan observaciones y fotos: ya no explican nada
    // y el servidor rechaza fotos sobre un punto en OK.
    actualizar(
      orden,
      valor === 'ok'
        ? { valor, observaciones: '', fotos: [] }
        : { valor },
    );
  }

  const contestados = catalogo.puntos.filter(
    (punto) => estado[punto.orden]?.valor != null,
  ).length;

  const faltanPuntos = catalogo.puntos.length - contestados;

  const sinObservaciones = catalogo.puntos.filter((punto) => {
    const actual = estado[punto.orden];
    return actual?.valor === 'no_ok' && actual.observaciones.trim() === '';
  }).length;

  const sinFotos = catalogo.puntos.filter((punto) => {
    const actual = estado[punto.orden];
    return actual?.valor === 'no_ok' && actual.fotos.length === 0;
  }).length;

  const puedeGuardar =
    faltanPuntos === 0 && sinObservaciones === 0 && sinFotos === 0;

  async function guardar() {
    if (!puedeGuardar) {
      return;
    }

    const puntos: Array<{
      orden: number;
      valor: ValorChecklist;
      observaciones: string;
    }> = [];
    const fotos: Record<number, File[]> = {};

    for (const punto of catalogo.puntos) {
      const actual = estado[punto.orden];

      // `puedeGuardar` ya lo garantizó; esto es para que el compilador lo sepa.
      if (actual?.valor == null) {
        return;
      }

      puntos.push({
        orden: punto.orden,
        valor: actual.valor,
        observaciones: actual.observaciones.trim(),
      });

      if (actual.fotos.length > 0) {
        fotos[punto.orden] = actual.fotos;
      }
    }

    try {
      await onGuardar({ puntos, fotos });
    } catch {
      // El panel ya avisó del error; se conserva lo capturado.
      return;
    }

    setEstado({});
  }

  return (
    <Card className="flex flex-col gap-4">
      <div>
        <h2 className="text-base font-semibold text-texto">
          {t('checklist.registroDelDia')}
        </h2>
        <p className="mt-1 text-sm text-texto-suave">
          {catalogo.subtitulo ?? t('checklist.descripcion')}
        </p>
      </div>

      {catalogo.puntos.map((punto) => {
        const actual = estado[punto.orden];

        return (
          <div
            key={punto.orden}
            className="flex flex-col gap-3 border-t border-borde pt-4 first:border-t-0 first:pt-0"
          >
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm font-medium text-texto">{punto.etiqueta}</p>

              <div
                role="radiogroup"
                aria-label={punto.etiqueta}
                className="flex shrink-0 gap-2"
              >
                {(['ok', 'no_ok'] as const).map((valor) => {
                  const activa = actual?.valor === valor;

                  return (
                    <button
                      key={valor}
                      type="button"
                      role="radio"
                      aria-checked={activa}
                      onClick={() => responder(punto.orden, valor)}
                      disabled={guardando}
                      className={cn(
                        'h-tactil w-24 rounded-md border text-sm font-semibold transition-colors',
                        'disabled:cursor-not-allowed disabled:opacity-50',
                        activa
                          ? SELECCIONADO[valor]
                          : 'border-borde text-texto-suave hover:border-borde-fuerte hover:text-texto',
                      )}
                    >
                      {valor === 'ok' ? t('checklist.ok') : t('checklist.noOk')}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Observaciones y evidencia solo en NO OK, y ahí son obligatorias. */}
            {actual?.valor === 'no_ok' && (
              <div className="flex flex-col gap-3 rounded-md border border-error bg-error-suave/40 p-4">
                <Textarea
                  etiqueta={t('comun.observaciones')}
                  name={`observaciones-${punto.orden}`}
                  value={actual.observaciones}
                  placeholder={t('checklist.observacionesPlaceholder')}
                  onChange={(evento) =>
                    actualizar(punto.orden, { observaciones: evento.target.value })
                  }
                  disabled={guardando}
                  error={
                    actual.observaciones.trim() === ''
                      ? t('comun.obligatorio')
                      : undefined
                  }
                />

                <CampoFotos
                  id={`fotos-${catalogo.clave}-${punto.orden}`}
                  fotos={actual.fotos}
                  onCambiar={(fotos) => actualizar(punto.orden, { fotos })}
                  onError={onError}
                  maximo={catalogo.max_fotos}
                  deshabilitado={guardando}
                />

                {actual.fotos.length === 0 && (
                  <p role="alert" className="text-sm text-error">
                    {t('checklist.faltaFoto')}
                  </p>
                )}
              </div>
            )}
          </div>
        );
      })}

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-borde pt-4">
        <p className="text-sm text-texto-tenue">
          {faltanPuntos > 0
            ? t('checklist.faltanPuntos', { total: faltanPuntos })
            : sinObservaciones > 0
              ? t('checklist.faltanObservaciones', { total: sinObservaciones })
              : sinFotos > 0
                ? t('checklist.faltanFotos', { total: sinFotos })
                : `${t('comun.fecha')}: ${fecha}`}
        </p>

        <Button
          tamano="lg"
          onClick={() => void guardar()}
          disabled={!puedeGuardar}
          cargando={guardando}
        >
          {t('checklist.confirmar')}
        </Button>
      </div>
    </Card>
  );
}
