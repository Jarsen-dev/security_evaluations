import type { ReactNode } from 'react';

import { Card } from '@/components/ui/Card';

interface TarjetaKPIProps {
  etiqueta: string;
  valor: ReactNode;
  detalle?: string;
  /** Se muestra en lugar del valor cuando no hay dato que mostrar. */
  vacio?: boolean;
  /** Mientras carga se muestra un marcador, nunca un cero engañoso. */
  cargando?: boolean;
}

export function TarjetaKPI({
  etiqueta,
  valor,
  detalle,
  vacio = false,
  cargando = false,
}: TarjetaKPIProps) {
  return (
    <Card>
      <p className="text-sm text-texto-suave">{etiqueta}</p>

      <p className="mt-1 text-3xl font-semibold text-texto">
        {cargando ? (
          // Un "0" mientras llega la respuesta se lee como dato real: el
          // administrador podría creer que nadie contestó.
          <span className="inline-block h-8 w-20 animate-pulse rounded bg-fondo-sutil align-middle" />
        ) : vacio ? (
          <span className="text-texto-tenue">—</span>
        ) : (
          valor
        )}
      </p>

      {detalle && !cargando && (
        <p className="mt-1 text-sm text-texto-tenue">{detalle}</p>
      )}
    </Card>
  );
}
