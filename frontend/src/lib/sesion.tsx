'use client';

/**
 * Sesión del panel: quién entró y qué puede hacer.
 *
 * Antes esto vivía dentro de `EncabezadoPanel`, que solo necesitaba el nombre
 * de usuario. Ahora los permisos deciden qué pestañas y qué botones se
 * muestran en media interfaz, así que se consulta una sola vez y se comparte
 * por contexto.
 *
 * IMPORTANTE: esconder un botón es cosmética. Quien autoriza de verdad es la
 * API, que revisa el permiso en cada endpoint; esto solo evita ofrecer
 * acciones que van a devolver 403.
 */

import { useRouter } from 'next/navigation';
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

import { ErrorDeApi, cerrarSesion, obtenerAdminActual } from '@/lib/api';
import type { Admin, Modulo } from '@/lib/types';

interface ContextoSesion {
  usuario: Admin | null;
  cargando: boolean;
  /** `true` si el usuario puede entrar al módulo; con `'editar'`, modificar y eliminar. */
  puede: (modulo: Modulo, accion?: 'editar') => boolean;
  /** Vuelve a leer la sesión, por si cambiaron los permisos propios. */
  recargar: () => Promise<void>;
}

const Contexto = createContext<ContextoSesion | null>(null);

export function ProveedorSesion({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [usuario, setUsuario] = useState<Admin | null>(null);
  const [cargando, setCargando] = useState(true);

  const salirAlLogin = useCallback(async () => {
    // Hay que BORRAR la cookie antes de rebotar al login. Si no, el
    // middleware vuelve a ver una cookie con contenido, manda de /login a
    // /cuestionarios, este efecto recibe otro 401 y el panel entra en un
    // bucle infinito: el navegador se queda cargando para siempre.
    // `/auth/logout` no exige sesión válida justamente para esto.
    try {
      await cerrarSesion();
    } catch {
      // Si el borrado falla, se redirige igual: quedarse en el bucle es
      // peor que aterrizar en el login con la cookie todavía puesta.
    }

    router.replace('/login');
    // Obliga al middleware a reevaluar la cookie ya borrada en lugar de
    // decidir con el estado previo cacheado.
    router.refresh();
  }, [router]);

  const cargar = useCallback(async () => {
    try {
      setUsuario(await obtenerAdminActual());
    } catch (error: unknown) {
      // El middleware solo comprueba que la cookie exista; la validación
      // real de la firma ocurre aquí, contra la API.
      //
      // Solo se actúa ante un 401. Un fallo de red (ErrorDeApi con status 0)
      // o un 502 momentáneo no significan que la sesión sea inválida, y
      // cerrarla dejaría fuera al usuario por una caída pasajera.
      if (error instanceof ErrorDeApi && error.status === 401) {
        await salirAlLogin();
      }
    } finally {
      setCargando(false);
    }
  }, [salirAlLogin]);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  const valor = useMemo<ContextoSesion>(
    () => ({
      usuario,
      cargando,
      puede: (modulo, accion) => {
        if (usuario === null) return false;
        if (usuario.es_superadmin) return true;

        const permiso = usuario.permisos[modulo];
        if (permiso === undefined) return false;

        return accion === 'editar' ? permiso.editar : true;
      },
      recargar: cargar,
    }),
    [usuario, cargando, cargar],
  );

  return <Contexto.Provider value={valor}>{children}</Contexto.Provider>;
}

export function useSesion(): ContextoSesion {
  const contexto = useContext(Contexto);
  if (contexto === null) {
    throw new Error('useSesion debe usarse dentro de <ProveedorSesion>.');
  }
  return contexto;
}
