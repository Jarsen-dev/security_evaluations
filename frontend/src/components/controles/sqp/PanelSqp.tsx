'use client';

import { useCallback, useEffect, useState } from 'react';

import { ModalCierreHallazgo } from '@/components/controles/ModalCierreHallazgo';
import { ModalDetalleRegistro } from '@/components/controles/ModalDetalleRegistro';
import { FormularioSqp } from '@/components/controles/sqp/FormularioSqp';
import { TablaInspeccionesSqp } from '@/components/controles/sqp/TablaInspeccionesSqp';
import { useToast } from '@/components/ui/Toast';
import {
  ErrorDeApi,
  descargarExcelSqp,
  listarIncidencias,
  listarInspeccionesSqp,
  obtenerAreas,
  obtenerCatalogoSqp,
  registrarInspeccionSqp,
} from '@/lib/api';
import { bilingue, useTraduccion } from '@/lib/i18n';
import type {
  Area,
  CatalogoSqp,
  InspeccionSqpPayload,
  InspeccionSqpResumen,
} from '@/lib/types';

/** Inspección de sustancias químicas peligrosas: captura e historial. */
export function PanelSqp() {
  const t = useTraduccion();
  const { mostrarToast } = useToast();

  // Qué hojas ya tienen cierre, para pintar el botón de la columna.
  const [cerrados, setCerrados] = useState<ReadonlySet<string>>(new Set());
  const [detalleId, setDetalleId] = useState<string | null>(null);
  const [cierreId, setCierreId] = useState<string | null>(null);

  const [catalogo, setCatalogo] = useState<CatalogoSqp | null>(null);
  const [areas, setAreas] = useState<Area[]>([]);
  const [inspecciones, setInspecciones] = useState<InspeccionSqpResumen[]>([]);
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [descargandoId, setDescargandoId] = useState<string | null>(null);
  const [errorCarga, setErrorCarga] = useState('');

  const cargarInspecciones = useCallback(async () => {
    const lista = await listarInspeccionesSqp();
    setInspecciones(lista);
    await cargarCierres(lista);
  }, []);

  /**
   * Qué inspecciones ya tienen cierre.
   *
   * El historial de SQP no se filtra por fechas, así que el rango se deduce de
   * lo que se está mostrando: preguntar por un periodo fijo dejaría fuera las
   * inspecciones viejas que siguen en la tabla.
   */
  const cargarCierres = useCallback(
    async (lista: InspeccionSqpResumen[]) => {
      if (lista.length === 0) {
        setCerrados(new Set());
        return;
      }

      const fechas = lista.map((inspeccion) => inspeccion.fecha).sort();

      try {
        const incidencias = await listarIncidencias({
          desde: fechas[0] as string,
          hasta: fechas[fechas.length - 1] as string,
          control: 'sqp',
          estado: 'cerrado',
        });
        setCerrados(new Set(incidencias.map((i) => i.registro_id)));
      } catch {
        // Sin esto la tabla solo pierde la marca de "cerrado"; no vale la
        // pena romper el historial completo por ello.
        setCerrados(new Set());
      }
    },
    [],
  );

  useEffect(() => {
    let cancelado = false;

    // El catálogo de puntos y el de áreas viven en el backend: el frontend
    // nunca los tiene escritos a mano.
    Promise.all([obtenerCatalogoSqp(), obtenerAreas(), listarInspeccionesSqp()])
      .then(([puntos, listaAreas, historial]) => {
        if (cancelado) {
          return;
        }
        setCatalogo(puntos);
        setAreas(listaAreas);
        setInspecciones(historial);
        void cargarCierres(historial);
      })
      .catch((error: unknown) => {
        if (!cancelado) {
          setErrorCarga(
            error instanceof ErrorDeApi ? error.message : t('comun.errorGenerico'),
          );
        }
      })
      .finally(() => {
        if (!cancelado) {
          setCargando(false);
        }
      });

    return () => {
      cancelado = true;
    };
  }, [t]);

  async function guardar(
    datos: InspeccionSqpPayload,
    fotos: Record<number, File[]>,
  ) {
    setGuardando(true);

    try {
      await registrarInspeccionSqp(datos, fotos);
      await cargarInspecciones();
      mostrarToast(t('sqp.guardada'), 'exito');
    } catch (error) {
      mostrarToast(
        error instanceof ErrorDeApi ? error.message : t('comun.errorGenerico'),
        'error',
      );
      // Se relanza para que el formulario conserve lo capturado.
      throw error;
    } finally {
      setGuardando(false);
    }
  }

  async function descargar(inspeccion: InspeccionSqpResumen) {
    setDescargandoId(inspeccion.id);

    try {
      await descargarExcelSqp(inspeccion.id);
    } catch (error) {
      mostrarToast(
        error instanceof ErrorDeApi ? error.message : t('comun.errorGenerico'),
        'error',
      );
    } finally {
      setDescargandoId(null);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-lg font-semibold text-texto">{bilingue(t('sqp.titulo'))}</h2>
        {catalogo !== null && (
          <p className="mt-1 text-sm text-texto-suave">
            {bilingue(t('sqp.descripcion', { total: catalogo.puntos.length }))}
          </p>
        )}
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
        catalogo !== null && (
          <FormularioSqp
            catalogo={catalogo}
            areas={areas}
            onGuardar={guardar}
            onError={(mensaje) => mostrarToast(mensaje, 'error')}
            guardando={guardando}
          />
        )
      )}

      <div className="flex flex-col gap-3">
        <h3 className="text-base font-semibold text-texto">{bilingue(t('sqp.historial'))}</h3>
        <TablaInspeccionesSqp
            onVerDetalle={(registro) => setDetalleId(registro.id)}
            onCerrarHallazgo={(registro) => setCierreId(registro.id)}
            cerrados={cerrados}
          inspecciones={inspecciones}
          onDescargar={(inspeccion) => void descargar(inspeccion)}
          descargandoId={descargandoId}
        />
      </div>

      <ModalDetalleRegistro
        abierto={detalleId !== null}
        control="sqp"
        registroId={detalleId}
        onCerrar={() => setDetalleId(null)}
        onError={(mensaje) => mostrarToast(mensaje, 'error')}
      />

      <ModalCierreHallazgo
        abierto={cierreId !== null}
        control="sqp"
        registroId={cierreId}
        onCerrar={() => setCierreId(null)}
        onGuardado={(mensaje) => {
          mostrarToast(mensaje, 'exito');
          void cargarInspecciones();
        }}
        onError={(mensaje) => mostrarToast(mensaje, 'error')}
      />
    </div>
  );
}
