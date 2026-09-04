'use client';

import { useCallback, useEffect, useState } from 'react';

import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { ErrorDeApi, listarPuntosRondin } from '@/lib/api';
import { bilingue, useTraduccion } from '@/lib/i18n';
import type { PuntoRondin } from '@/lib/types';

/**
 * Catálogo de puntos de rondín, de SOLO LECTURA.
 *
 * La captura la hacen los guardias en una app de AppSheet, que es la fuente de
 * verdad: los 44 puntos viven allá y aquí solo hay una copia que se refresca
 * en el servidor con `python -m app.cli importar-puntos`. Por eso no hay alta,
 * edición, borrado ni códigos QR — las etiquetas de la pared son de AppSheet.
 */
export function PanelPuntos() {
  const t = useTraduccion();

  const [puntos, setPuntos] = useState<PuntoRondin[]>([]);
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState('');

  const cargar = useCallback(async () => {
    setCargando(true);

    try {
      setPuntos(await listarPuntosRondin());
      setErrorCarga('');
    } catch (error: unknown) {
      setErrorCarga(
        error instanceof ErrorDeApi ? error.message : t('puntosRondin.falloCarga'),
      );
    } finally {
      setCargando(false);
    }
  }, [t]);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  return (
    <div className="flex flex-col gap-4">
      <div className="min-w-0">
        <h2 className="text-base font-semibold text-texto">
          {bilingue(t('puntosRondin.titulo'))}
        </h2>
        <p className="mt-1 text-sm text-texto-suave">
          {bilingue(t('puntosRondin.descripcion'))}
        </p>
      </div>

      {cargando ? (
        <p className="text-sm text-texto-suave">{bilingue(t('comun.cargando'))}</p>
      ) : errorCarga !== '' ? (
        <div
          role="alert"
          className="flex flex-wrap items-center gap-3 rounded-tarjeta border border-error bg-error-suave px-4 py-3 text-sm text-texto"
        >
          <span>{errorCarga}</span>
          <Button variante="secundario" tamano="sm" onClick={() => void cargar()}>
            {bilingue(t('comun.reintentar'))}
          </Button>
        </div>
      ) : puntos.length === 0 ? (
        <div className="rounded-tarjeta border border-dashed border-borde px-6 py-12 text-center">
          <p className="text-sm font-medium text-texto">
            {bilingue(t('puntosRondin.vacio'))}
          </p>
          <p className="mt-2 text-sm text-texto-suave">
            {bilingue(t('puntosRondin.vacioAyuda'))}
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-tarjeta border border-borde">
          <table className="w-full min-w-[38rem] text-sm">
            <thead className="bg-fondo-sutil">
              <tr>
                <th
                  scope="col"
                  className="px-5 py-3 text-left font-medium text-texto-suave"
                >
                  {bilingue(t('puntosRondin.numero'))}
                </th>
                <th
                  scope="col"
                  className="px-5 py-3 text-left font-medium text-texto-suave"
                >
                  {bilingue(t('puntosRondin.nombre'))}
                </th>
                <th
                  scope="col"
                  className="px-5 py-3 text-left font-medium text-texto-suave"
                >
                  {bilingue(t('puntosRondin.estado'))}
                </th>
              </tr>
            </thead>

            <tbody>
              {puntos.map((punto) => (
                <tr key={punto.id} className="border-t border-borde">
                  <td className="px-5 py-3 font-medium text-texto">{punto.numero}</td>
                  <td className="px-5 py-3 text-texto">{punto.nombre}</td>
                  <td className="px-5 py-3">
                    <Badge tono={punto.activo ? 'exito' : 'neutro'}>
                      {bilingue(
                        punto.activo
                          ? t('puntosRondin.activo')
                          : t('puntosRondin.inactivo'),
                      )}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
