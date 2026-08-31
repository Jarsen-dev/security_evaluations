'use client';

import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense } from 'react';

import { GuardiaModulo } from '@/components/GuardiaModulo';
import { PanelRecepciones } from '@/components/inventario/recepciones/PanelRecepciones';
import { TablaRecepciones } from '@/components/inventario/recepciones/TablaRecepciones';
import { Pestanas } from '@/components/ui/Pestanas';
import { bilingue, useTraduccion, type ClaveTraduccion } from '@/lib/i18n';

/**
 * Inventario.
 *
 * De momento tiene una sola función: recibir mercancía fotografiando la
 * remisión del proveedor. Cada recepción confirmada suma la existencia de los
 * insumos del catálogo, así que es la entrada del inventario.
 */
const SECCIONES: ReadonlyArray<{ clave: Seccion; etiqueta: ClaveTraduccion }> = [
  { clave: 'recepciones', etiqueta: 'inventario.recepciones' },
  { clave: 'historial', etiqueta: 'inventario.historial' },
];

type Seccion = 'recepciones' | 'historial';

const POR_DEFECTO: Seccion = 'recepciones';

function esSeccion(valor: string | null): valor is Seccion {
  return valor === 'recepciones' || valor === 'historial';
}

export default function PaginaInventario() {
  return (
    // `useSearchParams` obliga a un límite de Suspense para prerenderizar.
    <Suspense fallback={null}>
      <GuardiaModulo modulo="inventario">
        <ContenidoInventario />
      </GuardiaModulo>
    </Suspense>
  );
}

function ContenidoInventario() {
  const t = useTraduccion();
  const router = useRouter();
  const parametros = useSearchParams();

  const solicitada = parametros.get('seccion');
  const activa: Seccion = esSeccion(solicitada) ? solicitada : POR_DEFECTO;

  function cambiar(clave: string) {
    // La sección viaja en la query: la liga se puede compartir y sobrevive a
    // la recarga.
    router.replace(
      clave === POR_DEFECTO ? '/inventario' : `/inventario?seccion=${clave}`,
      { scroll: false },
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-texto">{bilingue(t('inventario.titulo'))}</h1>
        <p className="mt-1 text-sm text-texto-suave">{bilingue(t('inventario.descripcion'))}</p>
      </div>

      <Pestanas
        etiqueta={t('inventario.titulo')}
        activa={activa}
        onCambiar={cambiar}
        pestanas={SECCIONES.map((seccion) => ({
          clave: seccion.clave,
          etiqueta: t(seccion.etiqueta),
        }))}
      />

      {activa === 'recepciones' ? <PanelRecepciones /> : <TablaRecepciones />}
    </div>
  );
}
