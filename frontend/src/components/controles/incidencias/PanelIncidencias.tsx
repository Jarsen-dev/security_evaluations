'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { ModalDetalleRegistro } from '@/components/controles/ModalDetalleRegistro';
import { TablaIncidencias } from '@/components/controles/incidencias/TablaIncidencias';
import { Button } from '@/components/ui/Button';
import { useToast } from '@/components/ui/Toast';
import { ErrorDeApi, descargarExcelIncidencias, listarIncidencias } from '@/lib/api';
import { bilingue, unaLinea, useTraduccion } from '@/lib/i18n';
import type { EstadoIncidencia, Incidencia } from '@/lib/types';
import { fechaDeHoy, rangoDelMes } from '@/lib/utils';

/** Los controles que pueden tener hallazgos. Pláticas no es una inspección. */
const CONTROLES = [
  'sqp',
  'rayser',
  'almacen_rp',
  'recorridos',
  'muro',
  'silos',
  'tableros',
] as const;

const CLASES_CAMPO =
  'h-10 rounded-md border border-borde bg-fondo px-3 text-sm text-texto focus:border-primario';

/**
 * Todo lo que salió mal en los controles, junto.
 *
 * El arranque es el mes en curso y no solo el día: en planta se revisa "qué
 * traigo pendiente", y un hallazgo del lunes que sigue abierto el jueves es
 * justo lo que no debe desaparecer de la vista.
 */
export function PanelIncidencias() {
  const t = useTraduccion();
  const { mostrarToast } = useToast();

  const mesActual = rangoDelMes(fechaDeHoy());

  const [desde, setDesde] = useState(mesActual.desde);
  const [hasta, setHasta] = useState(mesActual.hasta);
  const [control, setControl] = useState('');
  const [estado, setEstado] = useState<'' | EstadoIncidencia>('');

  const [incidencias, setIncidencias] = useState<Incidencia[]>([]);
  const [cargando, setCargando] = useState(true);
  const [descargando, setDescargando] = useState(false);
  const [errorCarga, setErrorCarga] = useState('');
  const [detalle, setDetalle] = useState<Incidencia | null>(null);

  // Cancela la petición anterior cuando los filtros cambian rápido.
  const peticion = useRef<AbortController | null>(null);

  const filtros = useCallback(
    () => ({
      desde,
      hasta,
      ...(control ? { control } : {}),
      ...(estado ? { estado } : {}),
    }),
    [desde, hasta, control, estado],
  );

  const cargar = useCallback(async () => {
    peticion.current?.abort();
    const controlador = new AbortController();
    peticion.current = controlador;

    setCargando(true);

    try {
      setIncidencias(await listarIncidencias(filtros(), controlador.signal));
      setErrorCarga('');
    } catch (error) {
      // Un aborto no es un fallo: es que llegó un filtro más nuevo.
      if (controlador.signal.aborted) {
        return;
      }
      setErrorCarga(
        error instanceof ErrorDeApi ? error.message : t('comun.errorGenerico'),
      );
    } finally {
      if (!controlador.signal.aborted) {
        setCargando(false);
      }
    }
  }, [filtros, t]);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  async function descargar() {
    setDescargando(true);

    try {
      await descargarExcelIncidencias(filtros());
    } catch (error) {
      mostrarToast(
        error instanceof ErrorDeApi ? error.message : t('comun.errorGenerico'),
        'error',
      );
    } finally {
      setDescargando(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-base font-semibold text-texto">
          {bilingue(t('incidencias.titulo'))}
        </h2>
        <p className="mt-1 text-sm text-texto-suave">
          {bilingue(t('incidencias.descripcion'))}
        </p>
      </div>

      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1.5">
            <label htmlFor="incidencias-desde" className="text-sm font-medium text-texto">
              {bilingue(t('comun.desde'))}
            </label>
            <input
              id="incidencias-desde"
              type="date"
              value={desde}
              onChange={(evento) => setDesde(evento.target.value)}
              className={CLASES_CAMPO}
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="incidencias-hasta" className="text-sm font-medium text-texto">
              {bilingue(t('comun.hasta'))}
            </label>
            <input
              id="incidencias-hasta"
              type="date"
              value={hasta}
              onChange={(evento) => setHasta(evento.target.value)}
              className={CLASES_CAMPO}
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label
              htmlFor="incidencias-control"
              className="text-sm font-medium text-texto"
            >
              {bilingue(t('incidencias.control'))}
            </label>
            <select
              id="incidencias-control"
              value={control}
              onChange={(evento) => setControl(evento.target.value)}
              className={CLASES_CAMPO}
            >
              <option value="">{unaLinea(t('incidencias.todosLosControles'))}</option>
              {CONTROLES.map((clave) => (
                <option key={clave} value={clave}>
                  {unaLinea(t(NOMBRES[clave]))}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1.5">
            <label
              htmlFor="incidencias-estado"
              className="text-sm font-medium text-texto"
            >
              {bilingue(t('incidencias.estado'))}
            </label>
            <select
              id="incidencias-estado"
              value={estado}
              onChange={(evento) =>
                setEstado(evento.target.value as '' | EstadoIncidencia)
              }
              className={CLASES_CAMPO}
            >
              <option value="">{unaLinea(t('incidencias.todosLosEstados'))}</option>
              <option value="pendiente">{unaLinea(t('cierre.pendiente'))}</option>
              <option value="cerrado">{unaLinea(t('cierre.cerrado'))}</option>
            </select>
          </div>
        </div>

        <Button
          variante="secundario"
          onClick={() => void descargar()}
          cargando={descargando}
          disabled={incidencias.length === 0}
        >
          {bilingue(t('comun.descargarExcel'))}
        </Button>
      </div>

      {errorCarga && (
        <p
          role="alert"
          className="rounded-md border border-error bg-error-suave px-3 py-2 text-sm text-error"
        >
          {errorCarga}
        </p>
      )}

      {cargando ? (
        <p className="text-sm text-texto-suave">{bilingue(t('comun.cargando'))}</p>
      ) : (
        <TablaIncidencias incidencias={incidencias} onVerDetalle={setDetalle} />
      )}

      <ModalDetalleRegistro
        abierto={detalle !== null}
        control={detalle?.control ?? ''}
        registroId={detalle?.registro_id ?? null}
        onCerrar={() => setDetalle(null)}
        onError={(mensaje) => mostrarToast(mensaje, 'error')}
      />
    </div>
  );
}

/** Rótulo de cada control en el filtro; los mismos que la barra de pestañas. */
const NOMBRES = {
  sqp: 'controles.sqp',
  rayser: 'controles.rayser',
  almacen_rp: 'controles.almacenRp',
  recorridos: 'controles.recorridos',
  muro: 'controles.muro',
  silos: 'controles.silos',
  tableros: 'controles.tableros',
} as const;
