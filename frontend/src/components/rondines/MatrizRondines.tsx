'use client';

import { Card } from '@/components/ui/Card';
import { useIdioma } from '@/lib/i18n';
import { cn } from '@/lib/utils';
import type { Tablero } from '@/lib/types';

/**
 * La matriz de puntos × rondines.
 *
 * Cada celda lleva la hora del escaneo, no solo el color: quien revisa el
 * turno necesita saber a qué hora pasó el guardia, y el color nunca debe ser
 * la única señal.
 */
export function MatrizRondines({ tablero }: { tablero: Tablero }) {
  const { t, locale } = useIdioma();

  const hora = (iso: string) =>
    new Date(iso).toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' });

  const activos = tablero.puntos_activos || 1;

  return (
    <Card className="overflow-hidden p-0">
      {/* El scroll lateral vive dentro de la tabla: la página nunca se desplaza. */}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[52rem] text-sm">
          <thead className="bg-fondo-sutil">
            <tr>
              <th
                scope="col"
                className="sticky left-0 z-10 bg-fondo-sutil px-5 py-3 text-left font-medium text-texto-suave"
              >
                {t('rondines.punto')}
              </th>
              {Array.from({ length: tablero.rondines }, (_, indice) => (
                <th
                  key={indice}
                  scope="col"
                  className={cn(
                    'px-3 py-3 text-center font-medium',
                    // El rondín en curso se distingue: es el que se está
                    // llenando mientras alguien mira la pantalla.
                    tablero.rondin_actual === indice
                      ? 'text-primario'
                      : 'text-texto-suave',
                  )}
                >
                  {t('rondines.rondin', { numero: indice + 1 })}
                </th>
              ))}
              <th
                scope="col"
                className="px-3 py-3 text-center font-medium text-texto-suave"
              >
                {t('rondines.visitados')}
              </th>
            </tr>
          </thead>

          <tbody>
            {tablero.filas.map((fila) => (
              <tr key={fila.numero} className="border-b border-borde last:border-0">
                <th
                  scope="row"
                  className="sticky left-0 z-10 bg-fondo-elevado px-5 py-2.5 text-left font-normal"
                >
                  <span className="font-medium text-texto">{fila.numero}</span>
                  <span className="ml-2 text-texto-suave">{fila.nombre}</span>
                  {fila.ubicacion && (
                    <span className="block text-xs text-texto-tenue">
                      {fila.ubicacion}
                    </span>
                  )}
                </th>

                {fila.rondines.map((celda, indice) => (
                  <td key={indice} className="px-3 py-2.5 text-center">
                    {celda === null ? (
                      <span
                        className="text-error"
                        title={t('rondines.sinVisita')}
                        aria-label={t('rondines.sinVisita')}
                      >
                        —
                      </span>
                    ) : (
                      <span className="rounded-md bg-exito-suave px-2 py-1 font-medium text-exito">
                        {hora(celda)}
                      </span>
                    )}
                  </td>
                ))}

                <td className="px-3 py-2.5 text-center text-texto-suave">
                  {fila.visitados}/{tablero.rondines}
                </td>
              </tr>
            ))}
          </tbody>

          <tfoot className="border-t border-borde-fuerte bg-fondo-sutil">
            <tr>
              <th
                scope="row"
                className="sticky left-0 z-10 bg-fondo-sutil px-5 py-3 text-left font-medium text-texto-suave"
              >
                {t('rondines.porRondin')}
              </th>
              {tablero.por_rondin.map((visitados, indice) => (
                <td
                  key={indice}
                  className="px-3 py-3 text-center font-medium text-texto"
                >
                  {((visitados / activos) * 100).toFixed(0)}%
                </td>
              ))}
              <td className="px-3 py-3 text-center font-medium text-texto">
                {tablero.cumplimiento.toFixed(0)}%
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
    </Card>
  );
}
