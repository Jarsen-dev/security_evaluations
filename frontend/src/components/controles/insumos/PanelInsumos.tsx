'use client';

import { useCallback, useEffect, useState } from 'react';

import { FormularioInsumos } from '@/components/controles/insumos/FormularioInsumos';
import { TablaInsumos } from '@/components/controles/insumos/TablaInsumos';
import { Button } from '@/components/ui/Button';
import { useToast } from '@/components/ui/Toast';
import {
  ErrorDeApi,
  descargarExcelControlInsumos,
  listarControlInsumos,
  obtenerCatalogoControlInsumos,
  registrarControlInsumo,
} from '@/lib/api';
import { bilingue, useTraduccion } from '@/lib/i18n';
import type {
  CatalogoControlInsumos,
  ControlInsumoPayload,
  RegistroControlInsumo,
} from '@/lib/types';
import { fechaDeHoy, rangoDelMes } from '@/lib/utils';

/**
 * Control de Insumos: las salidas del almacén.
 *
 * Es el único control que **mueve datos de otro módulo**: al registrar una
 * entrega baja la existencia del catálogo. Por eso el historial se recarga
 * después de guardar —el stock que enseña el desplegable ya cambió— y por eso
 * la pantalla avisa de que el registro no se puede deshacer desde aquí.
 */
export function PanelInsumos() {
  const t = useTraduccion();
  const { mostrarToast } = useToast();

  const [catalogo, setCatalogo] = useState<CatalogoControlInsumos | null>(null);
  const [registros, setRegistros] = useState<RegistroControlInsumo[]>([]);
  const [mes, setMes] = useState(() => fechaDeHoy().slice(0, 7));
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [descargando, setDescargando] = useState(false);
  const [errorCarga, setErrorCarga] = useState('');

  function fallo(error: unknown) {
    mostrarToast(
      error instanceof ErrorDeApi ? error.message : t('comun.errorGenerico'),
      'error',
    );
  }

  // El catálogo se pide una sola vez: son constantes del backend.
  useEffect(() => {
    obtenerCatalogoControlInsumos()
      .then(setCatalogo)
      .catch((error: unknown) => {
        setErrorCarga(
          error instanceof ErrorDeApi ? error.message : t('comun.errorGenerico'),
        );
      });
  }, [t]);

  const cargar = useCallback(async () => {
    const { desde, hasta } = rangoDelMes(`${mes}-01`);
    setCargando(true);
    try {
      setRegistros(await listarControlInsumos(desde, hasta));
      setErrorCarga('');
    } catch (error: unknown) {
      setErrorCarga(
        error instanceof ErrorDeApi ? error.message : t('comun.errorGenerico'),
      );
    } finally {
      setCargando(false);
    }
  }, [mes, t]);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  async function guardar(datos: ControlInsumoPayload) {
    setGuardando(true);
    try {
      await registrarControlInsumo(datos);
      await cargar();
      mostrarToast(t('controlInsumos.guardado'), 'exito');
    } catch (error: unknown) {
      fallo(error);
      // Se relanza para que el formulario no se limpie: lo capturado sigue
      // sirviendo en cuanto se corrija el consumo o la existencia.
      throw error;
    } finally {
      setGuardando(false);
    }
  }

  async function descargar() {
    const { desde, hasta } = rangoDelMes(`${mes}-01`);
    setDescargando(true);
    try {
      await descargarExcelControlInsumos(desde, hasta);
    } catch (error: unknown) {
      fallo(error);
    } finally {
      setDescargando(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-base font-semibold text-texto">
          {bilingue(t('controlInsumos.titulo'))}
        </h2>
        <p className="mt-1 text-sm text-texto-suave">
          {bilingue(t('controlInsumos.descripcion'))}
        </p>
      </div>

      {errorCarga !== '' && (
        <p
          role="alert"
          className="rounded-md border border-error bg-error-suave px-3 py-2 text-sm text-error"
        >
          {errorCarga}
        </p>
      )}

      {catalogo !== null && (
        <FormularioInsumos
          areas={catalogo.areas}
          unidadesParciales={catalogo.unidades_parciales}
          guardando={guardando}
          onGuardar={guardar}
        />
      )}

      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-col gap-1.5">
          <label htmlFor="mes-insumos" className="text-sm font-medium text-texto">
            {bilingue(t('comun.mes'))}
          </label>
          <input
            id="mes-insumos"
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
          {bilingue(t('comun.descargarExcel'))}
        </Button>
      </div>

      <div className="flex flex-col gap-3">
        <div>
          <h3 className="text-base font-semibold text-texto">
            {bilingue(t('controlInsumos.historial'))}
          </h3>
          <p className="mt-1 text-sm text-texto-tenue">
            {bilingue(t('controlInsumos.inmutable'))}
          </p>
        </div>

        {cargando ? (
          <p className="text-sm text-texto-suave">{bilingue(t('comun.cargando'))}</p>
        ) : (
          <TablaInsumos registros={registros} />
        )}
      </div>
    </div>
  );
}
