'use client';

import { useRef, useState } from 'react';

import { nuevoIdLocal } from '@/components/cuestionarios/ConstructorPreguntas';
import { Button } from '@/components/ui/Button';
import { ErrorDeApi, URL_PLANTILLA_EXCEL, importarExcel } from '@/lib/api';
import type { ErrorImportacion, PreguntaBorrador } from '@/lib/types';

interface ImportarExcelProps {
  /** Recibe las preguntas parseadas; se AGREGAN a las existentes. */
  onImportadas: (preguntas: PreguntaBorrador[]) => void;
}

export function ImportarExcel({ onImportadas }: ImportarExcelProps) {
  const selectorArchivo = useRef<HTMLInputElement>(null);

  const [importando, setImportando] = useState(false);
  const [errores, setErrores] = useState<ErrorImportacion[]>([]);
  const [resumen, setResumen] = useState('');
  const [errorGeneral, setErrorGeneral] = useState('');

  async function alSeleccionarArchivo(archivo: File) {
    setImportando(true);
    setErrores([]);
    setResumen('');
    setErrorGeneral('');

    try {
      const reporte = await importarExcel(archivo);

      onImportadas(
        reporte.preguntas.map((pregunta) => ({
          idLocal: nuevoIdLocal(),
          texto: pregunta.texto,
          puntos: pregunta.puntos,
          opciones: pregunta.opciones.map((opcion) => ({
            idLocal: nuevoIdLocal(),
            texto: opcion.texto,
            es_correcta: opcion.es_correcta,
          })),
        })),
      );

      setErrores(reporte.errores);
      setResumen(
        reporte.importadas === 0
          ? 'No se importó ninguna pregunta.'
          : `Se agregaron ${reporte.importadas} pregunta(s) al constructor.`,
      );
    } catch (error) {
      setErrorGeneral(
        error instanceof ErrorDeApi
          ? error.message
          : 'No se pudo importar el archivo.',
      );
    } finally {
      setImportando(false);
      // Limpiar el input permite volver a elegir el MISMO archivo: sin esto,
      // el evento change no se dispara la segunda vez.
      if (selectorArchivo.current !== null) {
        selectorArchivo.current.value = '';
      }
    }
  }

  return (
    <div className="flex flex-col gap-3 rounded-tarjeta border border-borde bg-fondo p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Button
          variante="secundario"
          onClick={() => selectorArchivo.current?.click()}
          cargando={importando}
        >
          Importar desde Excel
        </Button>

        <a
          href={URL_PLANTILLA_EXCEL}
          download
          className="text-sm text-primario underline underline-offset-2 hover:text-primario-hover"
        >
          Descargar plantilla
        </a>

        <span className="ml-auto text-xs text-texto-tenue">
          Las preguntas importadas se agregan a las que ya tengas.
        </span>
      </div>

      <input
        ref={selectorArchivo}
        type="file"
        accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        className="hidden"
        onChange={(evento) => {
          const archivo = evento.target.files?.[0];
          if (archivo) {
            void alSeleccionarArchivo(archivo);
          }
        }}
      />

      {errorGeneral && (
        <p
          role="alert"
          className="rounded-md border border-error bg-error-suave px-3 py-2 text-sm text-error"
        >
          {errorGeneral}
        </p>
      )}

      {resumen && (
        <p className="rounded-md border border-exito bg-exito-suave px-3 py-2 text-sm text-exito">
          {resumen}
        </p>
      )}

      {errores.length > 0 && (
        <div className="rounded-md border border-alerta bg-alerta-suave px-3 py-2">
          <p className="text-sm font-medium text-alerta">
            {errores.length} fila(s) con problemas — corrígelas en tu Excel y
            vuelve a importar:
          </p>
          <ul className="mt-1.5 flex list-inside list-disc flex-col gap-0.5">
            {errores.map((error) => (
              <li key={`${error.fila}-${error.mensaje}`} className="text-sm text-texto-suave">
                <span className="font-medium text-texto">Fila {error.fila}:</span>{' '}
                {error.mensaje}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
