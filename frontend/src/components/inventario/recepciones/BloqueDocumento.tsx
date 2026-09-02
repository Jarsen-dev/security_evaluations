'use client';

import { Button } from '@/components/ui/Button';
import { Combobox } from '@/components/ui/Combobox';
import { Input } from '@/components/ui/Input';
import { bilingue, unaLinea, useIdioma } from '@/lib/i18n';
import { idUnico } from '@/lib/navegador';
import { cn } from '@/lib/utils';
import type { CandidatoInsumo } from '@/lib/types';

/** Un documento en edición, con sus partidas. */
export interface Documento {
  idLocal: string;
  proveedor: string;
  folio: string;
  fecha: string;
  tipo_documento: string;
  tipo_conocido: boolean;
  /** El nombre legible del formato; `tipo_documento` es el identificador. */
  tipoNombre: string;
  ocr_ok: boolean;
  ocr_raw: Record<string, unknown> | null;
  /** Rutas que devolvió la IA: `"fecha"`, `"items[0].cantidad"`. */
  advertencias: string[];
  nuevoFormato: string;
  items: PartidaBorrador[];
}

/**
 * Lo que devuelve la consulta de un código.
 *
 * Discriminado a propósito: con un simple `CandidatoInsumo[]` no hay forma de
 * distinguir "este código no existe" de "no se pudo preguntar", y confundir
 * las dos cosas marcaba en rojo códigos válidos cada vez que fallaba la red.
 */
export type ResultadoCodigo =
  | { estado: 'ok'; candidatos: CandidatoInsumo[] }
  | { estado: 'fallo' };

export interface PartidaBorrador {
  idLocal: string;
  codigo: string;
  cantidad: string;
  /** La descripción tal como la dice el papel; se teclea o la lee la IA. */
  descripcion: string;
  /** Todas las del código: un código ampara varios productos. */
  candidatos: CandidatoInsumo[];
  /** Cuál se eligió. `null` mientras nadie haya elegido. */
  insumoId: string | null;
  /** `true` cuando ya se consultó el código y no existe. */
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
  onBuscarCodigo: (codigo: string) => Promise<ResultadoCodigo>;
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
  const { t, locale } = useIdioma();

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
      actualizarPartida(partida.idLocal, {
        candidatos: [],
        insumoId: null,
        noRegistrado: false,
      });
      return;
    }

    const resultado = await onBuscarCodigo(codigo);

    // Si la consulta falló no se puede afirmar que el código no existe: eso
    // pintaba en rojo códigos perfectamente válidos cuando la red o el
    // permiso fallaban.
    if (resultado.estado === 'fallo') {
      actualizarPartida(partida.idLocal, { candidatos: [], noRegistrado: false });
      return;
    }

    const { candidatos } = resultado;
    actualizarPartida(partida.idLocal, {
      candidatos,
      noRegistrado: candidatos.length === 0,
      // Con una sola descripción no hay nada que elegir; con varias, la
      // elección previa solo vale si sigue siendo una de ellas.
      insumoId:
        candidatos.length === 1
          ? (candidatos[0]?.id ?? null)
          : candidatos.some((candidato) => candidato.id === partida.insumoId)
            ? partida.insumoId
            : null,
    });
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

      {/* Se anuncia el NOMBRE, no el identificador interno: nadie tiene por
          qué leer «mgpharma_remision» para saber que se reconoció su remisión.
          Y con su propio recuadro: en gris tenue pasaba desapercibido al lado
          de la tarjeta ámbar del formato no reconocido. */}
      {documento.ocr_ok && documento.tipo_conocido && (
        <p className="rounded-tarjeta border border-exito bg-exito-suave px-4 py-2 text-sm text-exito">
          {bilingue(
            t('recepciones.formatoDetectado', {
              formato: documento.tipoNombre || documento.tipo_documento,
            }),
          )}
        </p>
      )}

      <div className="flex flex-col gap-3">
        <h4 className="text-sm font-medium text-texto">{bilingue(t('recepciones.partidas'))}</h4>

        {documento.items.map((partida, indice) => {
          const elegido = partida.candidatos.find(
            (candidato) => candidato.id === partida.insumoId,
          );
          // Varias descripciones y ninguna elegida: es lo que bloquea el
          // guardado, y lo que se pinta en ámbar.
          const sinElegir = partida.candidatos.length > 1 && partida.insumoId === null;

          return (
          <div
            key={partida.idLocal}
            className="grid gap-3 rounded-md border border-borde bg-fondo p-3 sm:grid-cols-[12rem_1fr_7rem_auto]"
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
                    candidatos: [],
                    insumoId: null,
                    noRegistrado: false,
                  })
                }
                onBlur={() => void resolverCodigo(partida)}
              />
              {elegido !== undefined && (
                <p className="mt-1 text-xs text-texto-tenue">
                  {elegido.unidad_medida}
                  {' · '}
                  {t('recepciones.porCaja', { piezas: elegido.piezas_por_empaque })}
                </p>
              )}
            </div>

            <div>
              {/* Un código ampara varios productos y solo la descripción los
                  distingue. Se teclea lo que dice la remisión y se elige de la
                  lista; el servidor rechaza la partida sin elegir. */}
              <Combobox
                etiqueta={t('recepciones.descripcionItem')}
                opciones={partida.candidatos.map((candidato) => ({
                  valor: candidato.id,
                  etiqueta: candidato.descripcion,
                }))}
                valor={partida.insumoId}
                texto={partida.descripcion}
                vacio={t('recepciones.noRegistradoAyuda')}
                deshabilitado={partida.candidatos.length === 0}
                placeholder={
                  falta(`items[${indice}].descripcion`)
                    ? unaLinea(t('recepciones.sinLeer'))
                    : unaLinea(t('recepciones.elegirDescripcion'))
                }
                error={errores[`items[${indice}].insumo`]}
                ayuda={
                  sinElegir
                    ? unaLinea(
                        t('recepciones.variasDescripciones', {
                          total: partida.candidatos.length,
                        }),
                      )
                    : undefined
                }
                className={clasesAmbar(
                  sinElegir || falta(`items[${indice}].descripcion`),
                )}
                onTexto={(texto) =>
                  actualizarPartida(partida.idLocal, { descripcion: texto })
                }
                onElegir={(insumoId) => {
                  const candidato = partida.candidatos.find(
                    (otro) => otro.id === insumoId,
                  );
                  // Al elegir, el texto pasa a ser el del catálogo: es lo que
                  // el operador acaba de confirmar que recibió.
                  actualizarPartida(partida.idLocal, {
                    insumoId,
                    descripcion: candidato?.descripcion ?? partida.descripcion,
                  });
                }}
              />
            </div>

            <div>
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

              {/* Lo que se teclea son cajas y lo que entra al inventario son
                  piezas: la multiplicación se adelanta aquí para que el
                  operador vea el número antes de guardar, no después. */}
              {elegido !== undefined && /^\d+$/.test(partida.cantidad.trim()) && (
                <p className="mt-1 text-xs text-texto-tenue">
                  {t('recepciones.entranPiezas', {
                    piezas: (
                      Number(partida.cantidad) * elegido.piezas_por_empaque
                    ).toLocaleString(locale),
                  })}
                </p>
              )}
            </div>

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
          );
        })}

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
                    descripcion: '',
                    candidatos: [],
                    insumoId: null,
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
