'use client';

import { useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useRef, useState } from 'react';

import { ModalCierreHallazgo } from '@/components/controles/ModalCierreHallazgo';
import { ModalEscanear } from '@/components/controles/extintores/ModalEscanear';
import { ModalExtintor } from '@/components/controles/extintores/ModalExtintor';
import { ModalQrExtintor } from '@/components/controles/extintores/ModalQrExtintor';
import { ModalRevision } from '@/components/controles/extintores/ModalRevision';
import { TablaExtintores } from '@/components/controles/extintores/TablaExtintores';
import { BotonIcono } from '@/components/ui/BotonIcono';
import { Button } from '@/components/ui/Button';
import { DialogoConfirmacion } from '@/components/ui/DialogoConfirmacion';
import { IconoCamara } from '@/components/ui/Iconos';
import { useToast } from '@/components/ui/Toast';
import {
  ErrorDeApi,
  actualizarExtintor,
  crearExtintor,
  descargarEtiquetasExtintores,
  descargarExcelExtintores,
  eliminarExtintor,
  guardarRevisionExtintor,
  listarExtintores,
  obtenerCatalogoExtintores,
  obtenerRevisionDeHoy,
} from '@/lib/api';
import { avisarCambioDeAvisos } from '@/lib/avisos';
import { bilingue, useTraduccion, type ClaveTraduccion } from '@/lib/i18n';
import { useSesion } from '@/lib/sesion';
import type {
  CatalogoExtintores,
  Extintor,
  ExtintorPayload,
  ExtintoresPaginados,
  FilaExtintor,
  FiltrosExtintores,
  PuntoRevisionPayload,
  RevisionExtintor,
} from '@/lib/types';
import { fechaDeHoy, rangoDelMes } from '@/lib/utils';

const MS_DEBOUNCE = 350;
const SIN_FILTROS: FiltrosExtintores = {};

/** Clave de la cola de impresión. Lleva el usuario: la laptop es compartida. */
function claveCola(usuario: string): string {
  return `esh_cola_etiquetas:${usuario}`;
}

/**
 * Control de Extintores.
 *
 * Cada aparato tiene su ficha, su etiqueta QR y una revisión de doce puntos al
 * día. El QR pegado al extintor abre esta pestaña con `?extintor=<id>` y el
 * panel salta directo a su revisión: es lo que sustituye al escáner que el
 * navegador no puede darnos (ver `ModalEscanear`).
 */
export function PanelExtintores() {
  const t = useTraduccion();
  const { mostrarToast } = useToast();
  const { puede, usuario } = useSesion();
  const parametros = useSearchParams();

  const puedeEditar = puede('controles', 'editar');

  const [catalogo, setCatalogo] = useState<CatalogoExtintores | null>(null);
  const [datos, setDatos] = useState<ExtintoresPaginados | null>(null);
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState('');

  const [busqueda, setBusqueda] = useState('');
  const [filtros, setFiltros] = useState<FiltrosExtintores>(SIN_FILTROS);
  const [pagina, setPagina] = useState(1);
  const [mes, setMes] = useState(() => fechaDeHoy().slice(0, 7));

  const [editando, setEditando] = useState<Extintor | null>(null);
  const [modalAbierto, setModalAbierto] = useState(false);
  const [guardando, setGuardando] = useState(false);

  const [qr, setQr] = useState<Extintor | null>(null);
  const [cola, setCola] = useState<string[]>([]);
  const [imprimiendo, setImprimiendo] = useState(false);
  const [escaneando, setEscaneando] = useState(false);

  const [revisando, setRevisando] = useState<FilaExtintor | null>(null);
  const [revisionDeHoy, setRevisionDeHoy] = useState<RevisionExtintor | null>(null);

  const [cerrando, setCerrando] = useState<FilaExtintor | null>(null);
  const [porEliminar, setPorEliminar] = useState<Extintor | null>(null);
  const [eliminando, setEliminando] = useState(false);
  const [descargando, setDescargando] = useState(false);

  const peticion = useRef<AbortController | null>(null);
  const saltoHecho = useRef(false);

  function fallo(error: unknown, respaldo: ClaveTraduccion) {
    mostrarToast(error instanceof ErrorDeApi ? error.message : t(respaldo), 'error');
  }

  // El catálogo se pide una sola vez: son constantes del backend.
  useEffect(() => {
    obtenerCatalogoExtintores()
      .then(setCatalogo)
      .catch((error: unknown) => {
        setErrorCarga(
          error instanceof ErrorDeApi ? error.message : t('comun.errorGenerico'),
        );
      });
  }, [t]);

  // La cola vive en el navegador: es una lista de trabajo de quien está
  // imprimiendo, no un dato del sistema. `localStorage` sí funciona fuera de
  // contexto seguro, a diferencia de otras APIs (regla 5).
  useEffect(() => {
    if (usuario === null) {
      return;
    }
    try {
      const guardada = window.localStorage.getItem(claveCola(usuario.username));
      setCola(guardada === null ? [] : (JSON.parse(guardada) as string[]));
    } catch {
      setCola([]);
    }
  }, [usuario]);

  function guardarCola(siguiente: string[]) {
    setCola(siguiente);
    if (usuario === null) {
      return;
    }
    try {
      window.localStorage.setItem(claveCola(usuario.username), JSON.stringify(siguiente));
    } catch {
      // Sin almacenamiento la cola vive solo en memoria; no es motivo para
      // impedir imprimir.
    }
  }

  useEffect(() => {
    const temporizador = setTimeout(() => {
      setPagina(1);
      setFiltros((previos) => ({ ...previos, busqueda: busqueda.trim() || undefined }));
    }, MS_DEBOUNCE);
    return () => clearTimeout(temporizador);
  }, [busqueda]);

  const cargar = useCallback(async () => {
    peticion.current?.abort();
    const control = new AbortController();
    peticion.current = control;

    setCargando(true);
    try {
      const respuesta = await listarExtintores(filtros, pagina, control.signal);
      if (!control.signal.aborted) {
        setDatos(respuesta);
        setErrorCarga('');
      }
    } catch (error: unknown) {
      if (control.signal.aborted) {
        return;
      }
      setErrorCarga(
        error instanceof ErrorDeApi ? error.message : t('extintores.falloCarga'),
      );
    } finally {
      if (!control.signal.aborted) {
        setCargando(false);
      }
    }
  }, [filtros, pagina, t]);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  useEffect(() => () => peticion.current?.abort(), []);

  // El salto del QR: `?extintor=<id>` abre su revisión en cuanto la fila está
  // cargada. Se hace una sola vez, o volver de un modal reabriría el anterior.
  useEffect(() => {
    const pedido = parametros.get('extintor');
    if (pedido === null || saltoHecho.current || datos === null) {
      return;
    }
    const fila = datos.items.find((item) => item.extintor.id === pedido);
    if (fila !== undefined) {
      saltoHecho.current = true;
      void abrirRevision(fila);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [datos, parametros]);

  async function abrirRevision(fila: FilaExtintor) {
    setRevisionDeHoy(null);
    setRevisando(fila);
    if (!fila.revisado_hoy) {
      return;
    }
    try {
      setRevisionDeHoy(await obtenerRevisionDeHoy(fila.extintor.id));
    } catch (error: unknown) {
      fallo(error, 'extintores.falloCarga');
    }
  }

  async function guardarFicha(payload: ExtintorPayload) {
    setGuardando(true);
    try {
      if (editando === null) {
        await crearExtintor(payload);
        mostrarToast(t('extintores.guardado'), 'exito');
      } else {
        await actualizarExtintor(editando.id, payload);
        mostrarToast(t('extintores.actualizado'), 'exito');
      }
      setModalAbierto(false);
      await cargar();
      // El vencimiento cambió: la campana tiene que recontar.
      avisarCambioDeAvisos();
    } catch (error: unknown) {
      fallo(error, 'extintores.falloGuardar');
    } finally {
      setGuardando(false);
    }
  }

  async function guardarRevision(
    puntos: PuntoRevisionPayload[],
    fotos: Record<number, File[]>,
    corrigiendo: boolean,
  ) {
    if (revisando === null) {
      return;
    }
    setGuardando(true);
    try {
      await guardarRevisionExtintor(revisando.extintor.id, puntos, fotos, corrigiendo);
      mostrarToast(t('extintores.revisionGuardada'), 'exito');
      setRevisando(null);
      await cargar();
    } catch (error: unknown) {
      fallo(error, 'extintores.falloGuardar');
    } finally {
      setGuardando(false);
    }
  }

  async function confirmarEliminacion() {
    if (porEliminar === null) {
      return;
    }
    setEliminando(true);
    try {
      await eliminarExtintor(porEliminar.id);
      mostrarToast(t('extintores.eliminado'), 'exito');
      setPorEliminar(null);
      await cargar();
      avisarCambioDeAvisos();
    } catch (error: unknown) {
      fallo(error, 'extintores.falloEliminar');
    } finally {
      setEliminando(false);
    }
  }

  async function imprimir(ids: string[]) {
    setImprimiendo(true);
    try {
      await descargarEtiquetasExtintores(ids);
    } catch (error: unknown) {
      fallo(error, 'extintores.falloEtiquetas');
    } finally {
      setImprimiendo(false);
    }
  }

  async function descargar() {
    const { desde, hasta } = rangoDelMes(`${mes}-01`);
    setDescargando(true);
    try {
      await descargarExcelExtintores(desde, hasta);
    } catch (error: unknown) {
      fallo(error, 'comun.errorGenerico');
    } finally {
      setDescargando(false);
    }
  }

  const registrados = datos?.registrados ?? 0;
  const lleno = catalogo !== null && registrados >= catalogo.maximo;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-texto">
            {bilingue(t('extintores.titulo'))}
          </h2>
          <p className="mt-1 text-sm text-texto-suave">
            {bilingue(t('extintores.descripcion'))}
          </p>
          <p className="mt-1 text-sm text-texto-tenue">
            {bilingue(
              t('extintores.revisadosHoy', {
                revisados: datos?.revisados_hoy ?? 0,
                total: registrados,
              }),
            )}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <BotonIcono
            etiqueta={t('extintores.escanear')}
            icono={<IconoCamara />}
            onClick={() => setEscaneando(true)}
          />
          {cola.length > 0 && (
            <Button
              variante="secundario"
              onClick={() => void imprimir(cola)}
              cargando={imprimiendo}
            >
              {bilingue(t('extintores.imprimirCola', { total: cola.length }))}
            </Button>
          )}
          {cola.length > 0 && (
            <Button variante="fantasma" onClick={() => guardarCola([])}>
              {bilingue(t('extintores.vaciarCola'))}
            </Button>
          )}
          <Button
            onClick={() => {
              setEditando(null);
              setModalAbierto(true);
            }}
            disabled={lleno}
          >
            {bilingue(t('extintores.registrar'))}
          </Button>
        </div>
      </div>

      {lleno && (
        <p className="rounded-md border border-alerta bg-alerta-suave px-3 py-2 text-sm text-alerta">
          {bilingue(t('extintores.tope', { maximo: catalogo?.maximo ?? 0 }))}
        </p>
      )}

      {errorCarga !== '' && (
        <p
          role="alert"
          className="rounded-md border border-error bg-error-suave px-3 py-2 text-sm text-error"
        >
          {errorCarga}
        </p>
      )}

      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-col gap-1.5">
          <label htmlFor="mes-extintores" className="text-sm font-medium text-texto">
            {bilingue(t('comun.mes'))}
          </label>
          <input
            id="mes-extintores"
            type="month"
            value={mes}
            onChange={(evento) => setMes(evento.target.value)}
            className="h-10 rounded-md border border-borde bg-fondo px-3 text-sm text-texto focus:border-primario"
          />
        </div>

        <Button
          variante="secundario"
          onClick={() => void descargar()}
          cargando={descargando}
          disabled={registrados === 0}
        >
          {bilingue(t('comun.descargarExcel'))}
        </Button>
      </div>

      <TablaExtintores
        datos={datos}
        cargando={cargando}
        busqueda={busqueda}
        filtros={filtros}
        tipos={catalogo?.tipos ?? []}
        puedeEditar={puedeEditar}
        enCola={(id) => cola.includes(id)}
        onBusqueda={setBusqueda}
        onFiltros={(siguientes) => {
          setPagina(1);
          setFiltros(siguientes);
        }}
        onLimpiar={() => {
          setBusqueda('');
          setPagina(1);
          setFiltros(SIN_FILTROS);
        }}
        onPagina={setPagina}
        onQr={setQr}
        onEditar={(extintor) => {
          setEditando(extintor);
          setModalAbierto(true);
        }}
        onRevisar={(fila) => void abrirRevision(fila)}
        onCerrarHallazgo={setCerrando}
        onEliminar={setPorEliminar}
      />

      <ModalExtintor
        abierto={modalAbierto}
        extintor={editando}
        tipos={catalogo?.tipos ?? []}
        guardando={guardando}
        onGuardar={guardarFicha}
        onCerrar={() => setModalAbierto(false)}
      />

      <ModalRevision
        fila={revisando}
        puntos={catalogo?.puntos ?? []}
        maxFotos={catalogo?.max_fotos ?? 4}
        revision={revisionDeHoy}
        guardando={guardando}
        onGuardar={guardarRevision}
        onError={(mensaje) => mostrarToast(mensaje, 'error')}
        onCerrar={() => setRevisando(null)}
      />

      <ModalQrExtintor
        extintor={qr}
        enCola={qr !== null && cola.includes(qr.id)}
        imprimiendo={imprimiendo}
        onImprimir={() => qr !== null && void imprimir([qr.id])}
        onEncolar={() => {
          if (qr !== null && !cola.includes(qr.id)) {
            guardarCola([...cola, qr.id]);
            mostrarToast(t('extintores.anadidaACola'), 'exito');
          }
        }}
        onCerrar={() => setQr(null)}
      />

      <ModalEscanear abierto={escaneando} onCerrar={() => setEscaneando(false)} />

      {/* El mismo modal que el resto de los controles: ya es agnóstico. */}
      <ModalCierreHallazgo
        abierto={cerrando !== null}
        control="extintores"
        registroId={cerrando?.revision_id ?? ''}
        onCerrar={() => setCerrando(null)}
        onGuardado={(mensaje) => {
          mostrarToast(mensaje, 'exito');
          setCerrando(null);
          void cargar();
        }}
        onError={(mensaje) => mostrarToast(mensaje, 'error')}
      />

      <DialogoConfirmacion
        abierto={porEliminar !== null}
        titulo={t('extintores.confirmarEliminar')}
        mensaje={
          porEliminar === null
            ? ''
            : t('extintores.confirmarEliminarDetalle', { folio: porEliminar.folio })
        }
        procesando={eliminando}
        onConfirmar={() => void confirmarEliminacion()}
        onCancelar={() => setPorEliminar(null)}
      />
    </div>
  );
}
