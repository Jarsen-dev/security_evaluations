'use client';

import { useEffect, useState } from 'react';

import { obtenerAreas } from '@/lib/api';
import { bilingue, useTraduccion } from '@/lib/i18n';
import type { Area } from '@/lib/types';

/**
 * Bloque fijo y no editable del inicio del formulario.
 *
 * Nombre, número de empleado y área no son preguntas: son campos de
 * identidad del respondiente y viven como columnas en la tabla `intentos`.
 * Aquí solo se muestran, atenuados, para que el administrador sepa que
 * siempre se piden y no los duplique como preguntas.
 */
export function CamposFijos() {
  const t = useTraduccion();
  const [areas, setAreas] = useState<Area[]>([]);

  useEffect(() => {
    let cancelado = false;

    obtenerAreas()
      .then((resultado) => {
        if (!cancelado) {
          setAreas(resultado);
        }
      })
      .catch(() => {
        // El catálogo es informativo en este bloque: si falla, se muestra el
        // resto igual en lugar de romper el constructor completo.
      });

    return () => {
      cancelado = true;
    };
  }, []);

  return (
    <div className="rounded-tarjeta border border-dashed border-borde bg-fondo/50 p-4 opacity-75">
      <p className="mb-3 text-xs font-medium uppercase tracking-wide text-texto-tenue">
        {bilingue(t('cuestionarios.camposFijos'))}
      </p>

      <div className="grid gap-3 sm:grid-cols-3">
        <div>
          <span className="text-sm text-texto-suave">{bilingue(t('cuestionarios.nombre'))}</span>
          <div className="mt-1 h-9 rounded-md border border-borde bg-fondo-sutil" />
        </div>

        <div>
          <span className="text-sm text-texto-suave">
            {bilingue(t('cuestionarios.numeroEmpleado'))}
          </span>
          <div className="mt-1 h-9 rounded-md border border-borde bg-fondo-sutil" />
        </div>

        <div>
          <span className="text-sm text-texto-suave">{bilingue(t('comun.area'))}</span>
          <div className="mt-1 flex h-9 items-center rounded-md border border-borde bg-fondo-sutil px-2 text-xs text-texto-tenue">
            {bilingue(areas.length > 0
              ? t('cuestionarios.opcionesArea', { total: areas.length })
              : t('comun.cargando'))}
          </div>
        </div>
      </div>

      {areas.length > 0 && (
        <p className="mt-2 text-xs text-texto-tenue">
          {areas.map((area) => area.label).join(' · ')}
        </p>
      )}
    </div>
  );
}
