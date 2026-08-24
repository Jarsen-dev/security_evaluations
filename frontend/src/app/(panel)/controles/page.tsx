'use client';

import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense } from 'react';

import { GuardiaModulo } from '@/components/GuardiaModulo';
import { EnConstruccion } from '@/components/controles/EnConstruccion';
import { PanelRayser } from '@/components/controles/rayser/PanelRayser';
import { PanelSqp } from '@/components/controles/sqp/PanelSqp';
import { Pestanas } from '@/components/ui/Pestanas';
import { useTraduccion, type ClaveTraduccion } from '@/lib/i18n';

/**
 * Controles del departamento de seguridad.
 *
 * Cada pestaña es una hoja del formato en papel. De momento solo capturan
 * Rayser e Inspección de SQP; las demás se muestran para que se vea la forma
 * final del módulo y se irán habilitando conforme se definan sus reglas.
 */
const CONTROLES: ReadonlyArray<{ clave: string; etiqueta: ClaveTraduccion }> = [
  { clave: 'sqp', etiqueta: 'controles.sqp' },
  { clave: 'almacen-rp', etiqueta: 'controles.almacenRp' },
  { clave: 'rayser', etiqueta: 'controles.rayser' },
  { clave: 'platicas', etiqueta: 'controles.platicas' },
  { clave: 'recorridos', etiqueta: 'controles.recorridos' },
  { clave: 'muro', etiqueta: 'controles.muro' },
  { clave: 'medicamento', etiqueta: 'controles.medicamento' },
  { clave: 'silos', etiqueta: 'controles.silos' },
  { clave: 'tableros', etiqueta: 'controles.tableros' },
];

export default function PaginaControles() {
  return (
    // `useSearchParams` obliga a un límite de Suspense para prerenderizar.
    <Suspense fallback={null}>
      <GuardiaModulo modulo="controles">
        <ContenidoControles />
      </GuardiaModulo>
    </Suspense>
  );
}

function ContenidoControles() {
  const t = useTraduccion();
  const router = useRouter();
  const parametros = useSearchParams();

  const solicitada = parametros.get('control');
  const activa =
    CONTROLES.find((control) => control.clave === solicitada)?.clave ?? 'sqp';

  function cambiar(clave: string) {
    // La pestaña viaja en la query: la liga a un control concreto se puede
    // compartir y sobrevive a la recarga.
    router.replace(clave === 'sqp' ? '/controles' : `/controles?control=${clave}`, {
      scroll: false,
    });
  }

  const actual = CONTROLES.find((control) => control.clave === activa);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-texto">{t('controles.titulo')}</h1>
        <p className="mt-1 text-sm text-texto-suave">{t('controles.descripcion')}</p>
      </div>

      <Pestanas
        etiqueta={t('controles.pestanas')}
        activa={activa}
        onCambiar={cambiar}
        pestanas={CONTROLES.map((control) => ({
          clave: control.clave,
          etiqueta: t(control.etiqueta),
        }))}
      />

      {activa === 'sqp' && <PanelSqp />}
      {activa === 'rayser' && <PanelRayser />}
      {activa !== 'sqp' && activa !== 'rayser' && actual !== undefined && (
        <EnConstruccion nombre={t(actual.etiqueta)} />
      )}
    </div>
  );
}
