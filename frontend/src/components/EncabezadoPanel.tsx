'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

import { Button } from '@/components/ui/Button';
import { Logo } from '@/components/ui/Logo';
import { ErrorDeApi, cerrarSesion, obtenerAdminActual } from '@/lib/api';
import { cn } from '@/lib/utils';

const PESTANAS = [
  { href: '/cuestionarios', etiqueta: 'Cuestionarios' },
  { href: '/estadisticas', etiqueta: 'Estadísticas' },
] as const;

export function EncabezadoPanel() {
  const pathname = usePathname();
  const router = useRouter();

  const [usuario, setUsuario] = useState<string | null>(null);
  const [saliendo, setSaliendo] = useState(false);

  useEffect(() => {
    let cancelado = false;

    obtenerAdminActual()
      .then((admin) => {
        if (!cancelado) {
          setUsuario(admin.username);
        }
      })
      .catch(async (error: unknown) => {
        // El middleware solo comprueba que la cookie exista; la validación
        // real de la firma ocurre aquí, contra la API.
        //
        // Solo se actúa ante un 401. Un fallo de red (ErrorDeApi con status 0)
        // o un 502 momentáneo no significan que la sesión sea inválida, y
        // cerrarla dejaría fuera al admin por una caída pasajera.
        if (cancelado || !(error instanceof ErrorDeApi) || error.status !== 401) {
          return;
        }

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

        if (!cancelado) {
          router.replace('/login');
          // Obliga al middleware a reevaluar la cookie ya borrada en lugar de
          // decidir con el estado previo cacheado.
          router.refresh();
        }
      });

    return () => {
      cancelado = true;
    };
  }, [router]);

  async function manejarCerrarSesion() {
    setSaliendo(true);
    try {
      await cerrarSesion();
    } finally {
      // Aunque la petición falle, conviene sacar al usuario del panel.
      router.replace('/login');
      router.refresh();
    }
  }

  return (
    <header className="border-b border-borde bg-fondo-elevado">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-6 py-3">
        <div className="flex items-center gap-3">
          <Logo alto={30} sobreFondoOscuro />
          <span className="hidden text-sm font-semibold text-texto sm:inline">
            Evaluación de Conocimientos
          </span>
        </div>

        <nav className="flex gap-1" aria-label="Secciones del panel">
          {PESTANAS.map((pestana) => {
            const activa = pathname.startsWith(pestana.href);
            return (
              <Link
                key={pestana.href}
                href={pestana.href}
                aria-current={activa ? 'page' : undefined}
                className={cn(
                  'rounded-md px-4 py-2 text-sm font-medium transition-colors',
                  activa
                    ? 'bg-primario-suave text-primario'
                    : 'text-texto-suave hover:bg-fondo-sutil hover:text-texto',
                )}
              >
                {pestana.etiqueta}
              </Link>
            );
          })}
        </nav>

        <div className="flex items-center gap-3">
          {usuario && <span className="text-sm text-texto-suave">{usuario}</span>}
          <Button
            variante="fantasma"
            tamano="sm"
            onClick={manejarCerrarSesion}
            cargando={saliendo}
          >
            Salir
          </Button>
        </div>
      </div>
    </header>
  );
}
