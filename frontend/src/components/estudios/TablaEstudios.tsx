'use client';

import {
  CLASES_CELDA,
  claveEtiqueta,
  type GrupoOpciones,
} from '@/components/estudios/opciones';
import { Button } from '@/components/ui/Button';
import { useIdioma, type ClaveTraduccion } from '@/lib/i18n';
import type { CatalogoEstudios, Estudio, OpcionEstudio } from '@/lib/types';
import { fechaDeHoy, formatearFechaIso } from '@/lib/utils';
import { cn } from '@/lib/utils';

interface TablaEstudiosProps {
  catalogo: CatalogoEstudios;
  estudios: Estudio[];
  onEditar: (estudio: Estudio) => void;
  onEliminar: (estudio: Estudio) => void;
  /** Cuando es falso no se dibujan los botones de editar y eliminar. */
  puedeEditar: boolean;
}

/** Solo se convierte en enlace lo que el navegador puede abrir de verdad. */
function esEnlace(link: string): boolean {
  const minusculas = link.toLowerCase();
  return minusculas.startsWith('http://') || minusculas.startsWith('https://');
}

/**
 * Los estudios capturados, con las columnas de la hoja DETALLE.
 *
 * Los cuatro campos semaforizados —prioridad, estatus, aprobado y pagado—
 * toman su color del catálogo, no de una lista escrita aquí. La fecha de
 * vencimiento se marca en rojo cuando ya pasó; lo que está por vencer lo avisa
 * la campana del encabezado.
 */
export function TablaEstudios({
  catalogo,
  estudios,
  onEditar,
  onEliminar,
  puedeEditar,
}: TablaEstudiosProps) {
  const { t, locale } = useIdioma();
  const hoy = fechaDeHoy();

  function rotulo(
    grupo: GrupoOpciones,
    opciones: OpcionEstudio[],
    valor: string,
  ): string {
    const clave: ClaveTraduccion | undefined = claveEtiqueta(grupo, valor);
    if (clave) {
      return t(clave);
    }
    // Una clave que ya no está en el catálogo se muestra tal cual antes que
    // dejar la celda vacía.
    return opciones.find((opcion) => opcion.clave === valor)?.etiqueta ?? valor;
  }

  function color(opciones: OpcionEstudio[], valor: string): string {
    const semaforo = opciones.find((opcion) => opcion.clave === valor)?.semaforo ?? '';
    return CLASES_CELDA[semaforo] ?? '';
  }

  if (estudios.length === 0) {
    return (
      <div className="rounded-tarjeta border border-borde bg-fondo-elevado px-5 py-6">
        <p className="text-sm font-medium text-texto">{t('estudios.vacio')}</p>
        <p className="mt-1 text-sm text-texto-suave">{t('estudios.vacioAyuda')}</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-tarjeta border border-borde">
      <table className="w-full min-w-[64rem] text-sm">
        <thead className="bg-fondo-sutil">
          <tr>
            <Encabezado>{t('estudios.numero')}</Encabezado>
            <Encabezado alineado="left">{t('estudios.despacho')}</Encabezado>
            <Encabezado alineado="left">{t('estudios.estudio')}</Encabezado>
            <Encabezado>{t('estudios.vigencia')}</Encabezado>
            <Encabezado>{t('estudios.prioridad')}</Encabezado>
            <Encabezado>{t('estudios.tipo')}</Encabezado>
            <Encabezado>{t('estudios.estatus')}</Encabezado>
            <Encabezado>{t('estudios.vencimiento')}</Encabezado>
            <Encabezado>{t('estudios.aprobado')}</Encabezado>
            <Encabezado>{t('estudios.pagado')}</Encabezado>
            <Encabezado>{t('estudios.link')}</Encabezado>
            {puedeEditar && <Encabezado>{t('comun.acciones')}</Encabezado>}
          </tr>
        </thead>

        <tbody>
          {estudios.map((estudio, indice) => {
            const vencido =
              estudio.fecha_vencimiento !== null && estudio.fecha_vencimiento < hoy;

            return (
              <tr key={estudio.id} className="border-t border-borde align-top">
                <td className="px-3 py-2 text-center text-texto-suave">{indice + 1}</td>
                <td className="px-3 py-2 text-texto">{estudio.despacho}</td>

                <td className="px-3 py-2 text-texto">
                  {estudio.estudio}
                  {estudio.estudio_ko && (
                    <span className="mt-0.5 block text-texto-tenue">
                      {estudio.estudio_ko}
                    </span>
                  )}
                </td>

                <td className="px-3 py-2 text-center text-texto-suave">
                  {rotulo('vigencia', catalogo.vigencias, estudio.vigencia)}
                </td>

                <Celda clases={color(catalogo.prioridades, estudio.prioridad)}>
                  {rotulo('prioridad', catalogo.prioridades, estudio.prioridad)}
                </Celda>

                <td className="px-3 py-2 text-center font-medium text-texto">
                  {catalogo.tipos.find((opcion) => opcion.clave === estudio.tipo)?.corto ??
                    estudio.tipo}
                </td>

                <Celda clases={color(catalogo.estatus, estudio.estatus)}>
                  {rotulo('estatus', catalogo.estatus, estudio.estatus)}
                </Celda>

                <td
                  className={cn(
                    'whitespace-nowrap px-3 py-2 text-center',
                    vencido ? 'font-medium text-error' : 'text-texto-suave',
                  )}
                >
                  {estudio.fecha_vencimiento
                    ? formatearFechaIso(estudio.fecha_vencimiento, locale)
                    : rotulo('vencimiento', catalogo.vencimientos, estudio.vencimiento)}
                </td>

                <Celda clases={color(catalogo.aprobaciones, estudio.aprobado)}>
                  {rotulo('aprobacion', catalogo.aprobaciones, estudio.aprobado)}
                </Celda>

                <Celda clases={color(catalogo.aprobaciones, estudio.pagado)}>
                  {rotulo('aprobacion', catalogo.aprobaciones, estudio.pagado)}
                </Celda>

                <td className="max-w-[16rem] break-all px-3 py-2 text-center">
                  {estudio.link === null ? (
                    <span className="text-texto-tenue">—</span>
                  ) : esEnlace(estudio.link) ? (
                    <a
                      href={estudio.link}
                      target="_blank"
                      rel="noopener noreferrer"
                      title={t('estudios.abrirLink')}
                      className="text-primario hover:underline"
                    >
                      {estudio.link}
                    </a>
                  ) : (
                    // Una ruta de red no la abre el navegador: se muestra para
                    // copiarla, no como enlace.
                    <span className="text-texto-suave">{estudio.link}</span>
                  )}
                </td>

                {puedeEditar && (
                  <td className="whitespace-nowrap px-3 py-2 text-center">
                    <div className="flex justify-center gap-1">
                      <Button
                        variante="fantasma"
                        tamano="sm"
                        onClick={() => onEditar(estudio)}
                      >
                        {t('comun.editar')}
                      </Button>
                      <Button
                        variante="fantasma"
                        tamano="sm"
                        onClick={() => onEliminar(estudio)}
                      >
                        {t('comun.eliminar')}
                      </Button>
                    </div>
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function Encabezado({
  children,
  alineado = 'center',
}: {
  children: React.ReactNode;
  alineado?: 'left' | 'center';
}) {
  return (
    <th
      scope="col"
      className={cn(
        'whitespace-nowrap px-3 py-2 font-medium text-texto-suave',
        alineado === 'left' ? 'text-left' : 'text-center',
      )}
    >
      {children}
    </th>
  );
}

/** Celda semaforizada: el color lo trae el catálogo. */
function Celda({ children, clases }: { children: React.ReactNode; clases: string }) {
  return (
    <td className="px-2 py-2 text-center">
      <span
        className={cn(
          'inline-block min-w-[4.5rem] rounded-md px-2 py-1 text-xs font-semibold',
          clases || 'text-texto-suave',
        )}
      >
        {children}
      </span>
    </td>
  );
}
