'use client';

import { useRef } from 'react';

import { Button } from '@/components/ui/Button';
import { bilingue, useTraduccion } from '@/lib/i18n';

/**
 * Selector del reporte de mantenimiento.
 *
 * A diferencia de `CampoFotos`, esto **no es una foto**: no lleva `capture`, no
 * pasa por `reducirImagen` y no declara `accept`. El proveedor entrega lo que
 * entrega —PDF, Word, una hoja escaneada— y filtrar por formato solo
 * conseguiría que nadie suba nada. El servidor lo guarda tal cual y lo sirve
 * siempre como descarga, nunca incrustado.
 */
interface CampoReporteProps {
  reporte: File | null;
  onCambiar: (reporte: File | null) => void;
  onError: (mensaje: string) => void;
  /** Nombre del que ya estaba guardado, al corregir un registro. */
  nombreGuardado?: string | null;
  deshabilitado?: boolean;
  id: string;
}

/** Lo mismo que impone el servidor. */
const MAX_BYTES = 10 * 1024 * 1024;

function pesoLegible(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${Math.round(bytes / 1024)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function CampoReporte({
  reporte,
  onCambiar,
  onError,
  nombreGuardado,
  deshabilitado,
  id,
}: CampoReporteProps) {
  const t = useTraduccion();
  const entrada = useRef<HTMLInputElement>(null);

  function alElegir(elegidos: FileList | null) {
    try {
      const archivo = elegidos?.[0];
      if (archivo === undefined) {
        return;
      }

      // El servidor lo vuelve a comprobar; esto solo evita subir 10 MB para
      // que los rechacen al llegar.
      if (archivo.size > MAX_BYTES) {
        onError(t('pciMtto.reporteAyuda'));
        return;
      }

      onCambiar(archivo);
    } finally {
      // Sin esto, volver a elegir el mismo archivo tras quitarlo no dispara
      // `onChange` y el campo se queda vacío sin explicación.
      if (entrada.current) {
        entrada.current.value = '';
      }
    }
  }

  const actual = reporte?.name ?? nombreGuardado ?? null;

  return (
    <div className="flex flex-col gap-2">
      <span className="text-sm font-medium text-texto">
        {bilingue(t('pciMtto.reporte'))}
      </span>

      <input
        ref={entrada}
        id={id}
        type="file"
        className="hidden"
        onChange={(evento) => alElegir(evento.target.files)}
        disabled={deshabilitado}
      />

      <div className="flex flex-wrap items-center gap-3">
        <Button
          variante="secundario"
          onClick={() => entrada.current?.click()}
          disabled={deshabilitado}
        >
          {bilingue(
            actual === null ? t('pciMtto.reporteElegir') : t('pciMtto.reporteCambiar'),
          )}
        </Button>

        {actual !== null && (
          <span className="flex items-center gap-2 text-sm text-texto-suave">
            <span className="max-w-[18rem] truncate">{actual}</span>
            {reporte !== null && (
              <span className="text-texto-tenue">({pesoLegible(reporte.size)})</span>
            )}
            <button
              type="button"
              onClick={() => onCambiar(null)}
              disabled={deshabilitado}
              aria-label={t('pciMtto.reporteQuitar')}
              title={t('pciMtto.reporteQuitar')}
              className="text-texto-tenue hover:text-error disabled:cursor-not-allowed disabled:opacity-50"
            >
              ✕
            </button>
          </span>
        )}
      </div>

      <p className="text-sm text-texto-tenue">{bilingue(t('pciMtto.reporteAyuda'))}</p>
    </div>
  );
}
