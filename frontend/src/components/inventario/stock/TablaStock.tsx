'use client';

import {
  CLAVES_SEMAFORO,
  ESTADOS_INSUMO,
  FILAS_SEMAFORO,
  PUNTOS_SEMAFORO,
} from '@/components/catalogo/semaforo';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { bilingue, unaLinea, useIdioma } from '@/lib/i18n';
import { cn } from '@/lib/utils';
import type { FiltrosCatalogo, InsumosPaginados } from '@/lib/types';

interface TablaStockProps {
  datos: InsumosPaginados | null;
  cargando: boolean;
  categorias: string[];
  filtros: FiltrosCatalogo;
  /** Texto del buscador sin debounce, para que el campo responda al teclear. */
  busqueda: string;
  onBusqueda: (texto: string) => void;
  onFiltros: (filtros: FiltrosCatalogo) => void;
  onLimpiar: () => void;
  onPagina: (pagina: number) => void;
  onActualizar: () => void;
}

const CLASES_CAMPO =
  'h-10 rounded-md border border-borde bg-fondo px-3 text-sm text-texto focus:border-primario';

/** Número de columnas, para los renglones de estado vacío. */
const COLUMNAS = 5;

/**
 * Existencias de todo el catálogo.
 *
 * Presentacional: los filtros y la página los maneja `PanelStock`, igual que
 * `TablaCatalogo` con `PanelCatalogo`. Es de solo lectura a propósito —
 * corregir una existencia se hace en Catálogo, que tiene su propio permiso.
 */
export function TablaStock({
  datos,
  cargando,
  categorias,
  filtros,
  busqueda,
  onBusqueda,
  onFiltros,
  onLimpiar,
  onPagina,
  onActualizar,
}: TablaStockProps) {
  const { t, locale } = useIdioma();

  const total = datos?.total ?? 0;
  const size = datos?.size ?? 50;
  const pagina = datos?.page ?? 1;
  const totalPaginas = Math.max(1, Math.ceil(total / size));
  const hayFiltros = filtros.categoria !== undefined || filtros.estado !== undefined;

  const numero = (valor: number) => valor.toLocaleString(locale);

  return (
    <Card className="overflow-hidden p-0">
      <div className="flex flex-wrap items-end gap-3 border-b border-borde bg-fondo/40 px-5 py-4">
        <div className="flex min-w-[16rem] flex-1 flex-col gap-1.5">
          <label htmlFor="stock-busqueda" className="text-xs font-medium text-texto-suave">
            {bilingue(t('comun.buscar'))}
          </label>
          <input
            id="stock-busqueda"
            type="search"
            className={CLASES_CAMPO}
            placeholder={unaLinea(t('catalogo.buscarAyuda'))}
            value={busqueda}
            onChange={(evento) => onBusqueda(evento.target.value)}
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="stock-categoria" className="text-xs font-medium text-texto-suave">
            {bilingue(t('catalogo.categoria'))}
          </label>
          <select
            id="stock-categoria"
            className={CLASES_CAMPO}
            value={filtros.categoria ?? ''}
            onChange={(evento) =>
              onFiltros({ ...filtros, categoria: evento.target.value || undefined })
            }
          >
            <option value="">{unaLinea(t('catalogo.todasLasCategorias'))}</option>
            {categorias.map((categoria) => (
              <option key={categoria} value={categoria}>
                {categoria}
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="stock-estado" className="text-xs font-medium text-texto-suave">
            {bilingue(t('catalogo.estado'))}
          </label>
          <select
            id="stock-estado"
            className={CLASES_CAMPO}
            value={filtros.estado ?? ''}
            onChange={(evento) =>
              onFiltros({
                ...filtros,
                estado: (evento.target.value || undefined) as FiltrosCatalogo['estado'],
              })
            }
          >
            <option value="">{unaLinea(t('catalogo.todosLosEstados'))}</option>
            {ESTADOS_INSUMO.map((estado) => (
              <option key={estado} value={estado}>
                {unaLinea(t(CLAVES_SEMAFORO[estado]))}
              </option>
            ))}
          </select>
        </div>

        {(hayFiltros || busqueda !== '') && (
          <Button variante="fantasma" tamano="sm" onClick={onLimpiar}>
            {bilingue(t('catalogo.limpiar'))}
          </Button>
        )}

        {/* Un producto dado de alta en Catálogo aparece aquí al volver a
            consultar; el botón evita tener que salir y entrar a la pestaña. */}
        <Button variante="secundario" tamano="sm" onClick={onActualizar} cargando={cargando}>
          {bilingue(t('stock.actualizar'))}
        </Button>

        <span className="ml-auto text-sm text-texto-suave">
          {bilingue(t('stock.registros', { total }))}
        </span>
      </div>

      {/* El scroll lateral vive dentro de la tabla: la página nunca se desplaza. */}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[44rem] text-sm">
          <thead className="bg-fondo-sutil">
            <tr>
              <th scope="col" className="px-5 py-3 text-left font-medium text-texto-suave">
                {bilingue(t('catalogo.codigo'))}
              </th>
              <th scope="col" className="px-5 py-3 text-left font-medium text-texto-suave">
                {bilingue(t('catalogo.descripcionCampo'))}
              </th>
              <th scope="col" className="px-5 py-3 text-left font-medium text-texto-suave">
                {bilingue(t('catalogo.estado'))}
              </th>
              <th scope="col" className="px-5 py-3 text-right font-medium text-texto-suave">
                {bilingue(t('stock.existencia'))}
              </th>
              <th scope="col" className="px-5 py-3 text-left font-medium text-texto-suave">
                {bilingue(t('catalogo.unidadMedida'))}
              </th>
            </tr>
          </thead>

          <tbody>
            {cargando && datos === null ? (
              <tr>
                <td colSpan={COLUMNAS} className="px-5 py-10 text-center text-texto-suave">
                  {bilingue(t('comun.cargando'))}
                </td>
              </tr>
            ) : total === 0 ? (
              <tr>
                <td colSpan={COLUMNAS} className="px-5 py-10 text-center">
                  <p className="text-texto-suave">
                    {bilingue(
                      hayFiltros || busqueda !== ''
                        ? t('stock.sinCoincidencias')
                        : t('stock.vacio'),
                    )}
                  </p>
                  {!hayFiltros && busqueda === '' && (
                    <p className="mt-1 text-sm text-texto-tenue">
                      {bilingue(t('stock.vacioAyuda'))}
                    </p>
                  )}
                </td>
              </tr>
            ) : (
              datos?.items.map((insumo) => (
                <tr
                  key={insumo.id}
                  // El tinte es una ayuda para barrer la tabla; la señal que
                  // se lee sigue siendo el punto con su etiqueta.
                  className={cn(
                    'border-b border-borde last:border-0',
                    FILAS_SEMAFORO[insumo.estado],
                  )}
                >
                  <td className="px-5 py-3 font-medium text-texto">{insumo.codigo}</td>
                  <td className="px-5 py-3 text-texto-suave">
                    {insumo.descripcion ?? '—'}
                  </td>
                  <td className="px-5 py-3">
                    <span className="inline-flex items-center gap-2 text-texto-suave">
                      <span
                        aria-hidden
                        className={cn(
                          'h-2.5 w-2.5 shrink-0 rounded-full',
                          PUNTOS_SEMAFORO[insumo.estado],
                        )}
                      />
                      {bilingue(t(CLAVES_SEMAFORO[insumo.estado]))}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-right font-medium text-texto">
                    {numero(insumo.existencia)}
                  </td>
                  <td className="px-5 py-3 text-texto-suave">{insumo.unidad_medida}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {total > size && (
        <div className="flex items-center justify-between border-t border-borde px-5 py-3">
          <span className="text-sm text-texto-suave">
            {bilingue(t('catalogo.pagina', { pagina, total: totalPaginas }))}
          </span>

          <div className="flex gap-2">
            <Button
              variante="secundario"
              tamano="sm"
              disabled={pagina <= 1}
              onClick={() => onPagina(pagina - 1)}
            >
              {bilingue(t('catalogo.anterior'))}
            </Button>
            <Button
              variante="secundario"
              tamano="sm"
              disabled={pagina >= totalPaginas}
              onClick={() => onPagina(pagina + 1)}
            >
              {bilingue(t('catalogo.siguiente'))}
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}
