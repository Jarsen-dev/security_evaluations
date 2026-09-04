'use client';

import {
  CLAVES_SEMAFORO,
  ESTADOS_EXTINTOR,
  FILAS_SEMAFORO,
  PUNTOS_SEMAFORO,
} from '@/components/controles/extintores/semaforo';
import { BotonIcono, FilaAcciones } from '@/components/ui/BotonIcono';
import { Button } from '@/components/ui/Button';
import {
  IconoBote,
  IconoChecklist,
  IconoLapiz,
  IconoPalomita,
  IconoPortapapeles,
  IconoQr,
} from '@/components/ui/Iconos';
import { bilingue, useIdioma, type ClaveTraduccion } from '@/lib/i18n';
import type {
  EstadoExtintor,
  Extintor,
  ExtintoresPaginados,
  FilaExtintor,
  FiltrosExtintores,
} from '@/lib/types';
import { cn, formatearFechaIso } from '@/lib/utils';

const CLASES_CAMPO =
  'h-10 rounded-md border border-borde bg-fondo px-3 text-sm text-texto focus:border-primario';

const COLUMNAS = 7;

/** Los tres estados del filtro «revisado hoy», sin escribirlos a mano dos veces. */
const REVISADO: ReadonlyArray<{ valor: string; clave: ClaveTraduccion }> = [
  { valor: '', clave: 'extintores.revisadoTodos' },
  { valor: 'true', clave: 'extintores.revisadoSi' },
  { valor: 'false', clave: 'extintores.revisadoNo' },
];

export function TablaExtintores({
  datos,
  cargando,
  busqueda,
  filtros,
  tipos,
  puedeEditar,
  enCola,
  onBusqueda,
  onFiltros,
  onLimpiar,
  onPagina,
  onQr,
  onEditar,
  onRevisar,
  onCerrarHallazgo,
  onEliminar,
}: {
  datos: ExtintoresPaginados | null;
  cargando: boolean;
  busqueda: string;
  filtros: FiltrosExtintores;
  tipos: string[];
  puedeEditar: boolean;
  enCola: (id: string) => boolean;
  onBusqueda: (texto: string) => void;
  onFiltros: (filtros: FiltrosExtintores) => void;
  onLimpiar: () => void;
  onPagina: (pagina: number) => void;
  onQr: (extintor: Extintor) => void;
  onEditar: (extintor: Extintor) => void;
  onRevisar: (fila: FilaExtintor) => void;
  onCerrarHallazgo: (fila: FilaExtintor) => void;
  onEliminar: (extintor: Extintor) => void;
}) {
  const { t, locale } = useIdioma();

  const total = datos?.total ?? 0;
  const size = datos?.size ?? 50;
  const pagina = datos?.page ?? 1;
  const totalPaginas = Math.max(1, Math.ceil(total / size));
  const hayFiltros = Object.values(filtros).some((valor) => valor !== undefined);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex min-w-[16rem] flex-1 flex-col gap-1.5">
          <label htmlFor="buscar-extintor" className="text-sm font-medium text-texto">
            {bilingue(t('comun.buscar'))}
          </label>
          <input
            id="buscar-extintor"
            type="search"
            value={busqueda}
            placeholder={t('extintores.buscarPlaceholder')}
            onChange={(evento) => onBusqueda(evento.target.value)}
            className={CLASES_CAMPO}
          />
        </div>

        <select
          aria-label={t('extintores.tipo')}
          value={filtros.tipo ?? ''}
          onChange={(evento) =>
            onFiltros({ ...filtros, tipo: evento.target.value || undefined })
          }
          className={CLASES_CAMPO}
        >
          <option value="">{t('extintores.tipoTodos')}</option>
          {tipos.map((tipo) => (
            <option key={tipo} value={tipo}>
              {tipo}
            </option>
          ))}
        </select>

        <select
          aria-label={t('extintores.estado')}
          value={filtros.estado ?? ''}
          onChange={(evento) =>
            onFiltros({
              ...filtros,
              estado: (evento.target.value || undefined) as EstadoExtintor | undefined,
            })
          }
          className={CLASES_CAMPO}
        >
          <option value="">{t('extintores.estadoTodos')}</option>
          {/* Del mapa del semáforo: agregar un estado no puede dejar el filtro a medias. */}
          {ESTADOS_EXTINTOR.map((estado) => (
            <option key={estado} value={estado}>
              {t(CLAVES_SEMAFORO[estado])}
            </option>
          ))}
        </select>

        <select
          aria-label={t('extintores.revisadoHoy')}
          value={filtros.revisado === undefined ? '' : String(filtros.revisado)}
          onChange={(evento) =>
            onFiltros({
              ...filtros,
              revisado: evento.target.value === '' ? undefined : evento.target.value === 'true',
            })
          }
          className={CLASES_CAMPO}
        >
          {REVISADO.map((opcion) => (
            <option key={opcion.valor} value={opcion.valor}>
              {t(opcion.clave)}
            </option>
          ))}
        </select>

        {(hayFiltros || busqueda !== '') && (
          <Button variante="fantasma" tamano="sm" onClick={onLimpiar}>
            {bilingue(t('extintores.limpiarFiltros'))}
          </Button>
        )}
      </div>

      <div className="overflow-x-auto rounded-tarjeta border border-borde">
        <table className="w-full min-w-[64rem] border-collapse text-sm">
          <thead className="bg-fondo-sutil text-left text-texto-suave">
            <tr>
              <th className="px-4 py-2 font-medium">{bilingue(t('extintores.folio'))}</th>
              <th className="px-4 py-2 font-medium">{bilingue(t('extintores.modelo'))}</th>
              <th className="px-4 py-2 font-medium">{bilingue(t('extintores.tipo'))}</th>
              <th className="px-4 py-2 font-medium">{bilingue(t('extintores.ubicacion'))}</th>
              <th className="px-4 py-2 font-medium">{bilingue(t('extintores.vencimiento'))}</th>
              <th className="px-4 py-2 font-medium">{bilingue(t('extintores.estado'))}</th>
              <th className="px-4 py-2 text-right font-medium">
                {bilingue(t('comun.acciones'))}
              </th>
            </tr>
          </thead>
          <tbody>
            {cargando ? (
              <tr>
                <td colSpan={COLUMNAS} className="px-4 py-6 text-sm text-texto-suave">
                  {bilingue(t('comun.cargando'))}
                </td>
              </tr>
            ) : total === 0 ? (
              <tr>
                <td colSpan={COLUMNAS} className="px-4 py-6 text-sm text-texto-suave">
                  {bilingue(
                    hayFiltros || busqueda !== ''
                      ? t('extintores.sinResultados')
                      : t('extintores.vacio'),
                  )}
                </td>
              </tr>
            ) : (
              datos?.items.map((fila) => (
                <tr
                  key={fila.extintor.id}
                  className={cn('border-t border-borde', FILAS_SEMAFORO[fila.estado])}
                >
                  <td className="px-4 py-2 font-medium text-texto">{fila.extintor.folio}</td>
                  <td className="px-4 py-2 text-texto-suave">
                    {fila.extintor.modelo}
                    <span className="text-texto-tenue"> · {fila.extintor.capacidad}</span>
                  </td>
                  <td className="px-4 py-2 text-texto-suave">{fila.extintor.tipo}</td>
                  <td className="px-4 py-2 text-texto-suave">{fila.extintor.ubicacion}</td>
                  <td className="whitespace-nowrap px-4 py-2 text-texto-suave">
                    {formatearFechaIso(fila.extintor.vencimiento, locale)}
                  </td>
                  <td className="px-4 py-2">
                    {/* El punto de color nunca es la única señal: va con texto. */}
                    <span className="inline-flex items-center gap-2 text-texto-suave">
                      <span
                        aria-hidden
                        className={cn(
                          'h-2.5 w-2.5 shrink-0 rounded-full',
                          PUNTOS_SEMAFORO[fila.estado],
                        )}
                      />
                      {bilingue(t(CLAVES_SEMAFORO[fila.estado]))}
                    </span>
                  </td>
                  <td className="px-4 py-2">
                    <FilaAcciones>
                      <BotonIcono
                        etiqueta={t('extintores.verQr')}
                        icono={<IconoQr />}
                        onClick={() => onQr(fila.extintor)}
                        tono={enCola(fila.extintor.id) ? 'exito' : 'neutro'}
                      />
                      {puedeEditar && (
                        <BotonIcono
                          etiqueta={t('extintores.editar')}
                          icono={<IconoLapiz />}
                          onClick={() => onEditar(fila.extintor)}
                        />
                      )}
                      <BotonIcono
                        etiqueta={
                          fila.revisado_hoy
                            ? t('extintores.revisadoTitulo')
                            : t('extintores.revisionTitulo')
                        }
                        icono={fila.revisado_hoy ? <IconoPalomita /> : <IconoChecklist />}
                        tono={fila.revisado_hoy ? 'exito' : 'neutro'}
                        onClick={() => onRevisar(fila)}
                      />
                      {/* Solo cuando la revisión de hoy encontró algo. */}
                      {(fila.anomalias_hoy ?? 0) > 0 && (
                        <BotonIcono
                          etiqueta={
                            fila.cierre_hecho ? t('cierre.cerrado') : t('cierre.abrir')
                          }
                          icono={
                            fila.cierre_hecho ? <IconoPalomita /> : <IconoPortapapeles />
                          }
                          tono={fila.cierre_hecho ? 'exito' : 'neutro'}
                          onClick={() => onCerrarHallazgo(fila)}
                        />
                      )}
                      {puedeEditar && (
                        <BotonIcono
                          etiqueta={t('extintores.eliminar')}
                          icono={<IconoBote />}
                          tono="error"
                          onClick={() => onEliminar(fila.extintor)}
                        />
                      )}
                    </FilaAcciones>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>

        {total > size && (
          <div className="flex items-center justify-between border-t border-borde px-5 py-3">
            <span className="text-sm text-texto-suave">
              {bilingue(t('extintores.pagina', { pagina, total: totalPaginas }))}
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
      </div>
    </div>
  );
}
