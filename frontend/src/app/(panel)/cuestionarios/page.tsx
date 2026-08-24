'use client';

import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense } from 'react';

import { PanelCuestionarios } from '@/components/cuestionarios/PanelCuestionarios';
import { PanelEstadisticas } from '@/components/estadisticas/PanelEstadisticas';
import { Pestanas } from '@/components/ui/Pestanas';
import { useTraduccion } from '@/lib/i18n';

type Vista = 'cuestionarios' | 'estadisticas';

function esVista(valor: string | null): valor is Vista {
  return valor === 'cuestionarios' || valor === 'estadisticas';
}

/**
 * Cuestionarios y Estadísticas, en dos pestañas internas.
 *
 * La pestaña activa viaja en la query (`?vista=estadisticas`) y no en el
 * estado: así la liga se puede compartir y sobrevive a una recarga.
 */
export default function PaginaCuestionarios() {
  return (
    // `useSearchParams` obliga a un límite de Suspense para que Next pueda
    // prerenderizar la ruta.
    <Suspense fallback={null}>
      <ContenidoCuestionarios />
    </Suspense>
  );
}

function ContenidoCuestionarios() {
  const t = useTraduccion();
  const router = useRouter();
  const parametros = useSearchParams();

  const vistaParametro = parametros.get('vista');
  const vista: Vista = esVista(vistaParametro) ? vistaParametro : 'cuestionarios';

  function cambiar(clave: string) {
    const nuevos = new URLSearchParams(parametros.toString());

    if (clave === 'cuestionarios') {
      nuevos.delete('vista');
    } else {
      nuevos.set('vista', clave);
    }

    const consulta = nuevos.toString();
    // `scroll: false` evita el salto al inicio al cambiar de pestaña.
    router.replace(consulta ? `/cuestionarios?${consulta}` : '/cuestionarios', {
      scroll: false,
    });
  }

  return (
    <div className="flex flex-col gap-6">
      <Pestanas
        etiqueta={t('cuestionarios.pestanas')}
        activa={vista}
        onCambiar={cambiar}
        pestanas={[
          { clave: 'cuestionarios', etiqueta: t('cuestionarios.pestanaCuestionarios') },
          { clave: 'estadisticas', etiqueta: t('cuestionarios.pestanaEstadisticas') },
        ]}
      />

      {vista === 'cuestionarios' ? <PanelCuestionarios /> : <PanelEstadisticas />}
    </div>
  );
}
