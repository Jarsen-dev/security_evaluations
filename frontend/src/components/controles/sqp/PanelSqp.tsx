'use client';

import { useCallback, useEffect, useState } from 'react';

import { FormularioSqp } from '@/components/controles/sqp/FormularioSqp';
import { TablaInspeccionesSqp } from '@/components/controles/sqp/TablaInspeccionesSqp';
import { useToast } from '@/components/ui/Toast';
import {
  ErrorDeApi,
  descargarExcelSqp,
  listarInspeccionesSqp,
  obtenerAreas,
  obtenerCatalogoSqp,
  registrarInspeccionSqp,
} from '@/lib/api';
import { useTraduccion } from '@/lib/i18n';
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

  const [catalogo, setCatalogo] = useState<CatalogoSqp | null>(null);
  const [areas, setAreas] = useState<Area[]>([]);
  const [inspecciones, setInspecciones] = useState<InspeccionSqpResumen[]>([]);
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [descargandoId, setDescargandoId] = useState<string | null>(null);
  const [errorCarga, setErrorCarga] = useState('');

  const cargarInspecciones = useCallback(async () => {
    setInspecciones(await listarInspeccionesSqp());
  }, []);

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

  async function guardar(datos: InspeccionSqpPayload) {
    setGuardando(true);

    try {
      await registrarInspeccionSqp(datos);
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
        <h2 className="text-lg font-semibold text-texto">{t('sqp.titulo')}</h2>
        {catalogo !== null && (
          <p className="mt-1 text-sm text-texto-suave">
            {t('sqp.descripcion', { total: catalogo.puntos.length })}
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
        <p className="text-sm text-texto-suave">{t('comun.cargando')}</p>
      ) : (
        catalogo !== null && (
          <FormularioSqp
            catalogo={catalogo}
            areas={areas}
            onGuardar={guardar}
            guardando={guardando}
          />
        )
      )}

      <div className="flex flex-col gap-3">
        <h3 className="text-base font-semibold text-texto">{t('sqp.historial')}</h3>
        <TablaInspeccionesSqp
          inspecciones={inspecciones}
          onDescargar={(inspeccion) => void descargar(inspeccion)}
          descargandoId={descargandoId}
        />
      </div>
    </div>
  );
}
