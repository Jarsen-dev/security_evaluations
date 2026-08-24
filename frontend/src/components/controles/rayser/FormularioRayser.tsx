'use client';

import { useMemo, useState } from 'react';

import { CampoFotos } from '@/components/controles/CampoFotos';
import {
  CLASES_SEMAFORO,
  CLAVES_SEMAFORO,
  PUNTOS_SEMAFORO,
  clasificar,
} from '@/components/controles/rayser/semaforo';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Textarea } from '@/components/ui/Textarea';
import { useTraduccion } from '@/lib/i18n';
import type { RangoRayser } from '@/lib/types';
import { cn } from '@/lib/utils';

interface FormularioRayserProps {
  rango: RangoRayser;
  fecha: string;
  onGuardar: (datos: {
    lecturas: string[];
    observaciones: string;
    fotos: File[];
  }) => Promise<void>;
  guardando: boolean;
  onError: (mensaje: string) => void;
}

/** Tope de fotos de evidencia; el servidor aplica el mismo. */
const MAX_FOTOS_RAYSER = 4;

/** Cuántos manómetros trae el equipo; lo dice el backend. */
function lecturasVacias(total: number): string[] {
  return Array.from({ length: total }, () => '');
}

export function FormularioRayser({
  rango,
  fecha,
  onGuardar,
  guardando,
  onError,
}: FormularioRayserProps) {
  const t = useTraduccion();

  const minimo = Number(rango.minimo);
  const maximo = Number(rango.maximo);

  const [lecturas, setLecturas] = useState<string[]>(() =>
    lecturasVacias(rango.manometros),
  );
  const [observaciones, setObservaciones] = useState('');
  const [fotos, setFotos] = useState<File[]>([]);

  const semaforos = useMemo(
    () => lecturas.map((lectura) => clasificar(lectura, minimo, maximo)),
    [lecturas, minimo, maximo],
  );

  const completas = lecturas.every((lectura) => lectura.trim() !== '');
  const hayAlerta = semaforos.some((estado) => estado !== null && estado !== 'verde');

  // Una lectura fuera de rango sin evidencia no sirve para dar seguimiento:
  // el servidor la rechaza y aquí se bloquea antes de intentarlo.
  const faltaEvidencia = hayAlerta && (fotos.length === 0 || observaciones.trim() === '');
  const puedeGuardar = completas && !faltaEvidencia;

  function actualizar(indice: number, valor: string) {
    setLecturas((previas) =>
      previas.map((lectura, posicion) => (posicion === indice ? valor : lectura)),
    );
  }

  async function guardar() {
    if (!puedeGuardar) {
      return;
    }

    try {
      await onGuardar({ lecturas, observaciones, fotos });
    } catch {
      // El panel ya avisó del error. No se limpia el formulario: volver a
      // teclear las cuatro lecturas por un fallo del servidor es inaceptable.
      return;
    }

    setLecturas(lecturasVacias(rango.manometros));
    setObservaciones('');
    setFotos([]);
  }

  return (
    <Card className="flex flex-col gap-5">
      <div>
        <h2 className="text-base font-semibold text-texto">
          {t('rayser.registroDelDia')}
        </h2>
        <p className="mt-1 text-sm text-texto-suave">
          {t('rayser.descripcion', { normal: rango.normal })}
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {lecturas.map((lectura, indice) => {
          const estado = semaforos[indice] ?? null;
          const idCampo = `manometro-${indice + 1}`;

          return (
            <div key={idCampo} className="flex flex-col gap-1.5">
              <label htmlFor={idCampo} className="text-sm font-medium text-texto">
                {t('rayser.manometro', { numero: indice + 1 })}
              </label>

              <div className="relative">
                <input
                  id={idCampo}
                  // `decimal` abre el teclado numérico del celular con punto,
                  // que es lo que se captura en planta.
                  inputMode="decimal"
                  value={lectura}
                  placeholder={t('rayser.placeholderLectura')}
                  onChange={(evento) => actualizar(indice, evento.target.value)}
                  disabled={guardando}
                  className={cn(
                    'h-tactil w-full rounded-md border bg-fondo px-3 pr-10 text-base text-texto',
                    'placeholder:text-texto-tenue disabled:cursor-not-allowed disabled:opacity-50',
                    estado === null
                      ? 'border-borde focus:border-primario'
                      : CLASES_SEMAFORO[estado],
                  )}
                />

                {estado !== null && (
                  <span
                    aria-hidden="true"
                    className={cn(
                      'absolute right-3 top-1/2 h-3 w-3 -translate-y-1/2 rounded-full',
                      PUNTOS_SEMAFORO[estado],
                    )}
                  />
                )}
              </div>

              {/* El color nunca es la única señal: se rotula el estado. */}
              <p className="text-xs text-texto-tenue">
                {estado === null
                  ? t('rayser.rangoNormal', { minimo: rango.minimo, maximo: rango.maximo })
                  : t(CLAVES_SEMAFORO[estado])}
              </p>
            </div>
          );
        })}
      </div>

      {hayAlerta && (
        <div className="flex flex-col gap-4 rounded-md border border-alerta bg-alerta-suave p-4">
          <div>
            <p className="text-sm font-semibold text-alerta">
              {t('rayser.evidenciaTitulo')}
            </p>
            <p className="mt-1 text-sm text-texto-suave">
              {t('rayser.evidenciaDetalle')}
            </p>
          </div>

          <Textarea
            etiqueta={t('comun.observaciones')}
            name="observaciones-rayser"
            value={observaciones}
            placeholder={t('rayser.observacionesPlaceholder')}
            onChange={(evento) => setObservaciones(evento.target.value)}
            disabled={guardando}
          />

          <CampoFotos
            id="fotos-rayser"
            fotos={fotos}
            onCambiar={setFotos}
            onError={onError}
            maximo={MAX_FOTOS_RAYSER}
            deshabilitado={guardando}
          />
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-texto-tenue">
          {!completas
            ? t('rayser.faltanLecturas')
            : faltaEvidencia && observaciones.trim() === ''
              ? t('rayser.faltaObservaciones')
              : faltaEvidencia
                ? t('rayser.faltaFoto')
                : `${t('comun.fecha')}: ${fecha}`}
        </p>

        <Button
          tamano="lg"
          onClick={() => void guardar()}
          disabled={!puedeGuardar}
          cargando={guardando}
        >
          {t('rayser.terminarRegistro')}
        </Button>
      </div>
    </Card>
  );
}
