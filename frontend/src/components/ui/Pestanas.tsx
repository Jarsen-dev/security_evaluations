'use client';

import { useRef } from 'react';

import { bilingue } from '@/lib/i18n';
import { cn } from '@/lib/utils';

export interface Pestana {
  clave: string;
  etiqueta: string;
}

interface PestanasProps {
  pestanas: ReadonlyArray<Pestana>;
  activa: string;
  onCambiar: (clave: string) => void;
  /** Nombre de la lista para los lectores de pantalla. */
  etiqueta: string;
}

/**
 * Barra de pestañas internas, compartida por Cuestionarios y Controles.
 *
 * Se desplaza en horizontal a propósito: Controles tiene nueve pestañas y en
 * la laptop de planta no caben en una línea.
 */
export function Pestanas({ pestanas, activa, onCambiar, etiqueta }: PestanasProps) {
  const lista = useRef<HTMLDivElement>(null);

  function alPresionarTecla(evento: React.KeyboardEvent<HTMLDivElement>) {
    if (evento.key !== 'ArrowRight' && evento.key !== 'ArrowLeft') {
      return;
    }

    evento.preventDefault();

    const indice = pestanas.findIndex((pestana) => pestana.clave === activa);
    const salto = evento.key === 'ArrowRight' ? 1 : -1;
    // Da la vuelta en los extremos: con nueve pestañas, llegar al final y
    // seguir avanzando es lo que la gente espera.
    const siguiente = (indice + salto + pestanas.length) % pestanas.length;
    const destino = pestanas[siguiente];

    if (destino === undefined) {
      return;
    }

    onCambiar(destino.clave);
    lista.current
      ?.querySelectorAll<HTMLButtonElement>('[role="tab"]')
      [siguiente]?.focus();
  }

  return (
    <div
      ref={lista}
      role="tablist"
      aria-label={etiqueta}
      onKeyDown={alPresionarTecla}
      className="flex gap-1 overflow-x-auto border-b border-borde pb-px"
    >
      {pestanas.map((pestana) => {
        const seleccionada = pestana.clave === activa;

        return (
          <button
            key={pestana.clave}
            type="button"
            role="tab"
            aria-selected={seleccionada}
            tabIndex={seleccionada ? 0 : -1}
            onClick={() => onCambiar(pestana.clave)}
            className={cn(
              // px-3 y no px-4: con las nueve pestañas de Controles, este
              // recorte es lo que cierra el hueco que dejaba el ensanche del
              // panel en la laptop de planta (~1366px) y evita el scroll
              // lateral de la barra.
              'whitespace-nowrap rounded-t-md px-3 py-2 text-sm font-medium transition-colors',
              'border-b-2',
              seleccionada
                ? 'border-primario text-primario'
                : 'border-transparent text-texto-suave hover:text-texto',
            )}
          >
            {bilingue(pestana.etiqueta)}
          </button>
        );
      })}
    </div>
  );
}
