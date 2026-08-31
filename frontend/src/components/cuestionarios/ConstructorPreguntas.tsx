'use client';

import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core';
import {
  SortableContext,
  arrayMove,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';

import { CamposFijos } from '@/components/cuestionarios/CamposFijos';
import { ImportarExcel } from '@/components/cuestionarios/ImportarExcel';
import {
  TarjetaPregunta,
  type ErroresPregunta,
} from '@/components/cuestionarios/TarjetaPregunta';
import { Button } from '@/components/ui/Button';
import { bilingue, useTraduccion } from '@/lib/i18n';
import { idUnico } from '@/lib/navegador';
import type { OpcionBorrador, PreguntaBorrador } from '@/lib/types';

interface ConstructorProps {
  preguntas: PreguntaBorrador[];
  onCambiar: (preguntas: PreguntaBorrador[]) => void;
  errores: Record<string, ErroresPregunta>;
}

/**
 * Genera una clave local estable para React.
 *
 * Delega en `idUnico()`: `crypto.randomUUID` no existe por HTTP en una IP de
 * LAN, que es justo como corre el sistema en planta.
 */
export function nuevoIdLocal(): string {
  return idUnico();
}

export function opcionVacia(): OpcionBorrador {
  return { idLocal: nuevoIdLocal(), texto: '', es_correcta: false };
}

export function preguntaVacia(): PreguntaBorrador {
  return {
    idLocal: nuevoIdLocal(),
    texto: '',
    puntos: 1,
    // Arranca con dos opciones porque ese es el mínimo que exige la regla
    // de negocio: evita que el usuario tenga que agregarlas siempre.
    opciones: [opcionVacia(), opcionVacia()],
  };
}

export function ConstructorPreguntas({
  preguntas,
  onCambiar,
  errores,
}: ConstructorProps) {
  const t = useTraduccion();

  const sensores = useSensors(
    // Los 6px de tolerancia evitan que un clic en el asa dispare un arrastre
    // accidental al escribir.
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  function actualizarPregunta(
    idLocal: string,
    transformar: (pregunta: PreguntaBorrador) => PreguntaBorrador,
  ) {
    onCambiar(
      preguntas.map((pregunta) =>
        pregunta.idLocal === idLocal ? transformar(pregunta) : pregunta,
      ),
    );
  }

  function alTerminarArrastre(evento: DragEndEvent) {
    const { active, over } = evento;

    if (!over || active.id === over.id) {
      return;
    }

    const desde = preguntas.findIndex((p) => p.idLocal === active.id);
    const hasta = preguntas.findIndex((p) => p.idLocal === over.id);

    if (desde === -1 || hasta === -1) {
      return;
    }

    onCambiar(arrayMove(preguntas, desde, hasta));
  }

  return (
    <div className="flex flex-col gap-4">
      <CamposFijos />

      <ImportarExcel
        onImportadas={(importadas) => {
          // Se AGREGAN a las existentes, no las reemplazan: el usuario puede
          // combinar preguntas capturadas a mano con las de su archivo.
          const vacias = preguntas.filter(
            (pregunta) =>
              pregunta.texto.trim() === '' &&
              pregunta.opciones.every((opcion) => opcion.texto.trim() === ''),
          );
          // La pregunta en blanco que abre el constructor solo estorbaría
          // después de importar, así que se descarta si sigue intacta.
          onCambiar([
            ...preguntas.filter((pregunta) => !vacias.includes(pregunta)),
            ...importadas,
          ]);
        }}
      />

      <DndContext
        sensors={sensores}
        collisionDetection={closestCenter}
        onDragEnd={alTerminarArrastre}
      >
        <SortableContext
          items={preguntas.map((pregunta) => pregunta.idLocal)}
          strategy={verticalListSortingStrategy}
        >
          <div className="flex flex-col gap-3">
            {preguntas.map((pregunta, indice) => (
              <TarjetaPregunta
                key={pregunta.idLocal}
                pregunta={pregunta}
                indice={indice}
                errores={errores[pregunta.idLocal]}
                onCambiarTexto={(texto) =>
                  actualizarPregunta(pregunta.idLocal, (actual) => ({
                    ...actual,
                    texto,
                  }))
                }
                onCambiarOpcion={(idLocalOpcion, texto) =>
                  actualizarPregunta(pregunta.idLocal, (actual) => ({
                    ...actual,
                    opciones: actual.opciones.map((opcion) =>
                      opcion.idLocal === idLocalOpcion ? { ...opcion, texto } : opcion,
                    ),
                  }))
                }
                onMarcarCorrecta={(idLocalOpcion) =>
                  actualizarPregunta(pregunta.idLocal, (actual) => ({
                    ...actual,
                    opciones: actual.opciones.map((opcion) => ({
                      ...opcion,
                      es_correcta: opcion.idLocal === idLocalOpcion,
                    })),
                  }))
                }
                onAgregarOpcion={() =>
                  actualizarPregunta(pregunta.idLocal, (actual) => ({
                    ...actual,
                    opciones: [...actual.opciones, opcionVacia()],
                  }))
                }
                onEliminarOpcion={(idLocalOpcion) =>
                  actualizarPregunta(pregunta.idLocal, (actual) => ({
                    ...actual,
                    opciones: actual.opciones.filter(
                      (opcion) => opcion.idLocal !== idLocalOpcion,
                    ),
                  }))
                }
                onEliminar={() =>
                  onCambiar(
                    preguntas.filter((otra) => otra.idLocal !== pregunta.idLocal),
                  )
                }
              />
            ))}
          </div>
        </SortableContext>
      </DndContext>

      {preguntas.length === 0 && (
        <p className="rounded-tarjeta border border-dashed border-borde p-6 text-center text-sm text-texto-suave">
          {bilingue(t('constructor.sinPreguntas'))}
        </p>
      )}

      <div>
        <Button
          variante="secundario"
          onClick={() => onCambiar([...preguntas, preguntaVacia()])}
        >
          {bilingue(t('constructor.agregarPregunta'))}
        </Button>
      </div>
    </div>
  );
}
