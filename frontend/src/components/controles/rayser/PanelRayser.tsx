'use client';

import { useCallback, useEffect, useState } from 'react';

import { FormularioRayser } from '@/components/controles/rayser/FormularioRayser';
import { TablaRayser } from '@/components/controles/rayser/TablaRayser';
import { Button } from '@/components/ui/Button';
import { DialogoConfirmacion } from '@/components/ui/DialogoConfirmacion';
import { useToast } from '@/components/ui/Toast';
import {
  ErrorDeApi,
  descargarExcelRayser,
  eliminarRegistroRayser,
  listarRayser,
  obtenerRangoRayser,
  registrarRayser,
} from '@/lib/api';
import { useIdioma } from '@/lib/i18n';
import type { RangoRayser, RegistroRayser } from '@/lib/types';
import { fechaDeHoy, formatearFechaIso, rangoDelMes } from '@/lib/utils';

/** Control de presiones: captura del día e historial del mes. */
export function PanelRayser() {
  const { t, locale } = useIdioma();
  const { mostrarToast } = useToast();

  const [rango, setRango] = useState<RangoRayser | null>(null);
  const [registros, setRegistros] = useState<RegistroRayser[]>([]);
  const [mes, setMes] = useState(() => fechaDeHoy().slice(0, 7));
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [descargando, setDescargando] = useState(false);
  const [errorCarga, setErrorCarga] = useState('');
  const [porEliminar, setPorEliminar] = useState<RegistroRayser | null>(null);
  const [eliminando, setEliminando] = useState(false);

  const hoy = fechaDeHoy();

  const cargar = useCallback(async () => {
    const { desde, hasta } = rangoDelMes(`${mes}-01`);

    try {
      setRegistros(await listarRayser(desde, hasta));
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

    obtenerRangoRayser()
      .then((datos) => {
        if (!cancelado) {
          setRango(datos);
        }
      })
      .catch(() => {
        if (!cancelado) {
          setErrorCarga(t('comun.errorGenerico'));
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
    lecturas: string[];
    observaciones: string;
    foto: File | null;
  }) {
    setGuardando(true);

    try {
      await registrarRayser({ fecha: hoy, ...datos });
      await cargar();
      mostrarToast(t('rayser.guardado'), 'exito');
    } catch (error) {
      mostrarToast(
        error instanceof ErrorDeApi ? error.message : t('comun.errorGenerico'),
        'error',
      );
      // Se relanza para que el formulario no limpie lo capturado: volver a
      // teclear cuatro lecturas por un error del servidor es inaceptable.
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
      await eliminarRegistroRayser(porEliminar.id);
      await cargar();
      mostrarToast(t('rayser.eliminado'), 'exito');
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
      await descargarExcelRayser(desde, hasta);
    } catch (error) {
      mostrarToast(
        error instanceof ErrorDeApi ? error.message : t('comun.errorGenerico'),
        'error',
      );
    } finally {
      setDescargando(false);
    }
  }

  const yaRegistrado = registros.some((registro) => registro.fecha === hoy);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-lg font-semibold text-texto">{t('rayser.titulo')}</h2>
      </div>

      {errorCarga && (
        <p
          role="alert"
          className="rounded-md border border-error bg-error-suave px-3 py-2 text-sm text-error"
        >
          {errorCarga}
        </p>
      )}

      {rango !== null &&
        (yaRegistrado ? (
          <div className="rounded-tarjeta border border-borde bg-fondo-elevado px-5 py-6">
            <p className="text-sm font-medium text-texto">
              {t('rayser.yaRegistrado', { fecha: formatearFechaIso(hoy, locale) })}
            </p>
            <p className="mt-1 text-sm text-texto-suave">
              {t('rayser.eliminarRegistro')}
            </p>
          </div>
        ) : (
          <FormularioRayser
            rango={rango}
            fecha={formatearFechaIso(hoy, locale)}
            onGuardar={guardar}
            guardando={guardando}
            onError={(mensaje) => mostrarToast(mensaje, 'error')}
          />
        ))}

      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-col gap-1.5">
          <label htmlFor="mes-rayser" className="text-sm font-medium text-texto">
            {t('rayser.mes')}
          </label>
          <input
            id="mes-rayser"
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
          disabled={registros.length === 0}
        >
          {t('rayser.descargarExcel')}
        </Button>
      </div>

      <div className="flex flex-col gap-3">
        <h3 className="text-base font-semibold text-texto">{t('rayser.historial')}</h3>

        {cargando ? (
          <p className="text-sm text-texto-suave">{t('comun.cargando')}</p>
        ) : (
          <TablaRayser
            registros={registros}
            onEliminar={setPorEliminar}
            totalManometros={rango?.manometros ?? 4}
          />
        )}
      </div>

      <DialogoConfirmacion
        abierto={porEliminar !== null}
        titulo={t('rayser.confirmarEliminar', {
          fecha: porEliminar ? formatearFechaIso(porEliminar.fecha, locale) : '',
        })}
        mensaje={t('rayser.confirmarEliminarDetalle')}
        procesando={eliminando}
        onConfirmar={() => void eliminar()}
        onCancelar={() => setPorEliminar(null)}
      />
    </div>
  );
}
