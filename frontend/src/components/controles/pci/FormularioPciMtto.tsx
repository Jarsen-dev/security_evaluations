'use client';

import { useState } from 'react';

import { CampoFotos } from '@/components/controles/CampoFotos';
import { CampoReporte } from '@/components/controles/pci/CampoReporte';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import { Textarea } from '@/components/ui/Textarea';
import { bilingue, unaLinea, useIdioma } from '@/lib/i18n';
import type { CapturaPciMtto, RegistroPciMtto } from '@/lib/types';
import { cn, fechaDeHoy } from '@/lib/utils';

/** El mismo tope que el resto de los controles, y el que impone el servidor. */
const MAX_FOTOS = 4;

interface FormularioPciMttoProps {
  anio: number;
  mes: number;
  /** Al corregir, el registro que ya existe. */
  actual?: RegistroPciMtto | null;
  onGuardar: (datos: CapturaPciMtto, conservaReporte: boolean) => Promise<void>;
  guardando: boolean;
  onError: (mensaje: string) => void;
}

export function FormularioPciMtto({
  anio,
  mes,
  actual = null,
  onGuardar,
  guardando,
  onError,
}: FormularioPciMttoProps) {
  const { t, locale } = useIdioma();

  const [realizado, setRealizado] = useState<boolean | null>(
    actual !== null ? actual.realizado : null,
  );
  const [fecha, setFecha] = useState(actual?.fecha ?? fechaDeHoy);
  const [motivo, setMotivo] = useState(actual?.motivo ?? '');
  const [fotos, setFotos] = useState<File[]>([]);
  const [reporte, setReporte] = useState<File | null>(null);
  // Al corregir sin tocar el adjunto, el que ya estaba sigue contando.
  const [conservaReporte, setConservaReporte] = useState(
    actual?.tiene_reporte ?? false,
  );

  const hayReporte = reporte !== null || conservaReporte;
  const puedeGuardar =
    realizado === true
      ? fecha !== '' && fotos.length > 0 && hayReporte
      : realizado === false && motivo.trim() !== '';

  const nombreMes = new Intl.DateTimeFormat(locale, {
    month: 'long',
    year: 'numeric',
  }).format(new Date(anio, mes - 1, 1));

  function elegir(valor: boolean) {
    setRealizado(valor);
    // Lo capturado en la otra rama deja de aplicar: el servidor lo rechazaría.
    if (valor) {
      setMotivo('');
    } else {
      setFotos([]);
      setReporte(null);
      setConservaReporte(false);
    }
  }

  async function guardar() {
    if (!puedeGuardar || realizado === null) {
      return;
    }

    await onGuardar(
      {
        anio,
        mes,
        realizado,
        fecha,
        motivo: motivo.trim(),
        fotos,
        reporte,
      },
      conservaReporte && reporte === null,
    );
  }

  /** El aviso de lo que falta, que también explica por qué el botón no se activa. */
  const pendiente =
    realizado === null
      ? null
      : realizado
        ? fecha === ''
          ? t('pciMtto.faltaFecha')
          : !hayReporte
            ? t('pciMtto.faltaReporte')
            : fotos.length === 0
              ? t('pciMtto.faltaEvidencia')
              : t('pciMtto.listo')
        : motivo.trim() === ''
          ? t('pciMtto.faltaMotivo')
          : t('pciMtto.listo');

  return (
    <Card className="flex flex-col gap-5">
      <div>
        <h2 className="text-base font-semibold text-texto">
          {bilingue(t('pciMtto.pregunta'))}
        </h2>
        <p className="mt-1 text-sm text-texto-suave">
          {bilingue(t('pciMtto.periodo'))}
          {': '}
          <span className="font-medium text-texto">{nombreMes}</span>
        </p>
      </div>

      <div className="flex flex-wrap gap-3">
        {[true, false].map((valor) => {
          const activo = realizado === valor;
          return (
            <button
              key={String(valor)}
              type="button"
              role="radio"
              aria-checked={activo}
              onClick={() => elegir(valor)}
              disabled={guardando}
              className={cn(
                'min-h-tactil w-40 rounded-md border px-4 py-2 text-sm font-semibold',
                'transition-colors disabled:cursor-not-allowed disabled:opacity-50',
                activo
                  ? valor
                    ? 'border-exito bg-exito-suave text-exito'
                    : 'border-error bg-error-suave text-error'
                  : 'border-borde text-texto-suave hover:border-borde-fuerte hover:text-texto',
              )}
            >
              {bilingue(valor ? t('comun.si') : t('comun.no'))}
            </button>
          );
        })}
      </div>

      {realizado === true && (
        <div className="flex flex-col gap-5">
          <div className="sm:max-w-xs">
            <Input
              etiqueta={t('pciMtto.fecha')}
              name="fecha-pci"
              type="date"
              value={fecha}
              onChange={(evento) => setFecha(evento.target.value)}
              disabled={guardando}
            />
          </div>

          <CampoReporte
            id="reporte-pci"
            reporte={reporte}
            onCambiar={(archivo) => {
              setReporte(archivo);
              if (archivo !== null) {
                setConservaReporte(false);
              }
            }}
            onError={onError}
            nombreGuardado={conservaReporte ? actual?.reporte_nombre : null}
            deshabilitado={guardando}
          />

          <CampoFotos
            id="fotos-pci"
            fotos={fotos}
            onCambiar={setFotos}
            onError={onError}
            maximo={MAX_FOTOS}
            deshabilitado={guardando}
          />
        </div>
      )}

      {realizado === false && (
        <Textarea
          etiqueta={t('pciMtto.motivo')}
          name="motivo-pci"
          rows={3}
          value={motivo}
          placeholder={unaLinea(t('pciMtto.motivoPlaceholder'))}
          onChange={(evento) => setMotivo(evento.target.value)}
          disabled={guardando}
          maxLength={2000}
        />
      )}

      {realizado !== null && (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-texto-tenue">{bilingue(pendiente ?? '')}</p>

          <Button
            tamano="lg"
            onClick={() => void guardar()}
            disabled={!puedeGuardar}
            cargando={guardando}
          >
            {bilingue(t('checklist.confirmar'))}
          </Button>
        </div>
      )}
    </Card>
  );
}
