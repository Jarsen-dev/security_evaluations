'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { TablaStock } from '@/components/inventario/stock/TablaStock';
import { Button } from '@/components/ui/Button';
import { ErrorDeApi, listarStock, obtenerCategoriasStock } from '@/lib/api';
import { bilingue, useTraduccion } from '@/lib/i18n';
import type { FiltrosCatalogo, InsumosPaginados } from '@/lib/types';

/** Espera antes de consultar mientras se teclea en el buscador. */
const MS_DEBOUNCE = 350;

const SIN_FILTROS: FiltrosCatalogo = {};

/**
 * Existencias del catálogo, dentro de Inventario.
 *
 * Mismo ciclo que `PanelCatalogo` —debounce del buscador, filtros en estado
 * local y paginación del servidor— pero contra `/api/inventario/stock`, que
 * pide el permiso de este módulo y no el del catálogo.
 *
 * Se consulta al montar, así que entrar a la pestaña después de dar de alta un
 * producto ya lo trae; el botón de actualizar es para cuando alguien más lo
 * capturó mientras la pantalla estaba abierta.
 */
export function PanelStock() {
  const t = useTraduccion();

  const [datos, setDatos] = useState<InsumosPaginados | null>(null);
  const [categorias, setCategorias] = useState<string[]>([]);
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState('');

  const [busqueda, setBusqueda] = useState('');
  const [filtros, setFiltros] = useState<FiltrosCatalogo>(SIN_FILTROS);
  const [pagina, setPagina] = useState(1);

  // Una petición en vuelo: si el usuario sigue tecleando, la anterior se
  // cancela en vez de competir por pintar la tabla.
  const peticion = useRef<AbortController | null>(null);

  useEffect(() => {
    obtenerCategoriasStock()
      .then(setCategorias)
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
      const respuesta = await listarStock(filtros, pagina, control.signal);
      if (!control.signal.aborted) {
        setDatos(respuesta);
        setErrorCarga('');
      }
    } catch (error: unknown) {
      if (control.signal.aborted) {
        return;
      }
      setErrorCarga(error instanceof ErrorDeApi ? error.message : t('stock.falloCarga'));
    } finally {
      if (!control.signal.aborted) {
        setCargando(false);
      }
    }
  }, [filtros, pagina, t]);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  function cambiarFiltros(siguientes: FiltrosCatalogo) {
    // Cambiar un filtro con la página 7 abierta dejaría una lista vacía sin
    // explicación: se vuelve al principio.
    setPagina(1);
    setFiltros(siguientes);
  }

  function limpiar() {
    setBusqueda('');
    setPagina(1);
    setFiltros(SIN_FILTROS);
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-texto-suave">{bilingue(t('stock.descripcion'))}</p>

      {errorCarga !== '' && (
        <div
          role="alert"
          className="flex flex-wrap items-center gap-3 rounded-tarjeta border border-error bg-error-suave px-4 py-3 text-sm text-texto"
        >
          <span>{errorCarga}</span>
          <Button variante="secundario" tamano="sm" onClick={() => void cargar()}>
            {bilingue(t('comun.reintentar'))}
          </Button>
        </div>
      )}

      <TablaStock
        datos={datos}
        cargando={cargando}
        categorias={categorias}
        filtros={filtros}
        busqueda={busqueda}
        onBusqueda={setBusqueda}
        onFiltros={cambiarFiltros}
        onLimpiar={limpiar}
        onPagina={setPagina}
        onActualizar={() => void cargar()}
      />
    </div>
  );
}
