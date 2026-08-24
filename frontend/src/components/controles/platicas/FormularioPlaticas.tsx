'use client';

import { useState } from 'react';

import { CampoFotos } from '@/components/controles/CampoFotos';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import { useTraduccion } from '@/lib/i18n';
import type { AreaPlatica } from '@/lib/types';
import { cn, fechaDeHoy } from '@/lib/utils';

/** Tope de fotos por plática; el servidor aplica el mismo. */
const MAX_FOTOS = 4;

interface FormularioPlaticasProps {
  areas: AreaPlatica[];
  onGuardar: (datos: {
    fecha: string;
    tema: string;
    areas: string[];
    fotos: File[];
  }) => Promise<void>;
  guardando: boolean;
  onError: (mensaje: string) => void;
}

/**
 * Captura de una plática: primero el tema, luego las áreas, luego la foto.
 *
 * Los pasos se habilitan en cadena a propósito: en piso la plática se registra
 * mientras se está dando, y el orden de los campos es el orden en que ocurren
 * las cosas.
 */
export function FormularioPlaticas({
  areas,
  onGuardar,
  guardando,
  onError,
}: FormularioPlaticasProps) {
  const t = useTraduccion();

  const [fecha, setFecha] = useState(fechaDeHoy);
  const [tema, setTema] = useState('');
  const [elegidas, setElegidas] = useState<string[]>([]);
  const [fotos, setFotos] = useState<File[]>([]);

  const hayTema = tema.trim() !== '';
  const hayAreas = elegidas.length > 0;
  const puedeGuardar = hayTema && hayAreas && fotos.length > 0;

  function alternar(clave: string) {
    setElegidas((previas) =>
      previas.includes(clave)
        ? previas.filter((otra) => otra !== clave)
        : [...previas, clave],
    );
  }

  async function guardar() {
    if (!puedeGuardar) {
      return;
    }

    try {
      await onGuardar({ fecha, tema: tema.trim(), areas: elegidas, fotos });
    } catch {
      // El panel ya avisó del error; se conserva lo capturado.
      return;
    }

    setTema('');
    setElegidas([]);
    setFotos([]);
  }

  return (
    <Card className="flex flex-col gap-5">
      <div>
        <h2 className="text-base font-semibold text-texto">
          {t('platicas.registrar')}
        </h2>
        <p className="mt-1 text-sm text-texto-suave">{t('platicas.descripcion')}</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-[12rem_1fr]">
        <Input
          etiqueta={t('comun.fecha')}
          name="fecha-platica"
          type="date"
          value={fecha}
          onChange={(evento) => setFecha(evento.target.value)}
          disabled={guardando}
        />

        <Input
          etiqueta={t('platicas.tema')}
          name="tema-platica"
          value={tema}
          placeholder={t('platicas.temaPlaceholder')}
          onChange={(evento) => setTema(evento.target.value)}
          disabled={guardando}
          maxLength={300}
        />
      </div>

      <div className="flex flex-col gap-2">
        <span className="text-sm font-medium text-texto">
          {t('platicas.areas')}
          {!hayTema && (
            <span className="ml-2 font-normal text-texto-tenue">
              {t('platicas.primeroTema')}
            </span>
          )}
        </span>

        <div className="flex flex-wrap gap-2">
          {areas.map((area) => {
            const activa = elegidas.includes(area.clave);

            return (
              <button
                key={area.clave}
                type="button"
                aria-pressed={activa}
                onClick={() => alternar(area.clave)}
                disabled={!hayTema || guardando}
                className={cn(
                  'h-tactil min-w-[7rem] rounded-md border px-4 text-sm font-semibold transition-colors',
                  'disabled:cursor-not-allowed disabled:opacity-50',
                  activa
                    ? 'border-primario bg-primario-suave text-primario'
                    : 'border-borde text-texto-suave hover:border-borde-fuerte hover:text-texto',
                )}
              >
                {area.etiqueta}
              </button>
            );
          })}
        </div>
      </div>

      {hayAreas && (
        <CampoFotos
          id="fotos-platica"
          fotos={fotos}
          onCambiar={setFotos}
          onError={onError}
          maximo={MAX_FOTOS}
          deshabilitado={guardando}
        />
      )}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-texto-tenue">
          {!hayTema
            ? t('platicas.faltaTema')
            : !hayAreas
              ? t('platicas.faltaArea')
              : fotos.length === 0
                ? t('platicas.faltaFoto')
                : t('platicas.listo', { total: elegidas.length })}
        </p>

        <Button
          tamano="lg"
          onClick={() => void guardar()}
          disabled={!puedeGuardar}
          cargando={guardando}
        >
          {t('checklist.confirmar')}
        </Button>
      </div>
    </Card>
  );
}
