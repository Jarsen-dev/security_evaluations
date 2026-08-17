'use client';

import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import type { ColumnaOrdenable, IntentosPaginados } from '@/lib/types';
import { cn } from '@/lib/utils';

interface TablaIntentosProps {
  datos: IntentosPaginados | null;
  cargando: boolean;
  ordenPor: ColumnaOrdenable;
  descendente: boolean;
  onOrdenar: (columna: ColumnaOrdenable) => void;
  onPagina: (pagina: number) => void;
}

const COLUMNAS: Array<{ clave: ColumnaOrdenable | null; etiqueta: string }> = [
  { clave: 'nombre', etiqueta: 'Nombre' },
  { clave: 'numero_empleado', etiqueta: 'Núm. empleado' },
  { clave: 'area', etiqueta: 'Área' },
  { clave: 'finalizado_at', etiqueta: 'Fecha' },
  { clave: null, etiqueta: 'Duración' },
  { clave: 'puntaje', etiqueta: 'Puntaje' },
];

function formatearFecha(iso: string | null): string {
  if (iso === null) {
    return 'En progreso';
  }
  return new Date(iso).toLocaleString('es-MX', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatearDuracion(segundos: number | null): string {
  if (segundos === null) {
    return '—';
  }
  const minutos = Math.floor(segundos / 60);
  const resto = segundos % 60;
  return `${minutos}:${String(resto).padStart(2, '0')}`;
}

export function TablaIntentos({
  datos,
  cargando,
  ordenPor,
  descendente,
  onOrdenar,
  onPagina,
}: TablaIntentosProps) {
  const totalPaginas =
    datos === null ? 1 : Math.max(1, Math.ceil(datos.total / datos.size));

  return (
    <Card className="overflow-hidden p-0">
      <div className="flex items-center justify-between border-b border-borde px-5 py-4">
        <h2 className="font-medium text-texto">Intentos</h2>
        <span className="text-sm text-texto-tenue">
          {datos?.total ?? 0} registro(s)
        </span>
      </div>

      {/* La tabla desborda en horizontal dentro de su propio contenedor: la
          página nunca debe hacer scroll lateral. */}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[46rem] text-sm">
          <thead>
            <tr className="border-b border-borde text-left">
              {COLUMNAS.map((columna) => {
                const activa = columna.clave === ordenPor;
                return (
                  <th
                    key={columna.etiqueta}
                    scope="col"
                    aria-sort={
                      activa ? (descendente ? 'descending' : 'ascending') : undefined
                    }
                    className="px-5 py-3 font-medium text-texto-suave"
                  >
                    {columna.clave === null ? (
                      columna.etiqueta
                    ) : (
                      <button
                        type="button"
                        onClick={() => onOrdenar(columna.clave as ColumnaOrdenable)}
                        className={cn(
                          'inline-flex items-center gap-1 hover:text-texto',
                          activa && 'text-texto',
                        )}
                      >
                        {columna.etiqueta}
                        <span aria-hidden="true" className="text-xs">
                          {activa ? (descendente ? '▼' : '▲') : '↕'}
                        </span>
                      </button>
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>

          <tbody>
            {cargando && (
              <tr>
                <td colSpan={COLUMNAS.length} className="px-5 py-8 text-center text-texto-suave">
                  Cargando…
                </td>
              </tr>
            )}

            {!cargando && (datos?.items.length ?? 0) === 0 && (
              <tr>
                <td colSpan={COLUMNAS.length} className="px-5 py-8 text-center text-texto-suave">
                  No hay intentos para los filtros seleccionados.
                </td>
              </tr>
            )}

            {!cargando &&
              datos?.items.map((intento) => (
                <tr key={intento.id} className="border-b border-borde last:border-0">
                  <td className="px-5 py-3 text-texto">{intento.nombre}</td>
                  <td className="px-5 py-3 text-texto-suave">{intento.numero_empleado}</td>
                  <td className="px-5 py-3 text-texto-suave">{intento.area_label}</td>
                  <td className="px-5 py-3 text-texto-suave">
                    {formatearFecha(intento.finalizado_at)}
                  </td>
                  <td className="px-5 py-3 text-texto-suave">
                    {formatearDuracion(intento.duracion_segundos)}
                  </td>
                  <td className="px-5 py-3">
                    {intento.puntaje === null ? (
                      <span className="text-texto-tenue">—</span>
                    ) : (
                      <span className="font-medium text-texto">
                        {Number(intento.puntaje).toFixed(0)}%
                        <span className="ml-1 text-xs text-texto-tenue">
                          ({intento.correctas}/{intento.total_preguntas})
                        </span>
                      </span>
                    )}
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>

      {datos !== null && datos.total > datos.size && (
        <div className="flex items-center justify-between border-t border-borde px-5 py-3">
          <span className="text-sm text-texto-tenue">
            Página {datos.page} de {totalPaginas}
          </span>
          <div className="flex gap-2">
            <Button
              variante="secundario"
              tamano="sm"
              disabled={datos.page <= 1}
              onClick={() => onPagina(datos.page - 1)}
            >
              Anterior
            </Button>
            <Button
              variante="secundario"
              tamano="sm"
              disabled={datos.page >= totalPaginas}
              onClick={() => onPagina(datos.page + 1)}
            >
              Siguiente
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}
