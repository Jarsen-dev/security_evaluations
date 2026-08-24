'use client';

import { useCallback, useEffect, useState } from 'react';

import { FormularioPlaticas } from '@/components/controles/platicas/FormularioPlaticas';
import { TablaPlaticas } from '@/components/controles/platicas/TablaPlaticas';
import { Button } from '@/components/ui/Button';
import { DialogoConfirmacion } from '@/components/ui/DialogoConfirmacion';
import { useToast } from '@/components/ui/Toast';
import {
  ErrorDeApi,
  descargarExcelPlaticas,
  eliminarPlatica,
  listarPlaticas,
  obtenerAreasPlaticas,
  registrarPlatica,
} from '@/lib/api';
import { useIdioma } from '@/lib/i18n';
import type { AreaPlatica, Platica } from '@/lib/types';
import { fechaDeHoy, formatearFechaIso, rangoDelMes } from '@/lib/utils';

/** Pestaña de pláticas diarias de seguridad. */
export function PanelPlaticas() {
  const { t, locale } = useIdioma();
  const { mostrarToast } = useToast();

  const [areas, setAreas] = useState<AreaPlatica[]>([]);
  const [platicas, setPlaticas] = useState<Platica[]>([]);
  const [mes, setMes] = useState(() => fechaDeHoy().slice(0, 7));
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [descargando, setDescargando] = useState(false);
  const [errorCarga, setErrorCarga] = useState('');
  const [porEliminar, setPorEliminar] = useState<Platica | null>(null);
  const [eliminando, setEliminando] = useState(false);

  const cargar = useCallback(async () => {
    const { desde, hasta } = rangoDelMes(`${mes}-01`);

    try {
      setPlaticas(await listarPlaticas(desde, hasta));
      setErrorCarga('');
    } catch (error) {
      setErrorCarga(
        error instanceof ErrorDeApi ? error.message : t('comun.errorGenerico'),
      );
    } finally {
      setCargando(false);
    }
  }, [mes, t]);

  useEffect(() => {
    let cancelado = false;

    // Las áreas de esta hoja son propias del formato, no las del cuestionario:
    // por eso vienen de su propio endpoint.
    obtenerAreasPlaticas()
      .then((datos) => {
        if (!cancelado) {
          setAreas(datos);
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
  }, [t]);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  async function guardar(datos: {
    fecha: string;
    tema: string;
    areas: string[];
    fotos: File[];
  }) {
    setGuardando(true);

    try {
      await registrarPlatica(datos);
      await cargar();
      mostrarToast(t('platicas.guardada'), 'exito');
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

  async function eliminar() {
    if (porEliminar === null) {
      return;
    }

    setEliminando(true);

    try {
      await eliminarPlatica(porEliminar.id);
      await cargar();
      mostrarToast(t('platicas.eliminada'), 'exito');
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

  async function descargar() {
    const { desde, hasta } = rangoDelMes(`${mes}-01`);
    setDescargando(true);

    try {
      await descargarExcelPlaticas(desde, hasta);
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
      {errorCarga && (
        <p
          role="alert"
          className="rounded-md border border-error bg-error-suave px-3 py-2 text-sm text-error"
        >
          {errorCarga}
        </p>
      )}

      <FormularioPlaticas
        areas={areas}
        onGuardar={guardar}
        guardando={guardando}
        onError={(mensaje) => mostrarToast(mensaje, 'error')}
      />

      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-col gap-1.5">
          <label htmlFor="mes-platicas" className="text-sm font-medium text-texto">
            {t('comun.mes')}
          </label>
          <input
            id="mes-platicas"
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
          disabled={platicas.length === 0}
        >
          {t('comun.descargarExcel')}
        </Button>
      </div>

      <div className="flex flex-col gap-3">
        <h3 className="text-base font-semibold text-texto">
          {t('platicas.historial')}
        </h3>

        {cargando ? (
          <p className="text-sm text-texto-suave">{t('comun.cargando')}</p>
        ) : (
          <TablaPlaticas platicas={platicas} onEliminar={setPorEliminar} />
        )}
      </div>

      <DialogoConfirmacion
        abierto={porEliminar !== null}
        titulo={t('platicas.confirmarEliminar', {
          fecha: porEliminar ? formatearFechaIso(porEliminar.fecha, locale) : '',
        })}
        mensaje={t('platicas.confirmarEliminarDetalle')}
        procesando={eliminando}
        onConfirmar={() => void eliminar()}
        onCancelar={() => setPorEliminar(null)}
      />
    </div>
  );
}
