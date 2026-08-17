import { forwardRef, type InputHTMLAttributes } from 'react';

import { cn } from '@/lib/utils';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  etiqueta: string;
  /** Mensaje de error mostrado bajo el campo; también lo anuncia el lector de pantalla. */
  error?: string;
  ayuda?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { etiqueta, error, ayuda, className, id, ...props },
  ref,
) {
  const idCampo = id ?? props.name ?? etiqueta;
  const idError = `${idCampo}-error`;
  const idAyuda = `${idCampo}-ayuda`;

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={idCampo} className="text-sm font-medium text-texto">
        {etiqueta}
      </label>

      <input
        ref={ref}
        id={idCampo}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? idError : ayuda ? idAyuda : undefined}
        className={cn(
          'h-10 rounded-md border bg-fondo px-3 text-sm text-texto',
          'placeholder:text-texto-tenue',
          'disabled:cursor-not-allowed disabled:opacity-50',
          error ? 'border-error' : 'border-borde focus:border-primario',
          className,
        )}
        {...props}
      />

      {error && (
        <p id={idError} role="alert" className="text-sm text-error">
          {error}
        </p>
      )}

      {!error && ayuda && (
        <p id={idAyuda} className="text-sm text-texto-tenue">
          {ayuda}
        </p>
      )}
    </div>
  );
});
