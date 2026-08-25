'use client';

import { PanelCatalogo } from '@/components/catalogo/PanelCatalogo';
import { GuardiaModulo } from '@/components/GuardiaModulo';
import { useTraduccion } from '@/lib/i18n';

/**
 * Catálogo de insumos de seguridad.
 *
 * Es un catálogo, no un almacén: guarda qué insumos existen, dónde están y
 * entre qué topes debe moverse su existencia. El sistema de recepciones y
 * salidas se construirá encima más adelante.
 */
export default function PaginaCatalogo() {
  return (
    <GuardiaModulo modulo="catalogo">
      <ContenidoCatalogo />
    </GuardiaModulo>
  );
}

function ContenidoCatalogo() {
  const t = useTraduccion();

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-texto">{t('catalogo.titulo')}</h1>
        <p className="mt-1 text-sm text-texto-suave">{t('catalogo.descripcion')}</p>
      </div>

      <PanelCatalogo />
    </div>
  );
}
