'use client';

import { useCallback, useEffect, useState } from 'react';

import { ImportarCatalogo } from '@/components/catalogo/ImportarCatalogo';
import { ModalInsumo, type DatosInsumo } from '@/components/catalogo/ModalInsumo';
import { TablaCatalogo } from '@/components/catalogo/TablaCatalogo';
import { Button } from '@/components/ui/Button';
import { DialogoConfirmacion } from '@/components/ui/DialogoConfirmacion';
import { useToast } from '@/components/ui/Toast';
import {
  ErrorDeApi,
  actualizarInsumo,
  crearInsumo,
  eliminarInsumo,
  listarInsumos,
  obtenerCategoriasInsumo,
} from '@/lib/api';
import { useTraduccion, type ClaveTraduccion } from '@/lib/i18n';
import { useSesion } from '@/lib/sesion';
import type { FiltrosCatalogo, Insumo, InsumoPayload, InsumosPaginados } from '@/lib/types';

const SIN_FILTROS: FiltrosCatalogo = {};

/** Los campos opcionales viajan como `null`, no como cadena vacía. */
function aPayload(datos: DatosInsumo): InsumoPayload {
  const opcional = (valor: string) => valor.trim() || null;

  return {
    nombre: datos.nombre.trim(),
    descripcion: opcional(datos.descripcion),
    categoria: datos.categoria,
    proveedor: opcional(datos.proveedor),
    ubicacion: opcional(datos.ubicacion),
    cantidad: Number(datos.cantidad),
    minimo: Number(datos.minimo),
    maximo: Number(datos.maximo),
  };
}

export function PanelCatalogo() {
  const t = useTraduccion();
  const { mostrarToast } = useToast();
  const { puede } = useSesion();

  // La API rechaza con 403 lo que este usuario no puede hacer; aquí solo se
  // esconden los botones para no ofrecerlo.
  const puedeEditar = puede('catalogo', 'editar');

  const [datos, setDatos] = useState<InsumosPaginados | null>(null);
  const [categorias, setCategorias] = useState<string[]>([]);
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState('');

  const [busqueda, setBusqueda] = useState('');
  const [filtros, setFiltros] = useState<FiltrosCatalogo>(SIN_FILTROS);
  const [pagina, setPagina] = useState(1);

  const [modalAbierto, setModalAbierto] = useState(false);
  const [editando, setEditando] = useState<Insumo | null>(null);
  const [guardando, setGuardando] = useState(false);

  const [porEliminar, setPorEliminar] = useState<Insumo | null>(null);
  const [eliminando, setEliminando] = useState(false);

  // El catálogo de categorías se pide una sola vez: viene del backend para
  // que nunca quede escrito a mano en el frontend.
  useEffect(() => {
    let cancelado = false;

    obtenerCategoriasInsumo()
      .then((lista) => {
        if (!cancelado) setCategorias(lista);
      })
      .catch(() => {
        // Los selectores se quedan sin opciones; el resto de la pantalla
        // funciona igual y no vale la pena molestar con un error aparte.
      });

    return () => {
      cancelado = true;
    };
  }, []);

  // Debounce del buscador: cada tecla no dispara una consulta.
  useEffect(() => {
    const temporizador = setTimeout(() => {
      setPagina(1);
      setFiltros((previos) => ({
        ...previos,
        busqueda: busqueda.trim() || undefined,
      }));
    }, 350);

    return () => clearTimeout(temporizador);
  }, [busqueda]);

  const cargar = useCallback(async () => {
    setCargando(true);

    try {
      setDatos(await listarInsumos(filtros, pagina));
      setErrorCarga('');
    } catch (error: unknown) {
      setErrorCarga(
        error instanceof ErrorDeApi ? error.message : t('catalogo.falloCarga'),
      );
    } finally {
      setCargando(false);
    }
  }, [filtros, pagina, t]);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  function mostrarFallo(error: unknown, respaldo: ClaveTraduccion) {
    mostrarToast(error instanceof ErrorDeApi ? error.message : t(respaldo), 'error');
  }

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

  async function guardar(valores: DatosInsumo) {
    setGuardando(true);

    try {
      if (editando === null) {
        await crearInsumo(aPayload(valores));
        mostrarToast(t('catalogo.creado'), 'exito');
      } else {
        await actualizarInsumo(editando.id, aPayload(valores));
        mostrarToast(t('catalogo.actualizado'), 'exito');
      }

      setModalAbierto(false);
      await cargar();
    } catch (error: unknown) {
      mostrarFallo(error, 'catalogo.falloGuardar');
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
      await eliminarInsumo(porEliminar.id);
      mostrarToast(t('catalogo.eliminado'), 'exito');
      setPorEliminar(null);
      await cargar();
    } catch (error: unknown) {
      mostrarFallo(error, 'catalogo.falloEliminar');
    } finally {
      setEliminando(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        {/* `min-w-0` deja que el bloque de importación se encoja en vez de
            empujar el botón principal a otro renglón. */}
        <div className="min-w-0 flex-1">
          <ImportarCatalogo onImportado={() => void cargar()} />
        </div>

        <Button
          onClick={() => {
            setEditando(null);
            setModalAbierto(true);
          }}
        >
          {t('catalogo.nuevo')}
        </Button>
      </div>

      {errorCarga !== '' && (
        <div
          role="alert"
          className="flex flex-wrap items-center gap-3 rounded-tarjeta border border-error bg-error-suave px-4 py-3 text-sm text-texto"
        >
          <span>{errorCarga}</span>
          <Button variante="secundario" tamano="sm" onClick={() => void cargar()}>
            {t('comun.reintentar')}
          </Button>
        </div>
      )}

      <TablaCatalogo
        datos={datos}
        cargando={cargando}
        categorias={categorias}
        filtros={filtros}
        busqueda={busqueda}
        onBusqueda={setBusqueda}
        onFiltros={cambiarFiltros}
        onLimpiar={limpiar}
        onPagina={setPagina}
        puedeEditar={puedeEditar}
        onEditar={(insumo) => {
          setEditando(insumo);
          setModalAbierto(true);
        }}
        onEliminar={setPorEliminar}
      />

      <ModalInsumo
        abierto={modalAbierto}
        insumo={editando}
        categorias={categorias}
        guardando={guardando}
        onGuardar={(valores) => void guardar(valores)}
        onCerrar={() => setModalAbierto(false)}
      />

      <DialogoConfirmacion
        abierto={porEliminar !== null}
        titulo={t('catalogo.confirmarEliminar')}
        mensaje={
          porEliminar === null
            ? ''
            : t('catalogo.confirmarEliminarDetalle', { nombre: porEliminar.nombre })
        }
        procesando={eliminando}
        onConfirmar={() => void confirmarEliminacion()}
        onCancelar={() => setPorEliminar(null)}
      />
    </div>
  );
}
