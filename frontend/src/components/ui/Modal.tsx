'use client';

import { useEffect, useRef, type ReactNode } from 'react';

import { bilingue } from '@/lib/i18n';
import { cn } from '@/lib/utils';

interface ModalProps {
  abierto: boolean;
  onCerrar: () => void;
  titulo: string;
  descripcion?: string;
  children: ReactNode;
  /** Barra inferior de acciones. */
  pie?: ReactNode;
  ancho?: 'sm' | 'md' | 'lg' | 'xl';
}

const ANCHOS = {
  sm: 'max-w-md',
  md: 'max-w-2xl',
  lg: 'max-w-4xl',
  // Para lo que se ve en dos columnas: el detalle de una recepción pone la
  // foto de la remisión junto a sus partidas, y con `lg` ninguna de las dos
  // cabía sin barra de desplazamiento propia.
  xl: 'max-w-6xl',
} as const;

export function Modal({
  abierto,
  onCerrar,
  titulo,
  descripcion,
  children,
  pie,
  ancho = 'md',
}: ModalProps) {
  const contenedor = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!abierto) {
      return;
    }

    function alPresionarTecla(evento: KeyboardEvent) {
      if (evento.key === 'Escape') {
        onCerrar();
      }
    }

    document.addEventListener('keydown', alPresionarTecla);
    // Bloquea el scroll del fondo mientras el modal está abierto.
    const overflowPrevio = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    return () => {
      document.removeEventListener('keydown', alPresionarTecla);
      document.body.style.overflow = overflowPrevio;
    };
  }, [abierto, onCerrar]);

  useEffect(() => {
    if (abierto) {
      contenedor.current?.focus();
    }
  }, [abierto]);

  if (!abierto) {
    return null;
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/70 p-4 sm:p-8"
      onMouseDown={(evento) => {
        // Solo cierra si el clic empezó en el fondo: arrastrar desde dentro
        // del modal hasta el fondo no debe cerrarlo.
        if (evento.target === evento.currentTarget) {
          onCerrar();
        }
      }}
    >
      <div
        ref={contenedor}
        role="dialog"
        aria-modal="true"
        aria-label={titulo}
        tabIndex={-1}
        className={cn(
          'my-auto w-full rounded-tarjeta border border-borde bg-fondo-elevado shadow-xl outline-none',
          ANCHOS[ancho],
        )}
      >
        <header className="border-b border-borde px-6 py-4">
          <h2 className="text-lg font-semibold text-texto">{bilingue(titulo)}</h2>
          {descripcion && (
            <p className="mt-1 text-sm text-texto-suave">{bilingue(descripcion)}</p>
          )}
        </header>

        <div className="px-6 py-5">{children}</div>

        {pie && (
          <footer className="flex items-center justify-end gap-3 border-t border-borde px-6 py-4">
            {pie}
          </footer>
        )}
      </div>
    </div>
  );
}
