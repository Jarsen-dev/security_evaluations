'use client';

import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { bilingue, unaLinea, useTraduccion } from '@/lib/i18n';
import { idUnico } from '@/lib/navegador';
import { cn } from '@/lib/utils';
import type { Insumo } from '@/lib/types';

/** Un documento en edición, con sus partidas. */
export interface Documento {
  idLocal: string;
  proveedor: string;
  folio: string;
  fecha: string;
  tipo_documento: string;
  tipo_conocido: boolean;
  ocr_ok: boolean;
  ocr_raw: Record<string, unknown> | null;
  /** Rutas que devolvió la IA: `"fecha"`, `"items[0].cantidad"`. */
  advertencias: string[];
  nuevoFormato: string;
  items: PartidaBorrador[];
}

export interface PartidaBorrador {
  idLocal: string;
  codigo: string;
  cantidad: string;
  /** Lo que devolvió el catálogo al salir del campo de código. */
  insumo: Insumo | null;
  /** `true` cuando ya se consultó y no existe. */
  noRegistrado: boolean;
}

/**
 * Un campo que la IA no pudo leer se pinta en ámbar.
 *
 * El token se llama `alerta` y ya significa exactamente esto en el panel
 * ("falta capturar"): es el mismo que usa el formulario de checklist. `Input`
 * deja ganar a `className`, así que basta pasárselo.
 */
function clasesAmbar(resaltado: boolean): string | undefined {
  return resaltado ? 'border-alerta' : undefined;
}

interface BloqueDocumentoProps {
  documento: Documento;
  /** Número que se muestra; solo se pinta si hay más de uno. */
  numero: number;
  total: number;
  onCambiar: (documento: Documento) => void;
  onQuitar: () => void;
  onBuscarCodigo: (codigo: string) => Promise<Insumo | null>;
  errores: Record<string, string>;
}

export function BloqueDocumento({
  documento,
  numero,
  total,
  onCambiar,
  onQuitar,
  onBuscarCodigo,
  errores,
}: BloqueDocumentoProps) {
  const t = useTraduccion();

  // Si la IA no leyó nada, TODO el formulario va en ámbar: no hay un campo
  // concreto que culpar, se capturó a mano de principio a fin.
  const todoAmbar = !documento.ocr_ok;
  const falta = (ruta: string) => todoAmbar || documento.advertencias.includes(ruta);

  function actualizar(cambios: Partial<Documento>) {
    onCambiar({ ...documento, ...cambios });
  }

  function actualizarPartida(idLocal: string, cambios: Partial<PartidaBorrador>) {
    actualizar({
      items: documento.items.map((partida) =>
        partida.idLocal === idLocal ? { ...partida, ...cambios } : partida,
      ),
    });
  }

  async function resolverCodigo(partida: PartidaBorrador) {
    const codigo = partida.codigo.trim();
    if (codigo === '') {
      actualizarPartida(partida.idLocal, { insumo: null, noRegistrado: false });
      return;
    }

    const insumo = await onBuscarCodigo(codigo);
    actualizarPartida(partida.idLocal, { insumo, noRegistrado: insumo === null });
  }

  return (
    <section className="flex flex-col gap-4 rounded-tarjeta border border-borde bg-fondo-elevado p-5">
      {total > 1 && (
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-texto">
            {bilingue(t('recepciones.documento', { numero }))}
          </h3>
          <Button variante="fantasma" tamano="sm" onClick={onQuitar}>
            {bilingue(t('recepciones.quitarDocumento'))}
          </Button>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <Input
            name={`proveedor-${documento.idLocal}`}
            etiqueta={t('recepciones.proveedor')}
            value={documento.proveedor}
            className={clasesAmbar(falta('proveedor'))}
            placeholder={falta('proveedor') ? unaLinea(t('recepciones.sinLeer')) : undefined}
            autoComplete="off"
            onChange={(evento) => actualizar({ proveedor: evento.target.value })}
          />
        </div>

        <Input
          name={`folio-${documento.idLocal}`}
          etiqueta={t('recepciones.folio')}
          value={documento.folio}
          className={clasesAmbar(falta('folio'))}
          placeholder={falta('folio') ? unaLinea(t('recepciones.sinLeer')) : undefined}
          autoComplete="off"
          onChange={(evento) => actualizar({ folio: evento.target.value })}
        />

        <Input
          name={`fecha-${documento.idLocal}`}
          etiqueta={t('recepciones.fecha')}
          type="date"
          value={documento.fecha}
          className={clasesAmbar(falta('fecha'))}
          onChange={(evento) => actualizar({ fecha: evento.target.value })}
        />
      </div>

      {/* El nombre del formato se pide SOLO si la IA sí leyó pero no reconoció
          el papel. Con la IA caída no sabemos de qué formato es, y registrar
          uno a ciegas ensuciaría el catálogo de plantillas. */}
      {documento.ocr_ok && !documento.tipo_conocido && (
        <div className="rounded-tarjeta border border-alerta bg-alerta-suave p-4">
          <p className="text-sm font-medium text-texto">
            {bilingue(t('recepciones.formatoNuevo'))}
          </p>
          <p className="mt-1 text-sm text-texto-suave">
            {bilingue(t('recepciones.formatoNuevoAyuda'))}
          </p>
          <div className="mt-3">
            <Input
              name={`formato-${documento.idLocal}`}
              etiqueta={t('recepciones.nombreFormato')}
              value={documento.nuevoFormato}
              error={errores.nuevoFormato}
              autoComplete="off"
              onChange={(evento) => actualizar({ nuevoFormato: evento.target.value })}
            />
          </div>
        </div>
      )}

      {documento.ocr_ok && documento.tipo_conocido && (
        <p className="text-sm text-texto-tenue">
          {bilingue(t('recepciones.formatoDetectado', { formato: documento.tipo_documento }))}
        </p>
      )}

      <div className="flex flex-col gap-3">
        <h4 className="text-sm font-medium text-texto">{bilingue(t('recepciones.partidas'))}</h4>

        {documento.items.map((partida, indice) => (
          <div
            key={partida.idLocal}
            className="grid gap-3 rounded-md border border-borde bg-fondo p-3 sm:grid-cols-[1fr_7rem_auto]"
          >
            <div>
              <Input
                name={`codigo-${partida.idLocal}`}
                etiqueta={t('recepciones.codigo')}
                value={partida.codigo}
                error={
                  partida.noRegistrado
                    ? t('recepciones.noRegistradoAyuda')
                    : errores[`items[${indice}].codigo`]
                }
                className={clasesAmbar(falta(`items[${indice}].codigo`))}
                placeholder={
                  falta(`items[${indice}].codigo`) ? unaLinea(t('recepciones.sinLeer')) : undefined
                }
                autoComplete="off"
                onChange={(evento) =>
                  actualizarPartida(partida.idLocal, {
                    codigo: evento.target.value,
                    // Al teclear se olvida lo que se sabía: el código cambió.
                    insumo: null,
                    noRegistrado: false,
                  })
                }
                onBlur={() => void resolverCodigo(partida)}
              />
              {partida.insumo !== null && (
                <p className="mt-1 text-xs text-texto-tenue">
                  {partida.insumo.descripcion ?? '—'} · {partida.insumo.unidad_medida}
                </p>
              )}
            </div>

            <Input
              name={`cantidad-${partida.idLocal}`}
              etiqueta={t('recepciones.cantidad')}
              inputMode="numeric"
              value={partida.cantidad}
              error={errores[`items[${indice}].cantidad`]}
              className={cn(clasesAmbar(falta(`items[${indice}].cantidad`)))}
              placeholder={
                falta(`items[${indice}].cantidad`) ? '—' : undefined
              }
              onChange={(evento) =>
                actualizarPartida(partida.idLocal, { cantidad: evento.target.value })
              }
            />

            <div className="flex items-end">
              <Button
                variante="fantasma"
                tamano="sm"
                disabled={documento.items.length === 1}
                onClick={() =>
                  actualizar({
                    items: documento.items.filter(
                      (otra) => otra.idLocal !== partida.idLocal,
                    ),
                  })
                }
              >
                {bilingue(t('recepciones.quitarPartida'))}
              </Button>
            </div>
          </div>
        ))}

        {errores.items !== undefined && (
          <p role="alert" className="text-sm text-error">
            {errores.items}
          </p>
        )}

        <div>
          <Button
            variante="secundario"
            tamano="sm"
            onClick={() =>
              actualizar({
                items: [
                  ...documento.items,
                  {
                    // idUnico y no crypto.randomUUID: por la IP de la LAN esa
                    // API ni siquiera existe (regla 5).
                    idLocal: idUnico(),
                    codigo: '',
                    cantidad: '',
                    insumo: null,
                    noRegistrado: false,
                  },
                ],
              })
            }
          >
            {bilingue(t('recepciones.agregarPartida'))}
          </Button>
        </div>
      </div>
    </section>
  );
}
