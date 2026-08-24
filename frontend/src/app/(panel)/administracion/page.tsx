'use client';

import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense } from 'react';

import { PanelLogs } from '@/components/administracion/PanelLogs';
import { PanelMantenimiento } from '@/components/administracion/PanelMantenimiento';
import { PanelUsuarios } from '@/components/administracion/PanelUsuarios';
import { Pestanas } from '@/components/ui/Pestanas';
import { useTraduccion, type ClaveTraduccion } from '@/lib/i18n';
import { useSesion } from '@/lib/sesion';

/**
 * Pestaña de Administración, solo para el superadministrador.
 *
 * El encabezado ya no la muestra a nadie más, pero alguien puede llegar
 * tecleando la URL: por eso la pantalla también comprueba el rol. La
 * defensa real está en la API, que devuelve 403 en cada endpoint.
 */
const SECCIONES: ReadonlyArray<{ clave: Seccion; etiqueta: ClaveTraduccion }> = [
  { clave: 'usuarios', etiqueta: 'administracion.usuarios' },
  { clave: 'logs', etiqueta: 'administracion.logs' },
  { clave: 'mantenimiento', etiqueta: 'administracion.mantenimiento' },
];

type Seccion = 'usuarios' | 'logs' | 'mantenimiento';

const POR_DEFECTO: Seccion = 'usuarios';

function esSeccion(valor: string | null): valor is Seccion {
  return valor === 'usuarios' || valor === 'logs' || valor === 'mantenimiento';
}

export default function PaginaAdministracion() {
  return (
    // `useSearchParams` obliga a un límite de Suspense para prerenderizar.
    <Suspense fallback={null}>
      <ContenidoAdministracion />
    </Suspense>
  );
}

function ContenidoAdministracion() {
  const t = useTraduccion();
  const router = useRouter();
  const parametros = useSearchParams();
  const { usuario, cargando } = useSesion();

  const solicitada = parametros.get('seccion');
  const activa: Seccion = esSeccion(solicitada) ? solicitada : POR_DEFECTO;

  function cambiar(clave: string) {
    // La sección viaja en la query: la liga se puede compartir y sobrevive
    // a la recarga.
    router.replace(
      clave === POR_DEFECTO ? '/administracion' : `/administracion?seccion=${clave}`,
      { scroll: false },
    );
  }

  if (cargando) {
    return <p className="text-sm text-texto-suave">{t('comun.cargando')}</p>;
  }

  if (usuario?.es_superadmin !== true) {
    return (
      <div
        role="alert"
        className="rounded-tarjeta border border-error bg-error-suave px-4 py-3 text-sm text-texto"
      >
        {t('administracion.soloSuperadmin')}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-texto">
          {t('administracion.titulo')}
        </h1>
        <p className="mt-1 text-sm text-texto-suave">
          {t('administracion.descripcion')}
        </p>
      </div>

      <Pestanas
        etiqueta={t('administracion.secciones')}
        activa={activa}
        onCambiar={cambiar}
        pestanas={SECCIONES.map((seccion) => ({
          clave: seccion.clave,
          etiqueta: t(seccion.etiqueta),
        }))}
      />

      {activa === 'usuarios' && <PanelUsuarios />}
      {activa === 'logs' && <PanelLogs />}
      {activa === 'mantenimiento' && <PanelMantenimiento />}
    </div>
  );
}
