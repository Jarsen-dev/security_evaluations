'use client';

import { useEffect, useId, useRef, useState } from 'react';

import { bilingue } from '@/lib/i18n';
import { cn } from '@/lib/utils';

export interface OpcionCombobox {
  valor: string;
  etiqueta: string;
}

interface ComboboxProps {
  etiqueta: string;
  opciones: ReadonlyArray<OpcionCombobox>;
  /** Opción elegida, o `null` mientras nadie ha elegido. */
  valor: string | null;
  onElegir: (valor: string) => void;
  /** Texto libre mientras se teclea: es lo que dice el papel, no el catálogo. */
  texto: string;
  onTexto: (texto: string) => void;
  placeholder?: string;
  error?: string;
  ayuda?: string;
  /** Clases del `<input>`: por aquí entra el resaltado en ámbar. */
  className?: string;
  deshabilitado?: boolean;
  vacio: string;
}

/**
 * Campo de texto con lista de opciones.
 *
 * Existe porque en una recepción el operador escribe lo que dice la remisión y
 * el sistema tiene que casarlo con una de las descripciones del catálogo: hace
 * falta un campo que sea las dos cosas a la vez, texto libre y elección.
 *
 * Nada de `<datalist>`: no se puede estilizar, no impide guardar algo que no
 * está en la lista, y cada navegador lo pinta a su manera.
 *
 * El `<input>` es real y acepta `className` a propósito: el formulario de
 * recepciones resalta en ámbar los campos que la IA no pudo leer y salta al
 * primero de ellos buscando `input.border-alerta`. Con un `<div>` disfrazado,
 * ese salto dejaría de encontrarlo.
 */
export function Combobox({
  etiqueta,
  opciones,
  valor,
  onElegir,
  texto,
  onTexto,
  placeholder,
  error,
  ayuda,
  className,
  deshabilitado = false,
  vacio,
}: ComboboxProps) {
  const [abierto, setAbierto] = useState(false);
  const [activa, setActiva] = useState(0);

  const contenedor = useRef<HTMLDivElement>(null);
  // `useId` y no `idUnico()`: el id tiene que ser el mismo en el HTML del
  // servidor y en el del navegador, o Next descarta la hidratación.
  const idBase = useId();
  const idLista = `${idBase}-lista`;
  const idError = `${idBase}-error`;
  const idAyuda = `${idBase}-ayuda`;

  useEffect(() => {
    if (!abierto) {
      return;
    }

    // `mousedown` y no `click`: con `click`, el blur del input cierra la lista
    // antes de que el clic llegue a la opción.
    function alHacerClic(evento: MouseEvent) {
      if (!contenedor.current?.contains(evento.target as Node)) {
        setAbierto(false);
      }
    }

    document.addEventListener('mousedown', alHacerClic);
    return () => document.removeEventListener('mousedown', alHacerClic);
  }, [abierto]);

  function elegir(indice: number) {
    const opcion = opciones[indice];
    if (opcion === undefined) {
      return;
    }
    onElegir(opcion.valor);
    setAbierto(false);
  }

  function alPresionarTecla(evento: React.KeyboardEvent<HTMLInputElement>) {
    if (evento.key === 'Escape') {
      // Cierra sin borrar lo tecleado: lo escrito es el dato de la remisión.
      setAbierto(false);
      return;
    }

    if (evento.key === 'Enter' && abierto) {
      evento.preventDefault();
      elegir(activa);
      return;
    }

    if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(evento.key)) {
      return;
    }

    evento.preventDefault();

    if (!abierto) {
      setAbierto(true);
      return;
    }

    const ultima = opciones.length - 1;
    setActiva((previa) => {
      if (evento.key === 'Home') return 0;
      if (evento.key === 'End') return ultima;
      const salto = evento.key === 'ArrowDown' ? 1 : -1;
      return Math.min(ultima, Math.max(0, previa + salto));
    });
  }

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={idBase} className="text-sm font-medium text-texto">
        {bilingue(etiqueta)}
      </label>

      <div ref={contenedor} className="relative">
        <input
          id={idBase}
          type="text"
          role="combobox"
          autoComplete="off"
          aria-expanded={abierto}
          aria-controls={idLista}
          aria-autocomplete="list"
          aria-activedescendant={abierto ? `${idLista}-${activa}` : undefined}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? idError : ayuda ? idAyuda : undefined}
          disabled={deshabilitado}
          value={texto}
          placeholder={placeholder}
          onChange={(evento) => {
            onTexto(evento.target.value);
            setAbierto(true);
            setActiva(0);
          }}
          onFocus={() => setAbierto(true)}
          onKeyDown={alPresionarTecla}
          className={cn(
            'h-10 w-full rounded-md border bg-fondo px-3 text-sm text-texto',
            'placeholder:text-texto-tenue',
            'disabled:cursor-not-allowed disabled:opacity-50',
            error ? 'border-error' : 'border-borde focus:border-primario',
            className,
          )}
        />

        {abierto && (
          <ul
            id={idLista}
            role="listbox"
            aria-label={etiqueta}
            className={cn(
              'absolute left-0 right-0 z-40 mt-1 max-h-56 overflow-y-auto rounded-md',
              'border border-borde bg-fondo-elevado py-1 shadow-xl',
            )}
          >
            {opciones.length === 0 ? (
              <li className="px-3 py-2 text-sm text-texto-tenue">{bilingue(vacio)}</li>
            ) : (
              opciones.map((opcion, indice) => (
                <li
                  key={opcion.valor}
                  id={`${idLista}-${indice}`}
                  role="option"
                  aria-selected={opcion.valor === valor}
                  onMouseEnter={() => setActiva(indice)}
                  onMouseDown={(evento) => {
                    // El input pierde el foco al soltar; sin esto la lista se
                    // cierra antes de registrar la elección.
                    evento.preventDefault();
                    elegir(indice);
                  }}
                  className={cn(
                    'cursor-pointer px-3 py-2 text-sm',
                    indice === activa ? 'bg-fondo-sutil text-texto' : 'text-texto-suave',
                    opcion.valor === valor && 'font-medium text-primario',
                  )}
                >
                  {/* Es un dato del catálogo: no se traduce ni se envuelve. */}
                  {opcion.etiqueta}
                </li>
              ))
            )}
          </ul>
        )}
      </div>

      {error && (
        <p id={idError} role="alert" className="text-sm text-error">
          {bilingue(error)}
        </p>
      )}

      {!error && ayuda && (
        <p id={idAyuda} className="text-sm text-texto-tenue">
          {bilingue(ayuda)}
        </p>
      )}
    </div>
  );
}
