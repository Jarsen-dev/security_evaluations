'use client';

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

import { cn } from '@/lib/utils';

type TonoToast = 'exito' | 'error' | 'info';

interface Toast {
  id: number;
  mensaje: string;
  tono: TonoToast;
}

interface ContextoToast {
  mostrarToast: (mensaje: string, tono?: TonoToast) => void;
}

const Contexto = createContext<ContextoToast | null>(null);

const DURACION_MS = 4000;

const TONOS: Record<TonoToast, string> = {
  exito: 'border-exito bg-exito-suave text-exito',
  error: 'border-error bg-error-suave text-error',
  info: 'border-borde bg-fondo-sutil text-texto',
};

export function ProveedorToast({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const mostrarToast = useCallback((mensaje: string, tono: TonoToast = 'info') => {
    // Date.now() puede repetirse si se disparan dos toasts en el mismo
    // milisegundo; el aleatorio evita colisiones de key en React.
    const id = Date.now() + Math.random();
    setToasts((previos) => [...previos, { id, mensaje, tono }]);

    setTimeout(() => {
      setToasts((previos) => previos.filter((toast) => toast.id !== id));
    }, DURACION_MS);
  }, []);

  const valor = useMemo(() => ({ mostrarToast }), [mostrarToast]);

  return (
    <Contexto.Provider value={valor}>
      {children}

      <div
        className="pointer-events-none fixed bottom-6 right-6 z-[60] flex flex-col gap-2"
        aria-live="polite"
        aria-atomic="false"
      >
        {toasts.map((toast) => (
          <div
            key={toast.id}
            role="status"
            className={cn(
              'pointer-events-auto rounded-md border px-4 py-3 text-sm shadow-lg',
              TONOS[toast.tono],
            )}
          >
            {toast.mensaje}
          </div>
        ))}
      </div>
    </Contexto.Provider>
  );
}

export function useToast(): ContextoToast {
  const contexto = useContext(Contexto);

  if (contexto === null) {
    throw new Error('useToast debe usarse dentro de <ProveedorToast>.');
  }

  return contexto;
}
