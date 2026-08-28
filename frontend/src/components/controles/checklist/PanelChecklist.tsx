'use client';

import { useCallback, useEffect, useState } from 'react';

import { ModalCierreHallazgo } from '@/components/controles/ModalCierreHallazgo';
import { ModalDetalleRegistro } from '@/components/controles/ModalDetalleRegistro';
import { FormularioChecklist } from '@/components/controles/checklist/FormularioChecklist';
import { TablaChecklist } from '@/components/controles/checklist/TablaChecklist';
import { Button } from '@/components/ui/Button';
import { DialogoConfirmacion } from '@/components/ui/DialogoConfirmacion';
import { useToast } from '@/components/ui/Toast';
import {
  ErrorDeApi,
  descargarExcelChecklist,
  descargarExcelInspeccion,
  eliminarRegistroChecklist,
  listarChecklist,
  listarIncidencias,
  obtenerCatalogoChecklist,
  registrarChecklist,
} from '@/lib/api';
import { useIdioma } from '@/lib/i18n';
import type { CatalogoChecklist, RegistroChecklist, ValorChecklist } from '@/lib/types';
import { fechaDeHoy, formatearFechaIso, rangoDelMes } from '@/lib/utils';

/**
 * Pestaña de un control de OK / NO OK.
 *
 * El mismo panel sirve a los tres: la lista de puntos, el título y el tope de
 * fotos salen del catálogo que entrega la API.
 */
export function PanelChecklist({ control }: { control: string }) {
  const { t, locale } = useIdioma();
  const { mostrarToast } = useToast();

  const [catalogo, setCatalogo] = useState<CatalogoChecklist | null>(null);
  const [registros, setRegistros] = useState<RegistroChecklist[]>([]);
  const [mes, setMes] = useState(() => fechaDeHoy().slice(0, 7));
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [descargando, setDescargando] = useState(false);
  const [errorCarga, setErrorCarga] = useState('');
  const [porEliminar, setPorEliminar] = useState<RegistroChecklist | null>(null);
  // Qué hojas ya tienen cierre, para pintar el botón de la columna.
  const [cerrados, setCerrados] = useState<ReadonlySet<string>>(new Set());
  const [detalleId, setDetalleId] = useState<string | null>(null);
  const [cierreId, setCierreId] = useState<string | null>(null);
  const [eliminando, setEliminando] = useState(false);
  const [descargandoId, setDescargandoId] = useState<string | null>(null);

  const hoy = fechaDeHoy();

  const cargar = useCallback(async () => {
    const { desde, hasta } = rangoDelMes(`${mes}-01`);

    try {
      const [lista, incidencias] = await Promise.all([
        listarChecklist(control, desde, hasta),
        // Una sola llamada para todo el mes: preguntar el cierre por renglón
        // serían 31 peticiones.
        listarIncidencias({ desde, hasta, control, estado: 'cerrado' }),
      ]);
      setRegistros(lista);
      setCerrados(new Set(incidencias.map((incidencia) => incidencia.registro_id)));
      setErrorCarga('');
    } catch (error) {
      setErrorCarga(
        error instanceof ErrorDeApi ? error.message : t('comun.errorGenerico'),
      );
    } finally {
      setCargando(false);
    }
  }, [control, mes, t]);

  useEffect(() => {
    let cancelado = false;

    // El catálogo se pide por control: al cambiar de pestaña hay que recargarlo.
    //
    // CUIDADO: esto desmonta <FormularioChecklist> y con él se va TODO lo que
    // el usuario lleve capturado —puntos, observaciones y fotos aún sin
    // subir—. Este efecto solo debe depender de cosas que cambien al cambiar
    // de control; `t` está aquí porque lo pide exhaustive-deps, y es inerte
    // porque el proveedor la mantiene estable (ver `lib/i18n/index.tsx`).
    setCatalogo(null);

    obtenerCatalogoChecklist(control)
      .then((datos) => {
        if (!cancelado) {
          setCatalogo(datos);
        }
      })
      .catch((error: unknown) => {
        if (!cancelado) {
          setErrorCarga(
            error instanceof ErrorDeApi ? error.message : t('comun.errorGenerico'),
          );
        }
      });

    return () => {
      cancelado = true;
    };
  }, [control, t]);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  async function guardar(datos: {
    puntos: Array<{
      orden: number;
      valor: ValorChecklist;
      observaciones: string;
      medicion?: string;
    }>;
    fotos: Record<number, File[]>;
    encabezado: Record<string, string>;
    secciones: Record<string, Record<string, string>>;
  }) {
    setGuardando(true);

    try {
      await registrarChecklist(control, { fecha: hoy, ...datos });
      await cargar();
      mostrarToast(t('checklist.guardado'), 'exito');
    } catch (error) {
      mostrarToast(
        error instanceof ErrorDeApi ? error.message : t('comun.errorGenerico'),
        'error',
      );
      // Se relanza para que el formulario no borre lo capturado.
      throw error;
    } finally {
      setGuardando(false);
    }
  }

  async function eliminar() {
    if (porEliminar === null) {
      return;
    }

    setEliminando(true);

    try {
      await eliminarRegistroChecklist(control, porEliminar.id);
      await cargar();
      mostrarToast(t('checklist.eliminado'), 'exito');
      setPorEliminar(null);
    } catch (error) {
      mostrarToast(
        error instanceof ErrorDeApi ? error.message : t('comun.errorGenerico'),
        'error',
      );
    } finally {
      setEliminando(false);
    }
  }

  /** Excel de una inspección suelta, con el formato de su hoja. */
  async function descargarInspeccion(registro: RegistroChecklist) {
    setDescargandoId(registro.id);

    try {
      await descargarExcelInspeccion(control, registro.id);
    } catch (error) {
      mostrarToast(
        error instanceof ErrorDeApi ? error.message : t('comun.errorGenerico'),
        'error',
      );
    } finally {
      setDescargandoId(null);
    }
  }

  async function descargar() {
    const { desde, hasta } = rangoDelMes(`${mes}-01`);
    setDescargando(true);

    try {
      await descargarExcelChecklist(control, desde, hasta);
    } catch (error) {
      mostrarToast(
        error instanceof ErrorDeApi ? error.message : t('comun.errorGenerico'),
        'error',
      );
    } finally {
      setDescargando(false);
    }
  }

  // En los formatos por inspección un día admite varias hojas —una por turno,
  // o una por tablero—, así que el aviso de "ya capturado" no aplica.
  const yaRegistrado =
    catalogo !== null &&
    !catalogo.por_inspeccion &&
    registros.some((registro) => registro.fecha === hoy);

  return (
    <div className="flex flex-col gap-6">
      {errorCarga && (
        <p
          role="alert"
          className="rounded-md border border-error bg-error-suave px-3 py-2 text-sm text-error"
        >
          {errorCarga}
        </p>
      )}

      {catalogo !== null &&
        (yaRegistrado ? (
          <div className="rounded-tarjeta border border-borde bg-fondo-elevado px-5 py-6">
            <p className="text-sm font-medium text-texto">
              {t('checklist.yaRegistrado', { fecha: formatearFechaIso(hoy, locale) })}
            </p>
            <p className="mt-1 text-sm text-texto-suave">
              {t('checklist.eliminarRegistro')}
            </p>
          </div>
        ) : (
          <FormularioChecklist
            catalogo={catalogo}
            fecha={formatearFechaIso(hoy, locale)}
            onGuardar={guardar}
            guardando={guardando}
            onError={(mensaje) => mostrarToast(mensaje, 'error')}
          />
        ))}

      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-col gap-1.5">
          <label
            htmlFor={`mes-${control}`}
            className="text-sm font-medium text-texto"
          >
            {t('comun.mes')}
          </label>
          <input
            id={`mes-${control}`}
            type="month"
            value={mes}
            onChange={(evento) => setMes(evento.target.value)}
            className="h-10 rounded-md border border-borde bg-fondo px-3 text-sm text-texto focus:border-primario"
          />
        </div>

        {/* El resumen mensual solo tiene sentido en las rejillas; los
            formatos por inspección se descargan hoja por hoja. */}
        {catalogo !== null && !catalogo.por_inspeccion && (
          <Button
            variante="secundario"
            onClick={() => void descargar()}
            cargando={descargando}
            disabled={registros.length === 0}
          >
            {t('comun.descargarExcel')}
          </Button>
        )}
      </div>

      <div className="flex flex-col gap-3">
        <h3 className="text-base font-semibold text-texto">
          {t('checklist.historial')}
        </h3>

        {cargando || catalogo === null ? (
          <p className="text-sm text-texto-suave">{t('comun.cargando')}</p>
        ) : (
          <TablaChecklist
            catalogo={catalogo}
            registros={registros}
            onEliminar={setPorEliminar}
            onVerDetalle={(registro) => setDetalleId(registro.id)}
            onCerrarHallazgo={(registro) => setCierreId(registro.id)}
            cerrados={cerrados}
            onDescargar={
              catalogo.por_inspeccion
                ? (registro) => void descargarInspeccion(registro)
                : undefined
            }
            descargandoId={descargandoId}
          />
        )}
      </div>

      <ModalDetalleRegistro
        abierto={detalleId !== null}
        control={control}
        registroId={detalleId}
        onCerrar={() => setDetalleId(null)}
        onError={(mensaje) => mostrarToast(mensaje, 'error')}
      />

      <ModalCierreHallazgo
        abierto={cierreId !== null}
        control={control}
        registroId={cierreId}
        onCerrar={() => setCierreId(null)}
        onGuardado={(mensaje) => {
          mostrarToast(mensaje, 'exito');
          void cargar();
        }}
        onError={(mensaje) => mostrarToast(mensaje, 'error')}
      />

      <DialogoConfirmacion
        abierto={porEliminar !== null}
        titulo={t('checklist.confirmarEliminar', {
          fecha: porEliminar ? formatearFechaIso(porEliminar.fecha, locale) : '',
        })}
        mensaje={t('checklist.confirmarEliminarDetalle')}
        procesando={eliminando}
        onConfirmar={() => void eliminar()}
        onCancelar={() => setPorEliminar(null)}
      />
    </div>
  );
}
