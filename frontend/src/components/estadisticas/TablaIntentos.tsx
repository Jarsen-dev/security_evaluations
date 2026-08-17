'use client';

import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import type { Area, ColumnaOrdenable, IntentosPaginados } from '@/lib/types';
import { cn } from '@/lib/utils';

interface TablaIntentosProps {
  datos: IntentosPaginados | null;
  cargando: boolean;
  ordenPor: ColumnaOrdenable;
  descendente: boolean;
  onOrdenar: (columna: ColumnaOrdenable) => void;
  onPagina: (pagina: number) => void;

  // --- Filtros de la sección ---
  areas: Area[];
  busqueda: string;
  onBusqueda: (texto: string) => void;
  area: string;
  onArea: (area: string) => void;
  desde: string;
  onDesde: (fecha: string) => void;
  hasta: string;
  onHasta: (fecha: string) => void;
  onLimpiar: () => void;
  onVerRespuestas: (intentoId: string) => void;
}

const COLUMNAS: Array<{ clave: ColumnaOrdenable | null; etiqueta: string }> = [
  { clave: 'nombre', etiqueta: 'Nombre' },
  { clave: 'numero_empleado', etiqueta: 'Núm. empleado' },
  { clave: 'area', etiqueta: 'Área' },
  { clave: 'finalizado_at', etiqueta: 'Fecha' },
  { clave: null, etiqueta: 'Duración' },
  { clave: 'puntaje', etiqueta: 'Puntaje' },
  { clave: null, etiqueta: 'Acciones' },
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
  areas,
  busqueda,
  onBusqueda,
  area,
  onArea,
  desde,
  onDesde,
  hasta,
  onHasta,
  onLimpiar,
  onVerRespuestas,
}: TablaIntentosProps) {
  const totalPaginas =
    datos === null ? 1 : Math.max(1, Math.ceil(datos.total / datos.size));

  const hayFiltros = busqueda !== '' || area !== '' || desde !== '' || hasta !== '';

  return (
    <Card className="overflow-hidden p-0">
      <div className="flex items-center justify-between border-b border-borde px-5 py-4">
        <h2 className="font-medium text-texto">Intentos</h2>
        <span className="text-sm text-texto-tenue">
          {datos?.total ?? 0} registro(s)
        </span>
      </div>

      {/* --- Filtros de la tabla --- */}
      <div className="flex flex-wrap items-end gap-3 border-b border-borde bg-fondo/40 px-5 py-4">
        <div className="flex min-w-[15rem] flex-1 flex-col gap-1.5">
          <label htmlFor="busqueda" className="text-sm font-medium text-texto">
            Buscar
          </label>
          <div className="relative">
            <input
              id="busqueda"
              type="search"
              value={busqueda}
              onChange={(evento) => onBusqueda(evento.target.value)}
              placeholder="Nombre o número de empleado"
              className="h-10 w-full rounded-md border border-borde bg-fondo px-3 pr-8 text-sm text-texto placeholder:text-texto-tenue focus:border-primario"
            />
            {busqueda !== '' && (
              <button
                type="button"
                onClick={() => onBusqueda('')}
                aria-label="Limpiar la búsqueda"
                className="absolute right-2 top-1/2 -translate-y-1/2 text-texto-tenue hover:text-texto"
              >
                ✕
              </button>
            )}
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="area-tabla" className="text-sm font-medium text-texto">
            Área
          </label>
          <select
            id="area-tabla"
            value={area}
            onChange={(evento) => onArea(evento.target.value)}
            className="h-10 rounded-md border border-borde bg-fondo px-3 text-sm text-texto focus:border-primario"
          >
            <option value="">Todas</option>
            {areas.map((opcion) => (
              <option key={opcion.value} value={opcion.value}>
                {opcion.label}
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="desde-tabla" className="text-sm font-medium text-texto">
            Desde
          </label>
          <input
            id="desde-tabla"
            type="date"
            value={desde}
            onChange={(evento) => onDesde(evento.target.value)}
            className="h-10 rounded-md border border-borde bg-fondo px-3 text-sm text-texto focus:border-primario"
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="hasta-tabla" className="text-sm font-medium text-texto">
            Hasta
          </label>
          <input
            id="hasta-tabla"
            type="date"
            value={hasta}
            onChange={(evento) => onHasta(evento.target.value)}
            className="h-10 rounded-md border border-borde bg-fondo px-3 text-sm text-texto focus:border-primario"
          />
        </div>

        {hayFiltros && (
          <Button variante="fantasma" onClick={onLimpiar}>
            Limpiar
          </Button>
        )}
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
                  {busqueda !== ''
                    ? `Ningún intento coincide con “${busqueda}”.`
                    : 'No hay intentos para los filtros seleccionados.'}
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

                  <td className="px-5 py-3">
                    <Button
                      variante="secundario"
                      tamano="sm"
                      onClick={() => onVerRespuestas(intento.id)}
                      aria-label={`Ver las respuestas de ${intento.nombre}`}
                    >
                      Ver respuestas
                    </Button>
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
