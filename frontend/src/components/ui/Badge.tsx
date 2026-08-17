import type { ReactNode } from 'react';

import { cn } from '@/lib/utils';

type Tono = 'exito' | 'neutro' | 'alerta' | 'error';

const TONOS: Record<Tono, string> = {
  exito: 'bg-exito-suave text-exito',
  neutro: 'bg-fondo-sutil text-texto-suave',
  alerta: 'bg-alerta-suave text-alerta',
  error: 'bg-error-suave text-error',
};

export function Badge({ tono = 'neutro', children }: { tono?: Tono; children: ReactNode }) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium',
        TONOS[tono],
      )}
    >
      {children}
    </span>
  );
}
