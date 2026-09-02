'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { Badge } from '@/components/ui/Badge';
import { BotonIcono, FilaAcciones } from '@/components/ui/BotonIcono';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { IconoOjo } from '@/components/ui/Iconos';
import { Modal } from '@/components/ui/Modal';
import { VisorImagen } from '@/components/ui/VisorImagen';
import {
  ErrorDeApi,
  listarRecepciones,
  obtenerRecepcion,
  obtenerTiposDocumento,
  urlFotoRecepcion,
} from '@/lib/api';
import { bilingue, unaLinea, useIdioma } from '@/lib/i18n';
import type {
  FiltrosRecepciones,
  Recepcion,
  RecepcionesPaginadas,
  TipoDocumento,
} from '@/lib/types';

const CLASES_CAMPO =
  'h-10 rounded-md border border-borde bg-fondo px-3 text-sm text-texto focus:border-primario';

/** Número de columnas, para los renglones de estado vacío. */
const COLUMNAS = 6;

/** Espera antes de consultar mientras se teclea en el buscador. */
const MS_DEBOUNCE = 300;

/** Historial de recepciones, paginado del lado del servidor. */
export function TablaRecepciones() {
  const { t, locale } = useIdioma();

  const [datos, setDatos] = useState<RecepcionesPaginadas | null>(null);
  const [tipos, setTipos] = useState<TipoDocumento[]>([]);
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState('');

  const [detalle, setDetalle] = useState<Recepcion | null>(null);
  const [detalleAbierto, setDetalleAbierto] = useState(false);
  const [errorDetalle, setErrorDetalle] = useState('');
  // La foto se toma del renglón y no de `detalle`: así aparece mientras las
  // partidas todavía se están cargando, y sigue estando si esa consulta falla
  // —que es justo cuando hace falta mirar el papel—.
  const [fotoDetalle, setFotoDetalle] = useState<string | null>(null);

  const [busqueda, setBusqueda] = useState('');
  const [filtros, setFiltros] = useState<FiltrosRecepciones>({});
  const [pagina, setPagina] = useState(1);

  // Una petición por render en vuelo: si el usuario sigue tecleando, la
  // anterior se cancela en vez de competir por pintar la tabla.
  const peticion = useRef<AbortController | null>(null);

  useEffect(() => {
    obtenerTiposDocumento()
      .then(setTipos)
      .catch(() => {
        // El filtro se queda sin opciones; la tabla funciona igual.
      });
  }, []);

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
      const pagina_ = await listarRecepciones(filtros, pagina, control.signal);
      if (!control.signal.aborted) {
        setDatos(pagina_);
        setErrorCarga('');
      }
    } catch (error: unknown) {
      if (control.signal.aborted) {
        return;
      }
      setErrorCarga(
        error instanceof ErrorDeApi ? error.message : t('recepciones.falloCarga'),
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

  const total = datos?.total ?? 0;
  const size = datos?.size ?? 50;
  const paginaActual = datos?.page ?? 1;
  const totalPaginas = Math.max(1, Math.ceil(total / size));
  const hayFiltros = busqueda !== '' || filtros.tipo_documento !== undefined;

  async function abrirDetalle(recepcion: Recepcion) {
    setDetalle(null);
    setErrorDetalle('');
    setFotoDetalle(recepcion.foto_id);
    setDetalleAbierto(true);

    try {
      setDetalle(await obtenerRecepcion(recepcion.id));
    } catch (error: unknown) {
      setErrorDetalle(
        error instanceof ErrorDeApi ? error.message : t('recepciones.falloDetalle'),
      );
    }
  }

  const fecha = (valor: string) =>
    new Date(valor).toLocaleString(locale, { dateStyle: 'short', timeStyle: 'short' });

  return (
    <Card className="overflow-hidden p-0">
      <div className="flex flex-wrap items-end gap-3 border-b border-borde bg-fondo/40 px-5 py-4">
        <div className="flex min-w-[16rem] flex-1 flex-col gap-1.5">
          <label htmlFor="recepciones-busqueda" className="text-xs font-medium text-texto-suave">
            {bilingue(t('comun.buscar'))}
          </label>
          <input
            id="recepciones-busqueda"
            type="search"
            className={CLASES_CAMPO}
            placeholder={unaLinea(t('recepciones.buscar'))}
            value={busqueda}
            onChange={(evento) => setBusqueda(evento.target.value)}
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="recepciones-formato" className="text-xs font-medium text-texto-suave">
            {bilingue(t('recepciones.formato'))}
          </label>
          <select
            id="recepciones-formato"
            className={CLASES_CAMPO}
            value={filtros.tipo_documento ?? ''}
            onChange={(evento) => {
              setPagina(1);
              setFiltros((previos) => ({
                ...previos,
                tipo_documento: evento.target.value || undefined,
              }));
            }}
          >
            <option value="">{unaLinea(t('recepciones.todosLosFormatos'))}</option>
            {tipos.map((tipo) => (
              <option key={tipo.slug} value={tipo.slug}>
                {tipo.nombre}
              </option>
            ))}
          </select>
        </div>

        <span className="ml-auto text-sm text-texto-suave">
          {bilingue(t('recepciones.registros', { total }))}
        </span>
      </div>

      {errorCarga !== '' && (
        <div role="alert" className="flex items-center gap-3 border-b border-borde px-5 py-3 text-sm">
          <span className="text-texto">{errorCarga}</span>
          <Button variante="secundario" tamano="sm" onClick={() => void cargar()}>
            {bilingue(t('comun.reintentar'))}
          </Button>
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full min-w-[52rem] text-sm">
          <thead className="bg-fondo-sutil">
            <tr>
              <th scope="col" className="px-5 py-3 text-left font-medium text-texto-suave">
                {bilingue(t('recepciones.proveedor'))}
              </th>
              <th scope="col" className="px-5 py-3 text-left font-medium text-texto-suave">
                {bilingue(t('recepciones.folio'))}
              </th>
              <th scope="col" className="px-5 py-3 text-left font-medium text-texto-suave">
                {bilingue(t('recepciones.fecha'))}
              </th>
              <th scope="col" className="px-5 py-3 text-left font-medium text-texto-suave">
                {bilingue(t('recepciones.partidas'))}
              </th>
              <th scope="col" className="px-5 py-3 text-left font-medium text-texto-suave">
                {bilingue(t('recepciones.capturadaEl'))}
              </th>
              <th scope="col" className="px-5 py-3 text-right">
                <span className="sr-only">{bilingue(t('comun.acciones'))}</span>
              </th>
            </tr>
          </thead>

          <tbody>
            {cargando ? (
              <tr>
                <td colSpan={COLUMNAS} className="px-5 py-8 text-center text-texto-suave">
                  {bilingue(t('comun.cargando'))}
                </td>
              </tr>
            ) : total === 0 ? (
              <tr>
                <td colSpan={COLUMNAS} className="px-5 py-10 text-center">
                  <p className="text-sm font-medium text-texto">
                    {bilingue(hayFiltros ? t('recepciones.sinCoincidencias') : t('recepciones.vacio'))}
                  </p>
                  {!hayFiltros && (
                    <p className="mt-2 text-sm text-texto-suave">
                      {bilingue(t('recepciones.vacioAyuda'))}
                    </p>
                  )}
                </td>
              </tr>
            ) : (
              datos?.items.map((recepcion) => (
                <tr key={recepcion.id} className="border-b border-borde last:border-0">
                  <td className="px-5 py-3">
                    <span className="font-medium text-texto">
                      {recepcion.proveedor ?? '—'}
                    </span>
                    <span className="mt-0.5 block text-xs text-texto-tenue">
                      {recepcion.creado_por}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-texto-suave">{recepcion.folio ?? '—'}</td>
                  <td className="px-5 py-3 text-texto-suave">{recepcion.fecha ?? '—'}</td>
                  <td className="px-5 py-3">
                    <span className="text-texto-suave">{recepcion.items.length}</span>
                    {/* Se distingue lo capturado a mano de lo que leyó la IA:
                        es lo que permite auditar el módulo después. */}
                    {!recepcion.ocr_ok && (
                      <Badge tono="alerta">{bilingue(t('recepciones.manual'))}</Badge>
                    )}
                  </td>
                  <td className="px-5 py-3 text-texto-tenue">
                    {fecha(recepcion.creado_at)}
                  </td>
                  <td className="px-5 py-3 text-right">
                    {/* Con el código repetible, el conteo de partidas ya no
                        dice a qué producto entró la mercancía. El detalle trae
                        además la foto, así que ya no hay enlace aparte para
                        abrirla en otra pestaña. */}
                    <FilaAcciones>
                      <BotonIcono
                        etiqueta={t('recepciones.verDetalle')}
                        icono={<IconoOjo />}
                        onClick={() => void abrirDetalle(recepcion)}
                      />
                    </FilaAcciones>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {total > size && (
        <div className="flex items-center justify-between border-t border-borde px-5 py-3">
          <span className="text-sm text-texto-suave">
            {bilingue(t('recepciones.pagina', { pagina: paginaActual, total: totalPaginas }))}
          </span>
          <div className="flex gap-2">
            <Button
              variante="secundario"
              tamano="sm"
              disabled={paginaActual <= 1}
              onClick={() => setPagina(paginaActual - 1)}
            >
              {bilingue(t('recepciones.anterior'))}
            </Button>
            <Button
              variante="secundario"
              tamano="sm"
              disabled={paginaActual >= totalPaginas}
              onClick={() => setPagina(paginaActual + 1)}
            >
              {bilingue(t('recepciones.siguiente'))}
            </Button>
          </div>
        </div>
      )}

      <Modal
        abierto={detalleAbierto}
        onCerrar={() => setDetalleAbierto(false)}
        titulo={t('recepciones.detalle')}
        descripcion={
          detalle === null
            ? undefined
            : `${detalle.proveedor ?? '—'} · ${detalle.folio ?? '—'}`
        }
        ancho="xl"
      >
        {/* Lado a lado, igual que la pantalla de captura: lo que se compara
            es la hoja contra las partidas, y apiladas obligaba a subir y bajar
            para cotejar cada renglón. En una pantalla angosta se apilan, que
            ahí no hay ancho para dos columnas. */}
        <div className="grid gap-4 lg:grid-cols-2">
          {/* El mismo visor de la captura: la remisión llega como la tomó el
              operador —de lado, o con la letra demasiado chica—, y consultar
              el histórico exige leerla igual que corregirla. */}
          {fotoDetalle !== null ? (
            <div className="overflow-hidden rounded-tarjeta border border-borde">
              <VisorImagen
                src={urlFotoRecepcion(fotoDetalle)}
                alt={t('recepciones.fotoRemision')}
                className="h-[45vh] w-full lg:h-[60vh]"
              />
            </div>
          ) : (
            <p className="text-sm text-texto-suave">{bilingue(t('recepciones.sinFoto'))}</p>
          )}

          {errorDetalle !== '' ? (
            <p role="alert" className="text-sm text-error">
              {errorDetalle}
            </p>
          ) : detalle === null ? (
            <p className="text-sm text-texto-suave">{bilingue(t('comun.cargando'))}</p>
          ) : (
            // La tabla se desplaza dentro de su columna y no arrastra el modal
            // entero: así la foto se queda quieta mientras se recorren las
            // partidas, que es justo para lo que sirve verlas juntas.
            <div className="overflow-auto lg:max-h-[60vh]">
              <table className="w-full min-w-[26rem] text-sm">
                <thead className="bg-fondo-sutil">
                  <tr>
                    <th scope="col" className="px-3 py-2 text-left font-medium text-texto-suave">
                      {bilingue(t('recepciones.codigo'))}
                    </th>
                    <th scope="col" className="px-3 py-2 text-left font-medium text-texto-suave">
                      {bilingue(t('recepciones.descripcionItem'))}
                    </th>
                    <th scope="col" className="px-3 py-2 text-right font-medium text-texto-suave">
                      {bilingue(t('recepciones.cajas'))}
                    </th>
                    <th scope="col" className="px-3 py-2 text-right font-medium text-texto-suave">
                      {bilingue(t('recepciones.piezasTotales'))}
                    </th>
                    <th scope="col" className="px-3 py-2 text-left font-medium text-texto-suave">
                      {bilingue(t('recepciones.unidad'))}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {/* Todo es el snapshot guardado con el documento: si el
                      catálogo cambió después, la remisión sigue diciendo lo que
                      se recibió el día que se recibió. */}
                  {detalle.items.map((item) => (
                    <tr key={item.id} className="border-b border-borde last:border-0">
                      <td className="px-3 py-2 font-medium text-texto">{item.codigo}</td>
                      <td className="px-3 py-2 text-texto-suave">
                        {item.descripcion ?? '—'}
                      </td>
                      <td className="px-3 py-2 text-right text-texto-suave">
                        {item.cantidad.toLocaleString(locale)}
                      </td>
                      <td className="px-3 py-2 text-right font-medium text-texto">
                        {item.piezas.toLocaleString(locale)}
                      </td>
                      <td className="px-3 py-2 text-texto-suave">{item.unidad_medida}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </Modal>
    </Card>
  );
}
