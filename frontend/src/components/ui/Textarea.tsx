import { forwardRef, type TextareaHTMLAttributes } from 'react';

import { cn } from '@/lib/utils';

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  etiqueta?: string;
  error?: string;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { etiqueta, error, className, id, ...props },
  ref,
) {
  const idCampo = id ?? props.name ?? etiqueta;
  const idError = `${idCampo}-error`;

  return (
    <div className="flex flex-col gap-1.5">
      {etiqueta && (
        <label htmlFor={idCampo} className="text-sm font-medium text-texto">
          {etiqueta}
        </label>
      )}

      <textarea
        ref={ref}
        id={idCampo}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? idError : undefined}
        className={cn(
          'min-h-[4.5rem] rounded-md border bg-fondo px-3 py-2 text-sm text-texto',
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
    </div>
  );
});
