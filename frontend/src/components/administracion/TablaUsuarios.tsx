'use client';

import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { useIdioma } from '@/lib/i18n';
import type { Modulo, Usuario } from '@/lib/types';

/**
 * Tabla de usuarios con las tres acciones rápidas por fila.
 *
 * Sobre la fila propia no se muestra ninguna: el backend ya rechaza que
 * alguien se desactive o se elimine a sí mismo, y ofrecer botones que van a
 * fallar solo confunde.
 */
const MODULOS: readonly Modulo[] = [
  'cuestionarios',
  'controles',
  'inventario',
  'estudios',
  'catalogo',
  'rondines',
];

interface TablaUsuariosProps {
  usuarios: Usuario[];
  /** Id del usuario en sesión, para no ofrecerle acciones sobre sí mismo. */
  idPropio: string | undefined;
  procesandoId: string | null;
  onEditar: (usuario: Usuario) => void;
  onAlternarActivo: (usuario: Usuario) => void;
  onEliminar: (usuario: Usuario) => void;
}

export function TablaUsuarios({
  usuarios,
  idPropio,
  procesandoId,
  onEditar,
  onAlternarActivo,
  onEliminar,
}: TablaUsuariosProps) {
  const { t, locale } = useIdioma();

  return (
    // El scroll lateral vive dentro de la tabla: la página nunca se desplaza.
    <div className="overflow-x-auto rounded-tarjeta border border-borde">
      <table className="w-full min-w-[52rem] text-sm">
        <thead className="bg-fondo-sutil">
          <tr>
            <th scope="col" className="px-5 py-3 text-left font-medium text-texto-suave">
              {t('usuarios.nombre')}
            </th>
            <th scope="col" className="px-5 py-3 text-left font-medium text-texto-suave">
              {t('usuarios.usuario')}
            </th>
            <th scope="col" className="px-5 py-3 text-left font-medium text-texto-suave">
              {t('usuarios.email')}
            </th>
            <th scope="col" className="px-5 py-3 text-left font-medium text-texto-suave">
              {t('permisos.titulo')}
            </th>
            <th scope="col" className="px-5 py-3 text-left font-medium text-texto-suave">
              {t('usuarios.estado')}
            </th>
            <th scope="col" className="px-5 py-3 text-left font-medium text-texto-suave">
              {t('usuarios.ultimoAcceso')}
            </th>
            <th scope="col" className="px-5 py-3 text-right">
              <span className="sr-only">{t('comun.acciones')}</span>
            </th>
          </tr>
        </thead>

        <tbody>
          {usuarios.map((usuario) => {
            const esPropio = usuario.id === idPropio;
            const ocupado = procesandoId === usuario.id;

            return (
              <tr key={usuario.id} className="border-t border-borde">
                <td className="px-5 py-3 text-texto">
                  {usuario.nombre}
                  {esPropio && (
                    <span className="ml-2 text-xs text-texto-tenue">
                      ({t('usuarios.tu')})
                    </span>
                  )}
                </td>

                <td className="px-5 py-3 text-texto-suave">{usuario.username}</td>

                <td className="px-5 py-3 text-texto-suave">{usuario.email ?? '—'}</td>

                <td className="px-5 py-3">
                  <Permisos usuario={usuario} />
                </td>

                <td className="px-5 py-3">
                  <Badge tono={usuario.activo ? 'exito' : 'neutro'}>
                    {usuario.activo ? t('usuarios.activo') : t('usuarios.inactivo')}
                  </Badge>
                </td>

                <td className="px-5 py-3 text-texto-suave">
                  {usuario.last_login_at === null
                    ? t('usuarios.nunca')
                    : new Date(usuario.last_login_at).toLocaleString(locale, {
                        dateStyle: 'short',
                        timeStyle: 'short',
                      })}
                </td>

                <td className="px-5 py-3">
                  <div className="flex justify-end gap-2">
                    <Button
                      variante="secundario"
                      tamano="sm"
                      onClick={() => onEditar(usuario)}
                    >
                      {t('comun.editar')}
                    </Button>

                    {!esPropio && (
                      <>
                        <Button
                          variante="secundario"
                          tamano="sm"
                          cargando={ocupado}
                          onClick={() => onAlternarActivo(usuario)}
                        >
                          {usuario.activo
                            ? t('usuarios.desactivar')
                            : t('usuarios.activar')}
                        </Button>

                        <Button
                          variante="peligro"
                          tamano="sm"
                          onClick={() => onEliminar(usuario)}
                        >
                          {t('comun.eliminar')}
                        </Button>
                      </>
                    )}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/** Resume los permisos de un usuario como una fila de etiquetas. */
function Permisos({ usuario }: { usuario: Usuario }) {
  const { t } = useIdioma();

  if (usuario.es_superadmin) {
    return <Badge tono="alerta">{t('usuarios.superadmin')}</Badge>;
  }

  const otorgados = MODULOS.filter((modulo) => usuario.permisos[modulo] !== undefined);

  if (otorgados.length === 0) {
    return <span className="text-xs text-texto-tenue">{t('usuarios.sinPermisos')}</span>;
  }

  return (
    <div className="flex flex-wrap gap-1.5">
      {otorgados.map((modulo) => (
        <Badge
          key={modulo}
          tono={usuario.permisos[modulo]?.editar === true ? 'exito' : 'neutro'}
        >
          {t(`permisos.${modulo}`)}
          {usuario.permisos[modulo]?.editar === true && ` · ${t('permisos.editar')}`}
        </Badge>
      ))}
    </div>
  );
}
