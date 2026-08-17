'use client';

import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';

import { Button } from '@/components/ui/Button';
import type { PreguntaBorrador } from '@/lib/types';
import { cn } from '@/lib/utils';

export interface ErroresPregunta {
  texto?: string;
  opciones?: string;
}

interface TarjetaPreguntaProps {
  pregunta: PreguntaBorrador;
  indice: number;
  errores?: ErroresPregunta;
  onCambiarTexto: (texto: string) => void;
  onCambiarOpcion: (idLocalOpcion: string, texto: string) => void;
  onMarcarCorrecta: (idLocalOpcion: string) => void;
  onAgregarOpcion: () => void;
  onEliminarOpcion: (idLocalOpcion: string) => void;
  onEliminar: () => void;
}

const MIN_OPCIONES = 2;

export function TarjetaPregunta({
  pregunta,
  indice,
  errores,
  onCambiarTexto,
  onCambiarOpcion,
  onMarcarCorrecta,
  onAgregarOpcion,
  onEliminarOpcion,
  onEliminar,
}: TarjetaPreguntaProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: pregunta.idLocal });

  return (
    <div
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={cn(
        'rounded-tarjeta border bg-fondo-elevado p-4',
        isDragging ? 'z-10 border-primario opacity-90 shadow-lg' : 'border-borde',
      )}
    >
      <div className="mb-3 flex items-start gap-3">
        <button
          type="button"
          // El arrastre se limita a este asa: si toda la tarjeta fuera
          // arrastrable, no se podría seleccionar texto en los inputs.
          className="mt-1.5 cursor-grab rounded px-1 text-texto-tenue hover:text-texto active:cursor-grabbing"
          aria-label={`Reordenar pregunta ${indice + 1}`}
          {...attributes}
          {...listeners}
        >
          ⠿
        </button>

        <div className="flex-1">
          <label
            htmlFor={`pregunta-${pregunta.idLocal}`}
            className="text-xs font-medium uppercase tracking-wide text-texto-tenue"
          >
            Pregunta {indice + 1}
          </label>
          <input
            id={`pregunta-${pregunta.idLocal}`}
            value={pregunta.texto}
            onChange={(evento) => onCambiarTexto(evento.target.value)}
            placeholder="Escribe la pregunta"
            aria-invalid={errores?.texto ? true : undefined}
            className={cn(
              'mt-1 h-10 w-full rounded-md border bg-fondo px-3 text-sm text-texto placeholder:text-texto-tenue',
              errores?.texto ? 'border-error' : 'border-borde focus:border-primario',
            )}
          />
          {errores?.texto && (
            <p role="alert" className="mt-1 text-sm text-error">
              {errores.texto}
            </p>
          )}
        </div>

        <Button
          variante="fantasma"
          tamano="sm"
          onClick={onEliminar}
          aria-label={`Eliminar pregunta ${indice + 1}`}
          className="mt-5 text-error hover:bg-error-suave"
        >
          Eliminar
        </Button>
      </div>

      <fieldset className="ml-8 flex flex-col gap-2">
        <legend className="sr-only">Opciones de la pregunta {indice + 1}</legend>

        {pregunta.opciones.map((opcion, indiceOpcion) => (
          <div key={opcion.idLocal} className="flex items-center gap-2">
            <input
              type="radio"
              // El name agrupa los radios por pregunta: así marcar una
              // correcta desmarca la anterior automáticamente.
              name={`correcta-${pregunta.idLocal}`}
              checked={opcion.es_correcta}
              onChange={() => onMarcarCorrecta(opcion.idLocal)}
              aria-label={`Marcar la opción ${indiceOpcion + 1} como correcta`}
              className="h-4 w-4 shrink-0 accent-exito"
            />

            <input
              value={opcion.texto}
              onChange={(evento) => onCambiarOpcion(opcion.idLocal, evento.target.value)}
              placeholder={`Opción ${indiceOpcion + 1}`}
              className="h-9 flex-1 rounded-md border border-borde bg-fondo px-3 text-sm text-texto placeholder:text-texto-tenue focus:border-primario"
            />

            <Button
              variante="fantasma"
              tamano="sm"
              onClick={() => onEliminarOpcion(opcion.idLocal)}
              disabled={pregunta.opciones.length <= MIN_OPCIONES}
              aria-label={`Eliminar opción ${indiceOpcion + 1}`}
              title={
                pregunta.opciones.length <= MIN_OPCIONES
                  ? 'Cada pregunta necesita al menos dos opciones'
                  : undefined
              }
            >
              ✕
            </Button>
          </div>
        ))}

        {errores?.opciones && (
          <p role="alert" className="text-sm text-error">
            {errores.opciones}
          </p>
        )}

        <div>
          <Button variante="secundario" tamano="sm" onClick={onAgregarOpcion}>
            Agregar opción
          </Button>
        </div>
      </fieldset>
    </div>
  );
}
