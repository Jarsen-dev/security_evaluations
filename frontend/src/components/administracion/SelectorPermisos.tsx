'use client';

import { useTraduccion, type ClaveTraduccion } from '@/lib/i18n';
import type { Modulo, Permisos } from '@/lib/types';

/**
 * Matriz de permisos por pestaña.
 *
 * Dos casillas por módulo: el acceso (ver y crear) y la edición (modificar y
 * eliminar). Editar sin acceso no tiene sentido, así que quitar el acceso
 * apaga también la edición y su casilla queda deshabilitada.
 */
const MODULOS: ReadonlyArray<{ clave: Modulo; etiqueta: ClaveTraduccion }> = [
  { clave: 'cuestionarios', etiqueta: 'permisos.cuestionarios' },
  { clave: 'controles', etiqueta: 'permisos.controles' },
  { clave: 'inventario', etiqueta: 'permisos.inventario' },
];

interface SelectorPermisosProps {
  valor: Permisos;
  onCambiar: (permisos: Permisos) => void;
}

export function SelectorPermisos({ valor, onCambiar }: SelectorPermisosProps) {
  const t = useTraduccion();

  function alternarAcceso(modulo: Modulo, tieneAcceso: boolean) {
    const siguiente = { ...valor };

    if (tieneAcceso) {
      siguiente[modulo] = { editar: false };
    } else {
      // Quitar la clave, no ponerla en falso: la ausencia ES la falta de
      // acceso, tanto aquí como en el JSON que guarda el backend.
      delete siguiente[modulo];
    }

    onCambiar(siguiente);
  }

  function alternarEdicion(modulo: Modulo, puedeEditar: boolean) {
    if (valor[modulo] === undefined) {
      return;
    }
    onCambiar({ ...valor, [modulo]: { editar: puedeEditar } });
  }

  return (
    <fieldset className="flex flex-col gap-3">
      <legend className="text-sm font-medium text-texto">{t('permisos.titulo')}</legend>
      <p className="text-sm text-texto-suave">{t('permisos.ayuda')}</p>

      <div className="overflow-hidden rounded-tarjeta border border-borde">
        <table className="w-full text-sm">
          <thead className="bg-fondo-sutil">
            <tr>
              <th
                scope="col"
                className="px-4 py-2 text-left font-medium text-texto-suave"
              >
                {t('permisos.modulo')}
              </th>
              <th
                scope="col"
                className="w-24 px-4 py-2 text-center font-medium text-texto-suave"
              >
                {t('permisos.acceso')}
              </th>
              <th
                scope="col"
                className="w-24 px-4 py-2 text-center font-medium text-texto-suave"
              >
                {t('permisos.editar')}
              </th>
            </tr>
          </thead>

          <tbody>
            {MODULOS.map((modulo) => {
              const permiso = valor[modulo.clave];
              const tieneAcceso = permiso !== undefined;
              const etiqueta = t(modulo.etiqueta);

              return (
                <tr key={modulo.clave} className="border-t border-borde">
                  <td className="px-4 py-2.5 text-texto">{etiqueta}</td>

                  <td className="px-4 py-2.5 text-center">
                    <input
                      type="checkbox"
                      className="h-4 w-4 accent-primario"
                      checked={tieneAcceso}
                      aria-label={t('permisos.accesoA', { modulo: etiqueta })}
                      onChange={(evento) =>
                        alternarAcceso(modulo.clave, evento.target.checked)
                      }
                    />
                  </td>

                  <td className="px-4 py-2.5 text-center">
                    <input
                      type="checkbox"
                      className="h-4 w-4 accent-primario disabled:opacity-40"
                      checked={permiso?.editar ?? false}
                      disabled={!tieneAcceso}
                      aria-label={t('permisos.editarEn', { modulo: etiqueta })}
                      onChange={(evento) =>
                        alternarEdicion(modulo.clave, evento.target.checked)
                      }
                    />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </fieldset>
  );
}
