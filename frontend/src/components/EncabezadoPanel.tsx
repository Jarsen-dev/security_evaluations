'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useState } from 'react';

import { SelectorIdioma } from '@/components/SelectorIdioma';
import { Button } from '@/components/ui/Button';
import { Logo } from '@/components/ui/Logo';
import { cerrarSesion } from '@/lib/api';
import { useTraduccion, type ClaveTraduccion } from '@/lib/i18n';
import { useSesion } from '@/lib/sesion';
import type { Modulo } from '@/lib/types';
import { cn } from '@/lib/utils';

// Estadísticas ya no es una pestaña principal: vive dentro de Cuestionarios.
//
// `modulo` decide quién ve cada pestaña. Administración no tiene módulo
// porque no se otorga por permisos: es solo del superadministrador.
const PESTANAS: ReadonlyArray<{
  href: string;
  clave: ClaveTraduccion;
  modulo: Modulo | null;
}> = [
  { href: '/cuestionarios', clave: 'encabezado.cuestionarios', modulo: 'cuestionarios' },
  { href: '/controles', clave: 'encabezado.controles', modulo: 'controles' },
  { href: '/inventario', clave: 'encabezado.inventario', modulo: 'inventario' },
  { href: '/administracion', clave: 'encabezado.administracion', modulo: null },
];

export function EncabezadoPanel() {
  const pathname = usePathname();
  const router = useRouter();
  const t = useTraduccion();

  const { usuario, puede } = useSesion();
  const [saliendo, setSaliendo] = useState(false);

  // Se filtra contra los permisos para no ofrecer pestañas que devolverían
  // 403 en la primera llamada. La autorización real la aplica la API.
  const visibles = PESTANAS.filter((pestana) =>
    pestana.modulo === null ? usuario?.es_superadmin === true : puede(pestana.modulo),
  );

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
            {t('encabezado.titulo')}
          </span>
        </div>

        <nav className="flex gap-1" aria-label={t('encabezado.secciones')}>
          {visibles.map((pestana) => {
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
                {t(pestana.clave)}
              </Link>
            );
          })}
        </nav>

        <div className="flex items-center gap-3">
          <SelectorIdioma />
          {usuario && (
            <span className="hidden text-sm text-texto-suave sm:inline">
              {usuario.username}
            </span>
          )}
          <Button
            variante="fantasma"
            tamano="sm"
            onClick={manejarCerrarSesion}
            cargando={saliendo}
          >
            {t('encabezado.salir')}
          </Button>
        </div>
      </div>
    </header>
  );
}
