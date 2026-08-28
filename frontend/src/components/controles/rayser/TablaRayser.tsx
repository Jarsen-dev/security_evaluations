'use client';

import {
  CLASES_SEMAFORO,
  CLAVES_SEMAFORO,
} from '@/components/controles/rayser/semaforo';
import { AccionesRegistro } from '@/components/controles/AccionesRegistro';
import { useIdioma } from '@/lib/i18n';
import { urlFotoControl } from '@/lib/api';
import type { RegistroRayser } from '@/lib/types';
import { cn, formatearFechaIso } from '@/lib/utils';

interface TablaRayserProps {
  registros: RegistroRayser[];
  onEliminar: (registro: RegistroRayser) => void;
  onVerDetalle: (registro: RegistroRayser) => void;
  onCerrarHallazgo: (registro: RegistroRayser) => void;
  /** Ids de los registros que ya tienen cierre. */
  cerrados: ReadonlySet<string>;
  totalManometros: number;
  /**
   * Si el usuario tiene permiso de edición en Controles. Sin él se esconde
   * Eliminar: la API lo rechazaría con 403. Capturar sí puede.
   */
  puedeEditar: boolean;
}

export function TablaRayser({
  registros,
  onEliminar,
  onVerDetalle,
  onCerrarHallazgo,
  cerrados,
  totalManometros,
  puedeEditar,
}: TablaRayserProps) {
  const { t, locale } = useIdioma();

  if (registros.length === 0) {
    return (
      <p className="rounded-tarjeta border border-borde bg-fondo-elevado px-4 py-8 text-center text-sm text-texto-suave">
        {t('rayser.historialVacio')}
      </p>
    );
  }

  return (
    <div className="overflow-x-auto rounded-tarjeta border border-borde">
      <table className="w-full min-w-[52rem] border-collapse text-sm">
        <thead className="bg-fondo-sutil text-left text-texto-suave">
          <tr>
            <th className="px-3 py-2 font-medium">{t('comun.fecha')}</th>
            {Array.from({ length: totalManometros }, (unused, indice) => (
              <th key={indice} className="px-3 py-2 text-center font-medium">
                {t('rayser.manometro', { numero: indice + 1 })}
              </th>
            ))}
            <th className="px-3 py-2 font-medium">{t('comun.observaciones')}</th>
            <th className="px-3 py-2 font-medium">{t('comun.responsable')}</th>
            <th className="px-3 py-2 font-medium">{t('rayser.evidencia')}</th>
            <th className="px-3 py-2 text-right font-medium">
              {t('comun.acciones')}
            </th>
          </tr>
        </thead>

        <tbody>
          {registros.map((registro) => (
            <tr key={registro.id} className="border-t border-borde align-top">
              <td className="whitespace-nowrap px-3 py-2 text-texto">
                {formatearFechaIso(registro.fecha, locale)}
              </td>

              {registro.manometros.map((lectura, indice) => (
                <td key={indice} className="px-2 py-2 text-center">
                  <span
                    className={cn(
                      'inline-flex min-w-[4.5rem] flex-col rounded-md border px-2 py-1',
                      CLASES_SEMAFORO[lectura.semaforo],
                    )}
                  >
                    <span className="font-medium">{lectura.valor}</span>
                    {/* El color no basta: se rotula si quedó baja o alta. */}
                    {lectura.semaforo !== 'verde' && (
                      <span className="text-xs">
                        {t(CLAVES_SEMAFORO[lectura.semaforo])}
                      </span>
                    )}
                  </span>
                </td>
              ))}

              <td className="max-w-xs px-3 py-2 text-texto-suave">
                {registro.observaciones ?? '—'}
              </td>

              <td className="whitespace-nowrap px-3 py-2 text-texto-suave">
                {registro.responsable}
              </td>

              <td className="px-3 py-2">
                {registro.fotos.length === 0 ? (
                  <span className="text-texto-tenue">—</span>
                ) : (
                  <span className="flex flex-wrap gap-1">
                    {registro.fotos.map((foto) => (
                      <a
                        key={foto}
                        href={urlFotoControl(foto)}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-block overflow-hidden rounded-md border border-borde"
                        title={t('rayser.verEvidencia')}
                      >
                        {/* eslint-disable-next-line @next/next/no-img-element -- la
                            imagen la sirve la API con la cookie de sesión;
                            next/image no puede optimizar una ruta protegida. */}
                        <img
                          src={urlFotoControl(foto)}
                          alt={t('rayser.verEvidencia')}
                          className="h-12 w-16 object-cover"
                        />
                      </a>
                    ))}
                  </span>
                )}
              </td>

              <td className="px-3 py-2 text-right">
                <AccionesRegistro
                  onVerDetalle={() => onVerDetalle(registro)}
                  // El hallazgo de Rayser es la lectura fuera de rango.
                  onCerrarHallazgo={
                    registro.fuera_de_rango
                      ? () => onCerrarHallazgo(registro)
                      : undefined
                  }
                  cerrado={cerrados.has(registro.id)}
                  onEliminar={puedeEditar ? () => onEliminar(registro) : undefined}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
