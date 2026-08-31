'use client';

import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense } from 'react';

import { GuardiaModulo } from '@/components/GuardiaModulo';
import { PanelPuntos } from '@/components/rondines/PanelPuntos';
import { PanelTablero } from '@/components/rondines/PanelTablero';
import { Pestanas } from '@/components/ui/Pestanas';
import { bilingue, useTraduccion, type ClaveTraduccion } from '@/lib/i18n';

/**
 * Rondines de seguridad.
 *
 * Sustituye al panel de Streamlit que leía un Google Sheets: aquí los códigos
 * QR de los puntos los genera y los recibe el propio sistema.
 */
const SECCIONES: ReadonlyArray<{ clave: Seccion; etiqueta: ClaveTraduccion }> = [
  { clave: 'tablero', etiqueta: 'rondines.tablero' },
  { clave: 'puntos', etiqueta: 'rondines.puntos' },
];

type Seccion = 'tablero' | 'puntos';

const POR_DEFECTO: Seccion = 'tablero';

function esSeccion(valor: string | null): valor is Seccion {
  return valor === 'tablero' || valor === 'puntos';
}

export default function PaginaRondines() {
  return (
    // `useSearchParams` obliga a un límite de Suspense para prerenderizar.
    <Suspense fallback={null}>
      <GuardiaModulo modulo="rondines">
        <ContenidoRondines />
      </GuardiaModulo>
    </Suspense>
  );
}

function ContenidoRondines() {
  const t = useTraduccion();
  const router = useRouter();
  const parametros = useSearchParams();

  const solicitada = parametros.get('seccion');
  const activa: Seccion = esSeccion(solicitada) ? solicitada : POR_DEFECTO;

  function cambiar(clave: string) {
    // La sección viaja en la query: la liga se puede compartir y sobrevive a
    // la recarga.
    router.replace(
      clave === POR_DEFECTO ? '/rondines' : `/rondines?seccion=${clave}`,
      { scroll: false },
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-texto">{bilingue(t('rondines.titulo'))}</h1>
        <p className="mt-1 text-sm text-texto-suave">{bilingue(t('rondines.descripcion'))}</p>
      </div>

      <Pestanas
        etiqueta={t('rondines.secciones')}
        activa={activa}
        onCambiar={cambiar}
        pestanas={SECCIONES.map((seccion) => ({
          clave: seccion.clave,
          etiqueta: t(seccion.etiqueta),
        }))}
      />

      {activa === 'tablero' ? <PanelTablero /> : <PanelPuntos />}
    </div>
  );
}
