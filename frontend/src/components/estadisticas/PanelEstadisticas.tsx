'use client';

import { useCallback, useEffect, useState } from 'react';

import {
  GraficaDistribucion,
  GraficaLineaTiempo,
  GraficaParticipacion,
  GraficaPreguntasFalladas,
  GraficaPromedioPorArea,
} from '@/components/estadisticas/Graficas';
import { ModalMetas } from '@/components/estadisticas/ModalMetas';
import { ModalRespuestas } from '@/components/estadisticas/ModalRespuestas';
import { TablaIntentos } from '@/components/estadisticas/TablaIntentos';
import { TarjetaKPI } from '@/components/estadisticas/TarjetaKPI';
import { Button } from '@/components/ui/Button';
import { useToast } from '@/components/ui/Toast';
import { bilingue, unaLinea, useTraduccion } from '@/lib/i18n';
import { useSesion } from '@/lib/sesion';
import {
  ErrorDeApi,
  descargarReporte,
  listarCuestionarios,
  obtenerAreas,
  obtenerDistribucion,
  obtenerIntentos,
  obtenerLineaTiempo,
  obtenerPorArea,
  obtenerPorPregunta,
  obtenerResumen,
} from '@/lib/api';
import type {
  Area,
  ColumnaOrdenable,
  CuestionarioResumen,
  EstadisticaArea,
  EstadisticaPregunta,
  FiltrosEstadisticas,
  IntentosPaginados,
  PuntoLineaTiempo,
  RangoDistribucion,
  Resumen,
} from '@/lib/types';

const TAMANO_PAGINA = 15;

/**
 * Pestaña "Estadísticas", ahora dentro de Cuestionarios: son dos vistas del
 * mismo material y separarlas obligaba a saltar de sección para comparar.
 */
export function PanelEstadisticas() {
  const t = useTraduccion();
  const { mostrarToast } = useToast();
  const { puede } = useSesion();

  // Capturar las metas por área modifica datos existentes: pide el mismo
  // permiso de edición que el resto de Cuestionarios.
  const puedeEditar = puede('cuestionarios', 'editar');

  const [cuestionarios, setCuestionarios] = useState<CuestionarioResumen[]>([]);
  const [areas, setAreas] = useState<Area[]>([]);

  const [cuestionarioId, setCuestionarioId] = useState('');
  const [area, setArea] = useState('');
  const [desde, setDesde] = useState('');
  const [hasta, setHasta] = useState('');

  const [resumen, setResumen] = useState<Resumen | null>(null);
  const [porArea, setPorArea] = useState<EstadisticaArea[]>([]);
  const [porPregunta, setPorPregunta] = useState<EstadisticaPregunta[]>([]);
  const [distribucion, setDistribucion] = useState<RangoDistribucion[]>([]);
  const [lineaTiempo, setLineaTiempo] = useState<PuntoLineaTiempo[]>([]);
  const [intentos, setIntentos] = useState<IntentosPaginados | null>(null);

  const [busqueda, setBusqueda] = useState('');
  // Valor con retardo: sin esto se dispararía una consulta por cada tecla.
  const [busquedaAplicada, setBusquedaAplicada] = useState('');

  const [pagina, setPagina] = useState(1);
  const [ordenPor, setOrdenPor] = useState<ColumnaOrdenable>('finalizado_at');
  const [descendente, setDescendente] = useState(true);

  const [cargando, setCargando] = useState(false);
  const [cargandoTabla, setCargandoTabla] = useState(false);
  const [error, setError] = useState('');
  const [metasAbierto, setMetasAbierto] = useState(false);
  const [intentoDetalle, setIntentoDetalle] = useState<string | null>(null);
  const [descargando, setDescargando] = useState<'excel' | 'powerpoint' | null>(null);

  // Catálogos iniciales: cuestionarios y áreas.
  useEffect(() => {
    let cancelado = false;

    Promise.all([listarCuestionarios(), obtenerAreas()])
      .then(([listaCuestionarios, listaAreas]) => {
        if (cancelado) {
          return;
        }
        setCuestionarios(listaCuestionarios);
        setAreas(listaAreas);

        // Se preselecciona el cuestionario con más respuestas: es el que el
        // administrador va a querer ver al entrar.
        const conRespuestas = [...listaCuestionarios].sort(
          (a, b) => b.total_respuestas - a.total_respuestas,
        );
        if (conRespuestas.length > 0 && conRespuestas[0]) {
          setCuestionarioId(conRespuestas[0].id);
        }
      })
      .catch((problema) => {
        if (!cancelado) {
          setError(
            problema instanceof ErrorDeApi
              ? problema.message
              : t('cuestionarios.falloCarga'),
          );
        }
      });

    return () => {
      cancelado = true;
    };
  }, [t]);

  // 350 ms es el punto donde la búsqueda se siente inmediata sin castigar
  // al servidor con una consulta por pulsación.
  useEffect(() => {
    const temporizador = setTimeout(() => {
      setBusquedaAplicada(busqueda.trim());
      setPagina(1);
    }, 350);

    return () => clearTimeout(temporizador);
  }, [busqueda]);

  const filtros: FiltrosEstadisticas | null =
    cuestionarioId === ''
      ? null
      : {
          cuestionario_id: cuestionarioId,
          ...(area !== '' ? { area } : {}),
          ...(desde !== '' ? { desde } : {}),
          ...(hasta !== '' ? { hasta } : {}),
        };

  const cargarPaneles = useCallback(async (activos: FiltrosEstadisticas) => {
    setCargando(true);
    setError('');

    try {
      const [datosResumen, datosArea, datosPregunta, datosDistribucion, datosTiempo] =
        await Promise.all([
          obtenerResumen(activos),
          obtenerPorArea(activos),
          obtenerPorPregunta(activos),
          obtenerDistribucion(activos),
          obtenerLineaTiempo(activos),
        ]);

      setResumen(datosResumen);
      setPorArea(datosArea);
      setPorPregunta(datosPregunta);
      setDistribucion(datosDistribucion);
      setLineaTiempo(datosTiempo);
    } catch (problema) {
      setError(
        problema instanceof ErrorDeApi
          ? problema.message
          : t('estadisticas.falloCarga'),
      );
    } finally {
      setCargando(false);
    }
  }, [t]);

  const cargarTabla = useCallback(
    async (activos: FiltrosEstadisticas) => {
      setCargandoTabla(true);
      try {
        setIntentos(
          await obtenerIntentos(activos, {
            page: pagina,
            size: TAMANO_PAGINA,
            orden_por: ordenPor,
            descendente,
            busqueda: busquedaAplicada,
          }),
        );
      } catch {
        setIntentos(null);
      } finally {
        setCargandoTabla(false);
      }
    },
    [pagina, ordenPor, descendente, busquedaAplicada],
  );

  // Recarga los paneles cuando cambian los filtros (no la paginación).
  useEffect(() => {
    if (filtros === null) {
      return;
    }
    void cargarPaneles(filtros);
    setPagina(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `filtros` se
    // reconstruye en cada render; se depende de sus valores primitivos.
  }, [cuestionarioId, area, desde, hasta, cargarPaneles]);

  // La tabla se recarga también al paginar u ordenar.
  useEffect(() => {
    if (filtros === null) {
      return;
    }
    void cargarTabla(filtros);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- misma razón.
  }, [
    cuestionarioId,
    area,
    desde,
    hasta,
    pagina,
    ordenPor,
    descendente,
    busquedaAplicada,
    cargarTabla,
  ]);

  function alternarOrden(columna: ColumnaOrdenable) {
    if (columna === ordenPor) {
      setDescendente((previo) => !previo);
    } else {
      setOrdenPor(columna);
      setDescendente(true);
    }
    setPagina(1);
  }

  async function descargar(formato: 'excel' | 'powerpoint') {
    if (filtros === null) {
      return;
    }

    setDescargando(formato);

    try {
      await descargarReporte(formato, filtros);
      mostrarToast(
        formato === 'excel'
          ? t('estadisticas.excelDescargado')
          : t('estadisticas.powerpointDescargado'),
        'exito',
      );
    } catch (problema) {
      mostrarToast(
        problema instanceof ErrorDeApi
          ? problema.message
          : t('estadisticas.falloReporte'),
        'error',
      );
    } finally {
      setDescargando(null);
    }
  }

  function limpiarFiltros() {
    setArea('');
    setDesde('');
    setHasta('');
    setBusqueda('');
  }

  const hayFiltros = area !== '' || desde !== '' || hasta !== '';
  const participacion = resumen?.participacion;
  // Sin datos todavía: los KPIs muestran un marcador en lugar de ceros.
  const sinResumen = resumen === null || cargando;

  return (
    <section className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-xl font-semibold text-texto">
          {bilingue(t('cuestionarios.pestanaEstadisticas'))}
        </h1>

        <div className="flex flex-wrap items-center gap-2">
          {puedeEditar && (
            <Button variante="fantasma" onClick={() => setMetasAbierto(true)}>
              {bilingue(t('estadisticas.configurarMetas'))}
            </Button>
          )}

          {/* Las descargas respetan los filtros activos del dashboard. */}
          <Button
            variante="secundario"
            disabled={cuestionarioId === ''}
            cargando={descargando === 'excel'}
            onClick={() => void descargar('excel')}
          >
            {bilingue(t('estadisticas.descargarExcel'))}
          </Button>

          <Button
            variante="secundario"
            disabled={cuestionarioId === ''}
            cargando={descargando === 'powerpoint'}
            onClick={() => void descargar('powerpoint')}
          >
            {bilingue(t('estadisticas.descargarPowerpoint'))}
          </Button>
        </div>
      </div>

      {/* --- Filtros --- */}
      <div className="flex flex-wrap items-end gap-3 rounded-tarjeta border border-borde bg-fondo-elevado p-4">
        <div className="flex min-w-[16rem] flex-1 flex-col gap-1.5">
          <label htmlFor="cuestionario" className="text-sm font-medium text-texto">
            {bilingue(t('estadisticas.cuestionario'))}
          </label>
          <select
            id="cuestionario"
            value={cuestionarioId}
            onChange={(evento) => setCuestionarioId(evento.target.value)}
            className="h-10 rounded-md border border-borde bg-fondo px-3 text-sm text-texto focus:border-primario"
          >
            <option value="">{unaLinea(t('estadisticas.seleccionaCuestionario'))}</option>
            {cuestionarios.map((cuestionario) => (
              <option key={cuestionario.id} value={cuestionario.id}>
                {cuestionario.nombre} (
                {unaLinea(t('estadisticas.respuestasContador', {
                  total: cuestionario.total_respuestas,
                }))}
                )
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="area" className="text-sm font-medium text-texto">
            {bilingue(t('comun.area'))}
          </label>
          <select
            id="area"
            value={area}
            onChange={(evento) => setArea(evento.target.value)}
            className="h-10 rounded-md border border-borde bg-fondo px-3 text-sm text-texto focus:border-primario"
          >
            <option value="">{unaLinea(t('comun.areaTodas'))}</option>
            {areas.map((opcion) => (
              <option key={opcion.value} value={opcion.value}>
                {opcion.label}
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="desde" className="text-sm font-medium text-texto">
            {bilingue(t('comun.desde'))}
          </label>
          <input
            id="desde"
            type="date"
            value={desde}
            onChange={(evento) => setDesde(evento.target.value)}
            className="h-10 rounded-md border border-borde bg-fondo px-3 text-sm text-texto focus:border-primario"
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="hasta" className="text-sm font-medium text-texto">
            {bilingue(t('comun.hasta'))}
          </label>
          <input
            id="hasta"
            type="date"
            value={hasta}
            onChange={(evento) => setHasta(evento.target.value)}
            className="h-10 rounded-md border border-borde bg-fondo px-3 text-sm text-texto focus:border-primario"
          />
        </div>

        {hayFiltros && (
          <Button variante="fantasma" onClick={limpiarFiltros}>
            {bilingue(t('estadisticas.limpiarFiltros'))}
          </Button>
        )}
      </div>

      {error && (
        <p
          role="alert"
          className="rounded-tarjeta border border-error bg-error-suave p-4 text-sm text-error"
        >
          {error}
        </p>
      )}

      {cuestionarioId === '' && !error && (
        <div className="rounded-tarjeta border border-dashed border-borde p-10 text-center">
          <p className="text-texto-suave">{bilingue(t('estadisticas.seleccionaParaVer'))}</p>
          {cuestionarios.length === 0 && (
            <p className="mt-1 text-sm text-texto-tenue">{bilingue(t('cuestionarios.vacio'))}</p>
          )}
        </div>
      )}

      {cuestionarioId !== '' && (
        <>
          {/* --- KPIs --- */}
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <TarjetaKPI
              etiqueta={t('estadisticas.kpiRespuestas')}
              cargando={sinResumen}
              valor={resumen?.total_respuestas ?? 0}
              detalle={
                resumen && resumen.total_en_progreso > 0
                  ? t('estadisticas.sinFinalizarContador', {
                      total: resumen.total_en_progreso,
                    })
                  : undefined
              }
            />

            <TarjetaKPI
              etiqueta={t('estadisticas.kpiParticipacion')}
              cargando={sinResumen}
              vacio={!participacion?.porcentaje}
              valor={`${participacion?.porcentaje ?? 0}%`}
              detalle={
                participacion?.meta
                  ? t('estadisticas.participacionDetalle', {
                      recibidas: participacion.recibidas,
                      meta: participacion.meta,
                    })
                  : t('estadisticas.sinMetas')
              }
            />

            <TarjetaKPI
              etiqueta={t('estadisticas.kpiPromedio')}
              cargando={sinResumen}
              vacio={resumen?.promedio_general === null}
              valor={`${resumen?.promedio_general ?? 0}%`}
            />

            <TarjetaKPI
              etiqueta={t('estadisticas.kpiAprobacion')}
              cargando={sinResumen}
              vacio={resumen?.tasa_aprobacion === null}
              valor={`${resumen?.tasa_aprobacion ?? 0}%`}
              detalle={
                resumen
                  ? t('estadisticas.aprobadosDetalle', {
                      total: resumen.aprobados,
                      umbral: resumen.umbral_aprobacion,
                    })
                  : undefined
              }
            />
          </div>

          {cargando && (
            <p className="text-sm text-texto-suave">{bilingue(t('estadisticas.actualizando'))}</p>
          )}

          {/* --- Gráficas --- */}
          <div className="grid gap-4 xl:grid-cols-2">
            <GraficaParticipacion datos={porArea} />
            <GraficaPromedioPorArea
              datos={porArea}
              umbral={resumen?.umbral_aprobacion ?? 70}
            />
            <GraficaDistribucion datos={distribucion} />
            <GraficaLineaTiempo datos={lineaTiempo} />
            <div className="xl:col-span-2">
              <GraficaPreguntasFalladas datos={porPregunta} />
            </div>
          </div>

          <TablaIntentos
            datos={intentos}
            cargando={cargandoTabla}
            ordenPor={ordenPor}
            descendente={descendente}
            onOrdenar={alternarOrden}
            onPagina={setPagina}
            areas={areas}
            busqueda={busqueda}
            onBusqueda={setBusqueda}
            // Área y fechas comparten estado con los filtros del tablero:
            // así no puede haber dos valores contradictorios en pantalla.
            area={area}
            onArea={setArea}
            desde={desde}
            onDesde={setDesde}
            hasta={hasta}
            onHasta={setHasta}
            onLimpiar={limpiarFiltros}
            onVerRespuestas={setIntentoDetalle}
          />
        </>
      )}

      <ModalRespuestas
        intentoId={intentoDetalle}
        onCerrar={() => setIntentoDetalle(null)}
      />

      <ModalMetas
        abierto={metasAbierto}
        onCerrar={() => setMetasAbierto(false)}
        onGuardado={() => {
          if (filtros !== null) {
            void cargarPaneles(filtros);
          }
        }}
      />
    </section>
  );
}
