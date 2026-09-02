'use client';

import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, type ReactNode } from 'react';

import { GuardiaModulo } from '@/components/GuardiaModulo';
import { PanelRecepciones } from '@/components/inventario/recepciones/PanelRecepciones';
import { TablaRecepciones } from '@/components/inventario/recepciones/TablaRecepciones';
import { PanelStock } from '@/components/inventario/stock/PanelStock';
import { Pestanas } from '@/components/ui/Pestanas';
import { bilingue, useTraduccion, type ClaveTraduccion } from '@/lib/i18n';

/**
 * Inventario.
 *
 * Dos caras de lo mismo: recibir mercancía fotografiando la remisión del
 * proveedor, y consultar lo que hay. Cada recepción confirmada suma la
 * existencia de los insumos del catálogo —las cajas capturadas multiplicadas
 * por las piezas que trae cada una—, así que es la entrada del inventario y
 * Stock es su resultado.
 */
const SECCIONES: ReadonlyArray<{ clave: Seccion; etiqueta: ClaveTraduccion }> = [
  { clave: 'recepciones', etiqueta: 'inventario.recepciones' },
  { clave: 'stock', etiqueta: 'inventario.stock' },
  { clave: 'historial', etiqueta: 'inventario.historial' },
];

type Seccion = 'recepciones' | 'stock' | 'historial';

const POR_DEFECTO: Seccion = 'recepciones';

function esSeccion(valor: string | null): valor is Seccion {
  return SECCIONES.some((seccion) => seccion.clave === valor);
}

/** Qué pinta cada pestaña. Con tres, un ternario ya no se lee. */
const VISTAS: Record<Seccion, () => ReactNode> = {
  recepciones: () => <PanelRecepciones />,
  stock: () => <PanelStock />,
  historial: () => <TablaRecepciones />,
};

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

      {VISTAS[activa]()}
    </div>
  );
}
