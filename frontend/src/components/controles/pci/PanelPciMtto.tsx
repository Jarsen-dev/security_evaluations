'use client';

import { useCallback, useEffect, useState } from 'react';

import { FormularioPciMtto } from '@/components/controles/pci/FormularioPciMtto';
import { ModalDetallePciMtto } from '@/components/controles/pci/ModalDetallePciMtto';
import { SolicitudUrgente } from '@/components/controles/pci/SolicitudUrgente';
import { TablaPciMtto } from '@/components/controles/pci/TablaPciMtto';
import { Card } from '@/components/ui/Card';
import { Modal } from '@/components/ui/Modal';
import { useToast } from '@/components/ui/Toast';
import {
  ErrorDeApi,
  corregirPciMtto,
  descargarExcelPciMtto,
  descargarReportePciMtto,
  guardarMotivoPciMtto,
  listarPciMtto,
  registrarPciMtto,
} from '@/lib/api';
import { avisarCambioDeAvisos } from '@/lib/avisos';
import { bilingue, unaLinea, useIdioma } from '@/lib/i18n';
import { useSesion } from '@/lib/sesion';
import type { CapturaPciMtto, ListadoPciMtto, RegistroPciMtto } from '@/lib/types';
import { Button } from '@/components/ui/Button';

const CLASES_CAMPO =
  'h-10 rounded-md border border-borde bg-fondo px-3 text-sm text-texto focus:border-primario';

/** Cuántos años hacia atrás ofrece el filtro cuando la tabla está vacía. */
const ANIOS_DE_RESPALDO = 3;

export function PanelPciMtto() {
  const { t, locale } = useIdioma();
  const { mostrarToast } = useToast();
  const { puede } = useSesion();

  const anioActual = new Date().getFullYear();
  const mesActual = new Date().getMonth() + 1;

  const [anio, setAnio] = useState(anioActual);
  const [datos, setDatos] = useState<ListadoPciMtto | null>(null);
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [descargando, setDescargando] = useState<string | null>(null);
  const [descargandoExcel, setDescargandoExcel] = useState(false);
  const [errorCarga, setErrorCarga] = useState('');
  const [detalle, setDetalle] = useState<RegistroPciMtto | null>(null);
  const [corrigiendo, setCorrigiendo] = useState<RegistroPciMtto | null>(null);

  const puedeEditar = puede('controles', 'editar');

  const cargar = useCallback(async () => {
    try {
      setDatos(await listarPciMtto(anio));
      setErrorCarga('');
    } catch (error) {
      setErrorCarga(
        error instanceof ErrorDeApi ? error.message : t('comun.errorGenerico'),
      );
    } finally {
      setCargando(false);
    }
  }, [anio, t]);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  function fallo(error: unknown) {
    mostrarToast(
      error instanceof ErrorDeApi ? error.message : t('comun.errorGenerico'),
      'error',
    );
  }

  async function guardar(captura: CapturaPciMtto) {
    setGuardando(true);
    try {
      await registrarPciMtto(captura);
      await cargar();
      // La campana muestra los meses sin explicar: puede haber cambiado.
      avisarCambioDeAvisos();
      mostrarToast(t('pciMtto.guardado'), 'exito');
    } catch (error) {
      fallo(error);
    } finally {
      setGuardando(false);
    }
  }

  async function corregir(captura: CapturaPciMtto, conservaReporte: boolean) {
    setGuardando(true);
    try {
      await corregirPciMtto(captura, conservaReporte);
      await cargar();
      avisarCambioDeAvisos();
      setCorrigiendo(null);
      mostrarToast(t('pciMtto.guardado'), 'exito');
    } catch (error) {
      fallo(error);
    } finally {
      setGuardando(false);
    }
  }

  async function justificar(anioMes: number, mes: number, motivo: string) {
    setGuardando(true);
    try {
      await guardarMotivoPciMtto(anioMes, mes, motivo, false);
      await cargar();
      avisarCambioDeAvisos();
      mostrarToast(t('pciMtto.motivoGuardado'), 'exito');
    } catch (error) {
      fallo(error);
    } finally {
      setGuardando(false);
    }
  }

  async function bajarReporte(registro: RegistroPciMtto) {
    setDescargando(registro.id);
    try {
      await descargarReportePciMtto(registro.anio, registro.mes);
    } catch (error) {
      fallo(error);
    } finally {
      setDescargando(null);
    }
  }

  async function bajarExcel() {
    setDescargandoExcel(true);
    try {
      await descargarExcelPciMtto(anio);
    } catch (error) {
      fallo(error);
    } finally {
      setDescargandoExcel(false);
    }
  }

  const registros = datos?.registros ?? [];
  const delMesActual = registros.find(
    (registro) => registro.anio === anioActual && registro.mes === mesActual,
  );

  // El control puede estrenarse a mitad de año: hasta que llegue su primer mes
  // no hay nada que capturar, y ofrecer el formulario solo conseguiría que el
  // servidor lo rechazara con un 422.
  const primero = datos?.primer_mes ?? null;
  const yaArranco =
    primero === null ||
    anioActual > primero.anio ||
    (anioActual === primero.anio && mesActual >= primero.mes);

  // El filtro ofrece los años con registros más el actual, para que la pestaña
  // sea usable el primer día, cuando todavía no hay nada guardado.
  const aniosDisponibles = Array.from(
    new Set([
      ...(datos?.anios ?? []),
      anioActual,
      ...Array.from({ length: ANIOS_DE_RESPALDO }, (_, i) => anioActual - i),
    ]),
  ).sort((a, b) => b - a);

  const nombreMesActual = new Intl.DateTimeFormat(locale, {
    month: 'long',
    year: 'numeric',
  }).format(new Date(anioActual, mesActual - 1, 1));

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-base font-semibold text-texto">
          {bilingue(t('pciMtto.titulo'))}
        </h2>
        <p className="mt-1 text-sm text-texto-suave">
          {bilingue(t('pciMtto.descripcion'))}
        </p>
      </div>

      {errorCarga && (
        <p
          role="alert"
          className="rounded-md border border-error bg-error-suave px-3 py-2 text-sm text-error"
        >
          {errorCarga}
        </p>
      )}

      <SolicitudUrgente
        pendientes={datos?.pendientes ?? []}
        onGuardar={justificar}
        guardando={guardando}
      />

      {!yaArranco && primero !== null ? (
        <Card>
          <p className="text-sm text-texto-suave">
            {bilingue(
              t('pciMtto.aunNoArranca', {
                mes: new Intl.DateTimeFormat(locale, {
                  month: 'long',
                  year: 'numeric',
                }).format(new Date(primero.anio, primero.mes - 1, 1)),
              }),
            )}
          </p>
        </Card>
      ) : delMesActual === undefined ? (
        <FormularioPciMtto
          anio={anioActual}
          mes={mesActual}
          onGuardar={(captura) => guardar(captura)}
          guardando={guardando}
          onError={(mensaje) => mostrarToast(mensaje, 'error')}
        />
      ) : (
        <Card>
          <p className="text-sm font-medium text-texto">
            {bilingue(t('pciMtto.yaRegistrado', { mes: nombreMesActual }))}
          </p>
          <p className="mt-1 text-sm text-texto-suave">
            {bilingue(t('pciMtto.yaRegistradoDetalle'))}
          </p>
        </Card>
      )}

      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-col gap-1.5">
          <label htmlFor="pci-anio" className="text-sm font-medium text-texto">
            {bilingue(t('pciMtto.anio'))}
          </label>
          <select
            id="pci-anio"
            value={anio}
            onChange={(evento) => setAnio(Number(evento.target.value))}
            className={CLASES_CAMPO}
          >
            {aniosDisponibles.map((valor) => (
              <option key={valor} value={valor}>
                {valor}
              </option>
            ))}
          </select>
        </div>

        <Button
          variante="secundario"
          onClick={() => void bajarExcel()}
          cargando={descargandoExcel}
          disabled={registros.length === 0}
        >
          {bilingue(t('comun.descargarExcel'))}
        </Button>
      </div>

      <div className="flex flex-col gap-3">
        <h3 className="text-base font-semibold text-texto">
          {bilingue(t('pciMtto.registros'))}
        </h3>

        {cargando ? (
          <p className="text-sm text-texto-suave">{bilingue(t('comun.cargando'))}</p>
        ) : (
          <TablaPciMtto
            registros={registros}
            onVerDetalle={setDetalle}
            onCorregir={setCorrigiendo}
            onDescargar={(registro) => void bajarReporte(registro)}
            descargando={descargando}
            puedeEditar={puedeEditar}
          />
        )}
      </div>

      <ModalDetallePciMtto registro={detalle} onCerrar={() => setDetalle(null)} />

      <Modal
        abierto={corrigiendo !== null}
        onCerrar={() => setCorrigiendo(null)}
        titulo={
          corrigiendo === null
            ? ''
            : t('pciMtto.corregirTitulo', {
                mes: new Intl.DateTimeFormat(locale, {
                  month: 'long',
                  year: 'numeric',
                }).format(
                  new Date(corrigiendo.anio, corrigiendo.mes - 1, 1),
                ),
              })
        }
        descripcion={unaLinea(t('pciMtto.corregirDetalle'))}
        ancho="lg"
      >
        {corrigiendo !== null && (
          <FormularioPciMtto
            // Remonta el formulario al cambiar de mes: si no, conservaría lo
            // capturado del registro anterior.
            key={corrigiendo.id}
            anio={corrigiendo.anio}
            mes={corrigiendo.mes}
            actual={corrigiendo}
            onGuardar={corregir}
            guardando={guardando}
            onError={(mensaje) => mostrarToast(mensaje, 'error')}
          />
        )}
      </Modal>
    </div>
  );
}
