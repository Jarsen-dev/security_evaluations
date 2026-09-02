'use client';

import { Badge } from '@/components/ui/Badge';
import { BotonIcono, FilaAcciones } from '@/components/ui/BotonIcono';
import { IconoBote, IconoEncender, IconoLapiz } from '@/components/ui/Iconos';
import { bilingue, unaLinea, useIdioma } from '@/lib/i18n';
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
              {bilingue(t('usuarios.nombre'))}
            </th>
            <th scope="col" className="px-5 py-3 text-left font-medium text-texto-suave">
              {bilingue(t('usuarios.usuario'))}
            </th>
            <th scope="col" className="px-5 py-3 text-left font-medium text-texto-suave">
              {bilingue(t('usuarios.email'))}
            </th>
            <th scope="col" className="px-5 py-3 text-left font-medium text-texto-suave">
              {bilingue(t('permisos.titulo'))}
            </th>
            <th scope="col" className="px-5 py-3 text-left font-medium text-texto-suave">
              {bilingue(t('usuarios.estado'))}
            </th>
            <th scope="col" className="px-5 py-3 text-left font-medium text-texto-suave">
              {bilingue(t('usuarios.ultimoAcceso'))}
            </th>
            <th scope="col" className="px-5 py-3 text-right">
              <span className="sr-only">{bilingue(t('comun.acciones'))}</span>
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
                      {/* `unaLinea` y no `bilingue`: los paréntesis son texto
                          literal del JSX y quedarían uno arriba y otro abajo,
                          a los lados del bloque de dos renglones. */}
                      ({unaLinea(t('usuarios.tu'))})
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
                    {bilingue(usuario.activo ? t('usuarios.activo') : t('usuarios.inactivo'))}
                  </Badge>
                </td>

                <td className="px-5 py-3 text-texto-suave">
                  {bilingue(usuario.last_login_at === null
                    ? t('usuarios.nunca')
                    : new Date(usuario.last_login_at).toLocaleString(locale, {
                        dateStyle: 'short',
                        timeStyle: 'short',
                      }))}
                </td>

                <td className="px-5 py-3">
                  <FilaAcciones>
                    <BotonIcono
                      etiqueta={t('comun.editar')}
                      icono={<IconoLapiz />}
                      onClick={() => onEditar(usuario)}
                    />

                    {!esPropio && (
                      <>
                        <BotonIcono
                          etiqueta={
                            usuario.activo
                              ? t('usuarios.desactivar')
                              : t('usuarios.activar')
                          }
                          icono={<IconoEncender />}
                          tono={usuario.activo ? 'exito' : 'neutro'}
                          cargando={ocupado}
                          onClick={() => onAlternarActivo(usuario)}
                        />

                        <BotonIcono
                          etiqueta={t('comun.eliminar')}
                          icono={<IconoBote />}
                          tono="error"
                          onClick={() => onEliminar(usuario)}
                        />
                      </>
                    )}
                  </FilaAcciones>
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
    return <Badge tono="alerta">{bilingue(t('usuarios.superadmin'))}</Badge>;
  }

  const otorgados = MODULOS.filter((modulo) => usuario.permisos[modulo] !== undefined);

  if (otorgados.length === 0) {
    return <span className="text-xs text-texto-tenue">{bilingue(t('usuarios.sinPermisos'))}</span>;
  }

  return (
    <div className="flex flex-wrap gap-1.5">
      {otorgados.map((modulo) => (
        <Badge
          key={modulo}
          tono={usuario.permisos[modulo]?.editar === true ? 'exito' : 'neutro'}
        >
          {bilingue(t(`permisos.${modulo}`))}
          {usuario.permisos[modulo]?.editar === true && ` · ${unaLinea(t('permisos.editar'))}`}
        </Badge>
      ))}
    </div>
  );
}
