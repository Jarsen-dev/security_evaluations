import type { ReactNode } from 'react';

import { cn } from '@/lib/utils';

export function Card({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        'rounded-tarjeta border border-borde bg-fondo-elevado p-5',
        className,
      )}
    >
      {children}
    </div>
  );
}
