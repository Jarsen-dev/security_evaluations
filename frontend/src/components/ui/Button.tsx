import type { ButtonHTMLAttributes, ReactNode } from 'react';

import { cn } from '@/lib/utils';

type Variante = 'primario' | 'secundario' | 'fantasma' | 'peligro';
type Tamano = 'sm' | 'md' | 'lg';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variante?: Variante;
  tamano?: Tamano;
  cargando?: boolean;
  children: ReactNode;
}

const VARIANTES: Record<Variante, string> = {
  primario: 'bg-primario text-white hover:bg-primario-hover',
  secundario: 'bg-fondo-sutil text-texto border border-borde hover:border-borde-fuerte',
  fantasma: 'text-texto-suave hover:bg-fondo-sutil hover:text-texto',
  peligro: 'bg-error text-white hover:opacity-90',
};

const TAMANOS: Record<Tamano, string> = {
  sm: 'h-8 px-3 text-sm',
  md: 'h-10 px-4 text-sm',
  lg: 'h-tactil px-6 text-base',
};

export function Button({
  variante = 'primario',
  tamano = 'md',
  cargando = false,
  disabled,
  className,
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      // Sin `type` explícito, un botón dentro de un formulario lo envía por
      // accidente; el default seguro es "button".
      type="button"
      disabled={disabled || cargando}
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-md font-medium transition-colors',
        'disabled:cursor-not-allowed disabled:opacity-50',
        VARIANTES[variante],
        TAMANOS[tamano],
        className,
      )}
      {...props}
    >
      {cargando && (
        <span
          aria-hidden="true"
          className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"
        />
      )}
      {children}
    </button>
  );
}
