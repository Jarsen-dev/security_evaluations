'use client';

import { useState } from 'react';

import { AvisoBorrador, BotonReiniciar } from '@/components/controles/AvisoBorrador';
import { CampoFotos } from '@/components/controles/CampoFotos';
import { CamposFormato } from '@/components/controles/checklist/CamposFormato';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Textarea } from '@/components/ui/Textarea';
import { useBorrador } from '@/hooks/useBorrador';
import { useIdioma } from '@/lib/i18n';
import { useSesion } from '@/lib/sesion';
import type {
  CampoFormato,
  CatalogoChecklist,
  PuntoControl,
  SeccionFormato,
  ValorChecklist,
} from '@/lib/types';
import { cn } from '@/lib/utils';

interface FormularioChecklistProps {
  catalogo: CatalogoChecklist;
  fecha: string;
  onGuardar: (datos: {
    puntos: Array<{
      orden: number;
      valor: ValorChecklist;
      observaciones: string;
      medicion?: string;
    }>;
    fotos: Record<number, File[]>;
    encabezado: Record<string, string>;
    secciones: Record<string, Record<string, string>>;
  }) => Promise<void>;
  guardando: boolean;
  onError: (mensaje: string) => void;
}

interface EstadoPunto {
  valor: ValorChecklist | null;
  observaciones: string;
  medicion: string;
  fotos: File[];
}

/** Clases del botón elegido. El hallazgo resalta en rojo. */
const SELECCIONADO: Record<ValorChecklist, string> = {
  ok: 'border-exito bg-exito-suave text-exito',
  no_ok: 'border-error bg-error-suave text-error',
};

const VACIO: EstadoPunto = { valor: null, observaciones: '', medicion: '', fotos: [] };

/** Campos de un grupo que quedaron vacíos siendo obligatorios. */
function faltantes(campos: CampoFormato[], valores: Record<string, string>): number {
  return campos.filter(
    (campo) => campo.obligatorio && (valores[campo.clave] ?? '').trim() === '',
  ).length;
}

export function FormularioChecklist({
  catalogo,
  fecha,
  onGuardar,
  guardando,
  onError,
}: FormularioChecklistProps) {
  const { t, idioma } = useIdioma();

  const [estado, setEstado] = useState<Record<number, EstadoPunto>>({});
  const [encabezado, setEncabezado] = useState<Record<string, string>>({});
  const [secciones, setSecciones] = useState<Record<string, Record<string, string>>>({});

  /** El formato es bilingüe: se muestra la línea del idioma del panel. */
  function texto(punto: PuntoControl): string {
    return idioma === 'ko' && punto.etiqueta_ko ? punto.etiqueta_ko : punto.etiqueta;
  }

  function tituloSeccion(seccion: SeccionFormato): string {
    return idioma === 'ko' && seccion.titulo_ko ? seccion.titulo_ko : seccion.titulo;
  }

  function actualizar(orden: number, cambios: Partial<EstadoPunto>) {
    setEstado((previo) => ({
      ...previo,
      [orden]: { ...(previo[orden] ?? VACIO), ...cambios },
    }));
  }

  function responder(orden: number, valor: ValorChecklist) {
    // Al volver al valor bueno se descartan observaciones y fotos: ya no
    // explican nada y el servidor rechaza fotos sobre un punto sin hallazgo.
    actualizar(
      orden,
      valor === 'ok' ? { valor, observaciones: '', fotos: [] } : { valor },
    );
  }

  function cambiarSeccion(seccion: string, clave: string, valor: string) {
    setSecciones((previo) => ({
      ...previo,
      [seccion]: { ...(previo[seccion] ?? {}), [clave]: valor },
    }));
  }

  const hayHallazgos = catalogo.puntos.some(
    (punto) => estado[punto.orden]?.valor === 'no_ok',
  );

  // El bloque de acción ante anomalía solo aparece cuando algo salió mal.
  const seccionesVisibles = catalogo.secciones.filter(
    (seccion) => !seccion.solo_con_hallazgos || hayHallazgos,
  );

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

  const sinMedicion = catalogo.puntos.filter(
    (punto) => punto.medicion && (estado[punto.orden]?.medicion ?? '').trim() === '',
  ).length;

  // Turno y hora de inspección los calcula el servicio al guardar (ver
  // `automatico` en el catálogo): no se piden aquí ni cuentan como
  // pendientes.
  const camposEncabezado = catalogo.encabezado.filter((campo) => !campo.automatico);

  const faltanEncabezado = faltantes(camposEncabezado, encabezado);
  const faltanSecciones = seccionesVisibles.reduce(
    (total, seccion) => total + faltantes(seccion.campos, secciones[seccion.clave] ?? {}),
    0,
  );

  // Lo capturado sobrevive a cambiar de pestaña, salir del panel o recargar.
  // Es la hoja donde más duele perderlo: hasta 30 puntos con fotos que solo
  // existen en memoria hasta que se confirma.
  const { usuario } = useSesion();
  const hayContenido =
    Object.keys(estado).length > 0 ||
    Object.values(encabezado).some((valor) => valor.trim() !== '') ||
    Object.values(secciones).some((campos) =>
      Object.values(campos).some((valor) => valor.trim() !== ''),
    );

  const borrador = useBorrador(
    usuario ? `${usuario.username}:checklist:${catalogo.clave}` : null,
    { estado, encabezado, secciones },
    hayContenido,
    (guardado) => {
      setEstado(guardado.estado);
      setEncabezado(guardado.encabezado);
      setSecciones(guardado.secciones);
    },
  );

  const puedeGuardar =
    faltanPuntos === 0 &&
    sinObservaciones === 0 &&
    sinFotos === 0 &&
    sinMedicion === 0 &&
    faltanEncabezado === 0 &&
    faltanSecciones === 0;

  async function guardar() {
    if (!puedeGuardar) {
      return;
    }

    const puntos: Array<{
      orden: number;
      valor: ValorChecklist;
      observaciones: string;
      medicion?: string;
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
        medicion: punto.medicion ? actual.medicion.trim() : undefined,
      });

      if (actual.fotos.length > 0) {
        fotos[punto.orden] = actual.fotos;
      }
    }

    // Solo viajan las secciones que estaban a la vista: mandar el bloque de
    // anomalía en un recorrido limpio guardaría campos que nadie llenó.
    const aEnviar = Object.fromEntries(
      seccionesVisibles.map((seccion) => [seccion.clave, secciones[seccion.clave] ?? {}]),
    );

    try {
      await onGuardar({ puntos, fotos, encabezado, secciones: aEnviar });
    } catch {
      // El panel ya avisó del error; se conserva lo capturado.
      return;
    }

    setEstado({});
    setSecciones({});
    // El encabezado se conserva: en tableros solo cambia el número entre una
    // inspección y la siguiente.
    borrador.descartar();
  }

  // Los puntos se agrupan por categoría cuando la hoja las trae.
  const grupos: Array<{ categoria: string | null; puntos: PuntoControl[] }> = [];
  for (const punto of catalogo.puntos) {
    const ultimo = grupos.at(-1);
    if (ultimo && ultimo.categoria === punto.categoria) {
      ultimo.puntos.push(punto);
    } else {
      grupos.push({ categoria: punto.categoria, puntos: [punto] });
    }
  }

  // Todas las hojas rotulan igual las dos respuestas. Antes unas decían
  // OK / NO OK y otras SÍ / NO; era una diferencia de rótulo, no de
  // significado, y el valor guardado sigue siendo el mismo.
  const etiquetaValor: Record<ValorChecklist, string> = {
    ok: t('checklist.conforme'),
    no_ok: t('checklist.inconforme'),
  };

  return (
    <div className="flex flex-col gap-4">
      <AvisoBorrador fecha={borrador.esDeOtroDia ? borrador.fecha : null} />

      {camposEncabezado.length > 0 && (
        <Card className="flex flex-col gap-4">
          <h2 className="text-base font-semibold text-texto">
            {t('checklist.encabezado')}
          </h2>
          <CamposFormato
            campos={camposEncabezado}
            valores={encabezado}
            onCambiar={(clave, valor) =>
              setEncabezado((previo) => ({ ...previo, [clave]: valor }))
            }
            deshabilitado={guardando}
            prefijo={`encabezado-${catalogo.clave}`}
          />
        </Card>
      )}

      <Card className="flex flex-col gap-4">
        <div>
          <h2 className="text-base font-semibold text-texto">
            {catalogo.por_inspeccion
              ? t('checklist.listaVerificacion')
              : t('checklist.registroDelDia')}
          </h2>
          <p className="mt-1 text-sm text-texto-suave">
            {catalogo.subtitulo ?? t('checklist.descripcion')}
          </p>
        </div>

        {/*
          La categoría NO sirve como clave: el catálogo repite algunas (por
          ejemplo "비상 / Emergencia") en grupos no contiguos del mismo
          control, y React descartaba uno de los dos. Se ancla al primer
          punto, que sí es único dentro del formato.
        */}
        {grupos.map((grupo, indice) => (
          <div
            key={grupo.puntos[0]?.orden ?? `grupo-${indice}`}
            className="flex flex-col gap-4"
          >
            {grupo.categoria && (
              <h3 className="border-t border-borde pt-4 text-sm font-semibold tracking-wide text-texto-suave">
                {grupo.categoria}
              </h3>
            )}

            {grupo.puntos.map((punto) => {
              const actual = estado[punto.orden];

              return (
                <div
                  key={punto.orden}
                  className={cn(
                    'flex flex-col gap-3',
                    grupo.categoria ? '' : 'border-t border-borde pt-4 first:border-t-0 first:pt-0',
                  )}
                >
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <p className="text-sm font-medium text-texto">
                      {catalogo.por_inspeccion && (
                        <span className="mr-2 text-texto-tenue">{punto.orden + 1}.</span>
                      )}
                      {texto(punto)}
                    </p>

                    <div className="flex shrink-0 items-center gap-2">
                      {punto.medicion && (
                        <input
                          aria-label={`${texto(punto)} — ${punto.medicion}`}
                          inputMode="decimal"
                          placeholder={punto.medicion}
                          value={actual?.medicion ?? ''}
                          onChange={(evento) =>
                            actualizar(punto.orden, { medicion: evento.target.value })
                          }
                          disabled={guardando}
                          className={cn(
                            'h-tactil w-28 rounded-md border bg-fondo px-3 text-sm text-texto',
                            'placeholder:text-texto-tenue disabled:cursor-not-allowed disabled:opacity-50',
                            (actual?.medicion ?? '').trim() === ''
                              ? 'border-alerta'
                              : 'border-borde focus:border-primario',
                          )}
                        />
                      )}

                      <div
                        role="radiogroup"
                        aria-label={texto(punto)}
                        className="flex gap-2"
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
                                'h-tactil w-32 rounded-md border text-sm font-semibold transition-colors',
                                'disabled:cursor-not-allowed disabled:opacity-50',
                                activa
                                  ? SELECCIONADO[valor]
                                  : 'border-borde text-texto-suave hover:border-borde-fuerte hover:text-texto',
                              )}
                            >
                              {etiquetaValor[valor]}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  </div>

                  {/* Observaciones y evidencia solo en el hallazgo, y ahí son
                      obligatorias. */}
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
          </div>
        ))}
      </Card>

      {seccionesVisibles.map((seccion) => (
        <Card key={seccion.clave} className="flex flex-col gap-4">
          <h2 className="text-base font-semibold text-texto">
            {tituloSeccion(seccion)}
          </h2>
          <CamposFormato
            campos={seccion.campos}
            valores={secciones[seccion.clave] ?? {}}
            onCambiar={(clave, valor) => cambiarSeccion(seccion.clave, clave, valor)}
            deshabilitado={guardando}
            prefijo={`${catalogo.clave}-${seccion.clave}`}
          />
        </Card>
      ))}

      {catalogo.nota && (
        <p className="rounded-md border border-alerta bg-alerta-suave px-4 py-3 text-sm text-texto-suave">
          {idioma === 'ko' && catalogo.nota_ko ? catalogo.nota_ko : catalogo.nota}
        </p>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-texto-tenue">
          {faltanEncabezado > 0
            ? t('checklist.faltanEncabezado', { total: faltanEncabezado })
            : faltanPuntos > 0
              ? t('checklist.faltanPuntos', { total: faltanPuntos })
              : sinMedicion > 0
                ? t('checklist.faltanMediciones', { total: sinMedicion })
                : sinObservaciones > 0
                  ? t('checklist.faltanObservaciones', { total: sinObservaciones })
                  : sinFotos > 0
                    ? t('checklist.faltanFotos', { total: sinFotos })
                    : faltanSecciones > 0
                      ? t('checklist.faltanSecciones', { total: faltanSecciones })
                      : `${t('comun.fecha')}: ${fecha}`}
        </p>

        <div className="flex flex-wrap items-center gap-3">
          <BotonReiniciar
            hayContenido={hayContenido}
            deshabilitado={guardando}
            onReiniciar={() => {
              setEstado({});
              setEncabezado({});
              setSecciones({});
              borrador.descartar();
            }}
          />

          <Button
            tamano="lg"
            onClick={() => void guardar()}
            disabled={!puedeGuardar}
            cargando={guardando}
          >
            {t('checklist.confirmar')}
          </Button>
        </div>
      </div>
    </div>
  );
}
