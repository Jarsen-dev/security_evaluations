'use client';

import { Button } from '@/components/ui/Button';
import { bilingue, unaLinea, useIdioma } from '@/lib/i18n';
import type { BitacoraPaginada, FiltrosBitacora } from '@/lib/types';

interface TablaLogsProps {
  datos: BitacoraPaginada | null;
  cargando: boolean;
  /** Se usa para distinguir "no hay nada" de "los filtros no encontraron nada". */
  hayFiltros: boolean;
  onPagina: (pagina: number) => void;
  filtros: FiltrosBitacora;
  usuarios: string[];
  onFiltros: (filtros: FiltrosBitacora) => void;
  onLimpiar: () => void;
}

const CLASES_CAMPO =
  'h-10 rounded-md border border-borde bg-fondo px-3 text-sm text-texto focus:border-primario';

export function TablaLogs({
  datos,
  cargando,
  hayFiltros,
  onPagina,
  filtros,
  usuarios,
  onFiltros,
  onLimpiar,
}: TablaLogsProps) {
  const { t, locale } = useIdioma();

  const total = datos?.total ?? 0;
  const size = datos?.size ?? 50;
  const pagina = datos?.page ?? 1;
  const totalPaginas = Math.max(1, Math.ceil(total / size));

  return (
    <div className="overflow-hidden rounded-tarjeta border border-borde">
      <div className="flex flex-wrap items-end gap-3 border-b border-borde bg-fondo/40 px-5 py-4">
        <Campo etiqueta={t('logs.fecha')} id="logs-fecha">
          <input
            id="logs-fecha"
            type="date"
            className={CLASES_CAMPO}
            value={filtros.fecha ?? ''}
            onChange={(evento) =>
              onFiltros({ ...filtros, fecha: evento.target.value || undefined })
            }
          />
        </Campo>

        <Campo etiqueta={t('logs.horaDesde')} id="logs-desde">
          <input
            id="logs-desde"
            type="time"
            className={CLASES_CAMPO}
            value={filtros.hora_desde ?? ''}
            onChange={(evento) =>
              onFiltros({ ...filtros, hora_desde: evento.target.value || undefined })
            }
          />
        </Campo>

        <Campo etiqueta={t('logs.horaHasta')} id="logs-hasta">
          <input
            id="logs-hasta"
            type="time"
            className={CLASES_CAMPO}
            value={filtros.hora_hasta ?? ''}
            onChange={(evento) =>
              onFiltros({ ...filtros, hora_hasta: evento.target.value || undefined })
            }
          />
        </Campo>

        <Campo etiqueta={t('logs.usuario')} id="logs-usuario">
          <select
            id="logs-usuario"
            className={CLASES_CAMPO}
            value={filtros.usuario ?? ''}
            onChange={(evento) =>
              onFiltros({ ...filtros, usuario: evento.target.value || undefined })
            }
          >
            <option value="">{unaLinea(t('logs.todosLosUsuarios'))}</option>
            {usuarios.map((usuario) => (
              <option key={usuario} value={usuario}>
                {usuario}
              </option>
            ))}
          </select>
        </Campo>

        <Button variante="fantasma" tamano="sm" onClick={onLimpiar}>
          {bilingue(t('logs.limpiar'))}
        </Button>

        <span className="ml-auto text-sm text-texto-suave">
          {bilingue(t('logs.registros', { total }))}
        </span>
      </div>

      {/* El scroll lateral vive aquí: la página nunca se desplaza. */}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[52rem] text-sm">
          <thead className="bg-fondo-sutil">
            <tr>
              <th
                scope="col"
                className="px-5 py-3 text-left font-medium text-texto-suave"
              >
                {bilingue(t('logs.hora'))}
              </th>
              <th
                scope="col"
                className="px-5 py-3 text-left font-medium text-texto-suave"
              >
                {bilingue(t('logs.usuario'))}
              </th>
              <th
                scope="col"
                className="px-5 py-3 text-left font-medium text-texto-suave"
              >
                {bilingue(t('logs.detalle'))}
              </th>
              <th
                scope="col"
                className="px-5 py-3 text-left font-medium text-texto-suave"
              >
                {bilingue(t('logs.accion'))}
              </th>
              <th
                scope="col"
                className="px-5 py-3 text-left font-medium text-texto-suave"
              >
                {bilingue(t('logs.origen'))}
              </th>
            </tr>
          </thead>

          <tbody>
            {cargando ? (
              <tr>
                <td colSpan={5} className="px-5 py-8 text-center text-texto-suave">
                  {bilingue(t('comun.cargando'))}
                </td>
              </tr>
            ) : total === 0 ? (
              <tr>
                <td colSpan={5} className="px-5 py-8 text-center text-texto-suave">
                  {bilingue(hayFiltros ? t('logs.sinCoincidencias') : t('logs.vacio'))}
                </td>
              </tr>
            ) : (
              datos?.items.map((registro) => (
                <tr key={registro.id} className="border-b border-borde last:border-0">
                  <td className="whitespace-nowrap px-5 py-3 text-texto-suave">
                    {new Date(registro.creado_at).toLocaleString(locale, {
                      dateStyle: 'short',
                      timeStyle: 'medium',
                    })}
                  </td>
                  <td className="px-5 py-3 text-texto">{registro.username}</td>
                  {/* Dato capturado por el backend: ya viene en español y no se traduce. */}
                  <td className="px-5 py-3 text-texto">{registro.descripcion}</td>
                  <td className="px-5 py-3 font-mono text-xs text-texto-tenue">
                    {registro.accion}
                  </td>
                  <td className="px-5 py-3 text-texto-tenue">{registro.ip ?? '—'}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {total > size && (
        <div className="flex items-center justify-between border-t border-borde px-5 py-3">
          <span className="text-sm text-texto-suave">
            {bilingue(t('logs.pagina', { pagina, total: totalPaginas }))}
          </span>

          <div className="flex gap-2">
            <Button
              variante="secundario"
              tamano="sm"
              disabled={pagina <= 1}
              onClick={() => onPagina(pagina - 1)}
            >
              {bilingue(t('logs.anterior'))}
            </Button>
            <Button
              variante="secundario"
              tamano="sm"
              disabled={pagina >= totalPaginas}
              onClick={() => onPagina(pagina + 1)}
            >
              {bilingue(t('logs.siguiente'))}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

/** Campo de filtro con su etiqueta, para no repetir el marcado cuatro veces. */
function Campo({
  etiqueta,
  id,
  children,
}: {
  etiqueta: string;
  id: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-xs font-medium text-texto-suave">
        {bilingue(etiqueta)}
      </label>
      {children}
    </div>
  );
}
