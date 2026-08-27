'use client';

import { useEffect, useRef, useState } from 'react';

import { Button } from '@/components/ui/Button';
import { useTraduccion } from '@/lib/i18n';
import { REDUCCION_EVIDENCIA, reducirImagen } from '@/lib/imagen';

/**
 * Captura de evidencia fotográfica, una o varias.
 *
 * Se usa un `<input type="file" capture>`, **no** `getUserMedia`: por la IP de
 * la LAN el navegador no está en contexto seguro y esa API no existe (regla 5
 * del CLAUDE.md). Además, Nginx manda `Permissions-Policy: camera=()`, así que
 * tampoco funcionaría por HTTPS. El input abre la cámara del celular igual, y
 * en la laptop abre el explorador de archivos.
 */

interface CampoFotosProps {
  fotos: File[];
  onCambiar: (fotos: File[]) => void;
  onError: (mensaje: string) => void;
  /** Tope que impone el servidor; lo entrega el catálogo. */
  maximo: number;
  deshabilitado?: boolean;
  /** Identificador del input, para que varios campos no colisionen. */
  id: string;
}

export function CampoFotos({
  fotos,
  onCambiar,
  onError,
  maximo,
  deshabilitado,
  id,
}: CampoFotosProps) {
  const t = useTraduccion();
  const entrada = useRef<HTMLInputElement>(null);
  const [vistasPrevias, setVistasPrevias] = useState<string[]>([]);
  const [procesando, setProcesando] = useState(false);

  useEffect(() => {
    const urls = fotos.map((foto) => URL.createObjectURL(foto));
    setVistasPrevias(urls);

    // Sin esto, cada foto elegida deja su blob en memoria hasta recargar.
    return () => urls.forEach((url) => URL.revokeObjectURL(url));
  }, [fotos]);

  async function alElegir(elegidos: FileList | null) {
    if (elegidos === null || elegidos.length === 0) {
      return;
    }

    const disponibles = maximo - fotos.length;

    if (disponibles <= 0) {
      onError(t('fotos.tope', { total: maximo }));
      return;
    }

    setProcesando(true);

    try {
      const nuevas: File[] = [];

      for (const archivo of Array.from(elegidos).slice(0, disponibles)) {
        if (!archivo.type.startsWith('image/')) {
          onError(t('fotos.invalida'));
          continue;
        }

        try {
          const reducida = await reducirImagen(archivo, REDUCCION_EVIDENCIA);

          if (reducida.size > REDUCCION_EVIDENCIA.maxBytes) {
            onError(t('fotos.pesada'));
            continue;
          }

          nuevas.push(reducida);
        } catch {
          onError(t('fotos.invalida'));
        }
      }

      if (elegidos.length > disponibles) {
        onError(t('fotos.tope', { total: maximo }));
      }

      if (nuevas.length > 0) {
        onCambiar([...fotos, ...nuevas]);
      }
    } finally {
      setProcesando(false);
      // Permite volver a elegir el mismo archivo después de quitarlo.
      if (entrada.current) {
        entrada.current.value = '';
      }
    }
  }

  function quitar(indice: number) {
    onCambiar(fotos.filter((foto, posicion) => posicion !== indice));
  }

  return (
    <div className="flex flex-col gap-2">
      <span className="text-sm font-medium text-texto">
        {t('fotos.titulo')}{' '}
        <span className="font-normal text-texto-tenue">
          {t('fotos.contador', { total: fotos.length, maximo })}
        </span>
      </span>

      <input
        ref={entrada}
        id={id}
        type="file"
        accept="image/*"
        capture="environment"
        multiple
        className="hidden"
        onChange={(evento) => void alElegir(evento.target.files)}
        disabled={deshabilitado}
      />

      <div>
        <Button
          variante="secundario"
          onClick={() => entrada.current?.click()}
          cargando={procesando}
          disabled={deshabilitado || fotos.length >= maximo}
        >
          {fotos.length === 0 ? t('fotos.agregar') : t('fotos.agregarOtra')}
        </Button>
      </div>

      {vistasPrevias.length > 0 && (
        <ul className="flex flex-wrap gap-2">
          {vistasPrevias.map((url, indice) => (
            <li key={url} className="relative">
              {/* eslint-disable-next-line @next/next/no-img-element -- es un blob
                  local; next/image no puede optimizar una URL de objeto. */}
              <img
                src={url}
                alt={t('fotos.numero', { numero: indice + 1 })}
                className="h-24 w-24 rounded-md border border-borde object-cover"
              />
              <button
                type="button"
                onClick={() => quitar(indice)}
                disabled={deshabilitado}
                aria-label={t('fotos.quitar', { numero: indice + 1 })}
                className="absolute -right-1.5 -top-1.5 flex h-6 w-6 items-center justify-center rounded-full border border-borde bg-fondo-elevado text-xs text-texto-suave hover:text-error"
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
