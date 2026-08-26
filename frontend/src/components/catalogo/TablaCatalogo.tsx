'use client';

import { CLAVES_SEMAFORO, PUNTOS_SEMAFORO } from '@/components/catalogo/semaforo';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { useIdioma } from '@/lib/i18n';
import { cn } from '@/lib/utils';
import type { FiltrosCatalogo, Insumo, InsumosPaginados } from '@/lib/types';

interface TablaCatalogoProps {
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
  puedeEditar: boolean;
  onEditar: (insumo: Insumo) => void;
  onEliminar: (insumo: Insumo) => void;
}

const CLASES_CAMPO =
  'h-10 rounded-md border border-borde bg-fondo px-3 text-sm text-texto focus:border-primario';

/** Número de columnas, para los renglones de estado vacío. */
const COLUMNAS = 8;

export function TablaCatalogo({
  datos,
  cargando,
  categorias,
  filtros,
  busqueda,
  onBusqueda,
  onFiltros,
  onLimpiar,
  onPagina,
  puedeEditar,
  onEditar,
  onEliminar,
}: TablaCatalogoProps) {
  const { t, locale } = useIdioma();

  const total = datos?.total ?? 0;
  const size = datos?.size ?? 50;
  const pagina = datos?.page ?? 1;
  const totalPaginas = Math.max(1, Math.ceil(total / size));
  const hayFiltros = Object.values(filtros).some((valor) => valor !== undefined);

  const numero = (valor: number) => valor.toLocaleString(locale);

  return (
    <Card className="overflow-hidden p-0">
      <div className="flex flex-wrap items-end gap-3 border-b border-borde bg-fondo/40 px-5 py-4">
        <div className="flex min-w-[16rem] flex-1 flex-col gap-1.5">
          <label htmlFor="catalogo-busqueda" className="text-xs font-medium text-texto-suave">
            {t('comun.buscar')}
          </label>
          <input
            id="catalogo-busqueda"
            type="search"
            className={CLASES_CAMPO}
            placeholder={t('catalogo.buscarAyuda')}
            value={busqueda}
            onChange={(evento) => onBusqueda(evento.target.value)}
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="catalogo-categoria" className="text-xs font-medium text-texto-suave">
            {t('catalogo.categoria')}
          </label>
          <select
            id="catalogo-categoria"
            className={CLASES_CAMPO}
            value={filtros.categoria ?? ''}
            onChange={(evento) =>
              onFiltros({ ...filtros, categoria: evento.target.value || undefined })
            }
          >
            <option value="">{t('catalogo.todasLasCategorias')}</option>
            {categorias.map((categoria) => (
              <option key={categoria} value={categoria}>
                {categoria}
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="catalogo-estado" className="text-xs font-medium text-texto-suave">
            {t('catalogo.estado')}
          </label>
          <select
            id="catalogo-estado"
            className={CLASES_CAMPO}
            value={filtros.estado ?? ''}
            onChange={(evento) =>
              onFiltros({
                ...filtros,
                estado: (evento.target.value || undefined) as FiltrosCatalogo['estado'],
              })
            }
          >
            <option value="">{t('catalogo.todosLosEstados')}</option>
            <option value="bajo">{t('semaforoInsumo.bajo')}</option>
            <option value="excedido">{t('semaforoInsumo.excedido')}</option>
          </select>
        </div>

        {(hayFiltros || busqueda !== '') && (
          <Button variante="fantasma" tamano="sm" onClick={onLimpiar}>
            {t('catalogo.limpiar')}
          </Button>
        )}

        <span className="ml-auto text-sm text-texto-suave">
          {t('catalogo.registros', { total })}
        </span>
      </div>

      {/* El scroll lateral vive dentro de la tabla: la página nunca se desplaza. */}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[58rem] text-sm">
          <thead className="bg-fondo-sutil">
            <tr>
              <th scope="col" className="px-5 py-3 text-left font-medium text-texto-suave">
                {t('catalogo.nombre')}
              </th>
              <th scope="col" className="px-5 py-3 text-left font-medium text-texto-suave">
                {t('catalogo.categoria')}
              </th>
              <th scope="col" className="px-5 py-3 text-left font-medium text-texto-suave">
                {t('catalogo.proveedor')}
              </th>
              <th scope="col" className="px-5 py-3 text-left font-medium text-texto-suave">
                {t('catalogo.ubicacion')}
              </th>
              <th scope="col" className="px-5 py-3 text-right font-medium text-texto-suave">
                {t('catalogo.cantidad')}
              </th>
              <th scope="col" className="px-5 py-3 text-right font-medium text-texto-suave">
                {t('catalogo.rango')}
              </th>
              <th scope="col" className="px-5 py-3 text-left font-medium text-texto-suave">
                {t('catalogo.estado')}
              </th>
              <th scope="col" className="px-5 py-3 text-right">
                <span className="sr-only">{t('comun.acciones')}</span>
              </th>
            </tr>
          </thead>

          <tbody>
            {cargando ? (
              <tr>
                <td colSpan={COLUMNAS} className="px-5 py-8 text-center text-texto-suave">
                  {t('comun.cargando')}
                </td>
              </tr>
            ) : total === 0 ? (
              <tr>
                <td colSpan={COLUMNAS} className="px-5 py-10 text-center">
                  <p className="text-sm font-medium text-texto">
                    {hayFiltros || busqueda !== ''
                      ? t('catalogo.sinCoincidencias')
                      : t('catalogo.vacio')}
                  </p>
                  {!hayFiltros && busqueda === '' && (
                    <p className="mt-2 text-sm text-texto-suave">
                      {t('catalogo.vacioAyuda')}
                    </p>
                  )}
                </td>
              </tr>
            ) : (
              datos?.items.map((insumo) => (
                <tr key={insumo.id} className="border-b border-borde last:border-0">
                  <td className="px-5 py-3">
                    <span className="font-medium text-texto">{insumo.nombre}</span>
                    {insumo.descripcion && (
                      <span className="block text-xs text-texto-tenue">
                        {insumo.descripcion}
                      </span>
                    )}
                  </td>
                  <td className="px-5 py-3 text-texto-suave">{insumo.categoria}</td>
                  <td className="px-5 py-3 text-texto-suave">{insumo.proveedor ?? '—'}</td>
                  <td className="px-5 py-3 text-texto-suave">{insumo.ubicacion ?? '—'}</td>
                  <td className="px-5 py-3 text-right font-medium text-texto">
                    {numero(insumo.cantidad)}
                  </td>
                  <td className="px-5 py-3 text-right text-texto-tenue">
                    {numero(insumo.minimo)} / {numero(insumo.maximo)}
                  </td>
                  <td className="px-5 py-3">
                    {/* El punto de color nunca es la única señal: va con texto. */}
                    <span className="inline-flex items-center gap-2 text-texto-suave">
                      <span
                        aria-hidden
                        className={cn(
                          'h-2.5 w-2.5 shrink-0 rounded-full',
                          PUNTOS_SEMAFORO[insumo.estado],
                        )}
                      />
                      {t(CLAVES_SEMAFORO[insumo.estado])}
                    </span>
                  </td>
                  <td className="px-5 py-3">
                    {puedeEditar && (
                      <div className="flex justify-end gap-2">
                        <Button
                          variante="secundario"
                          tamano="sm"
                          onClick={() => onEditar(insumo)}
                        >
                          {t('comun.editar')}
                        </Button>
                        <Button
                          variante="peligro"
                          tamano="sm"
                          onClick={() => onEliminar(insumo)}
                        >
                          {t('comun.eliminar')}
                        </Button>
                      </div>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {total > size && (
        <div className="flex items-center justify-between border-t border-borde px-5 py-3">
          <span className="text-sm text-texto-suave">
            {t('catalogo.pagina', { pagina, total: totalPaginas })}
          </span>

          <div className="flex gap-2">
            <Button
              variante="secundario"
              tamano="sm"
              disabled={pagina <= 1}
              onClick={() => onPagina(pagina - 1)}
            >
              {t('catalogo.anterior')}
            </Button>
            <Button
              variante="secundario"
              tamano="sm"
              disabled={pagina >= totalPaginas}
              onClick={() => onPagina(pagina + 1)}
            >
              {t('catalogo.siguiente')}
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}
