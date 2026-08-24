'use client';

import { GuardiaModulo } from '@/components/GuardiaModulo';
import { useTraduccion } from '@/lib/i18n';

/**
 * Inventario de medicamento e insumos de seguridad.
 *
 * Todavía se lleva en el archivo de Excel: la pestaña existe para fijar la
 * estructura del sistema mientras se definen sus reglas de captura.
 */
export default function PaginaInventario() {
  return (
    <GuardiaModulo modulo="inventario">
      <ContenidoInventario />
    </GuardiaModulo>
  );
}

function ContenidoInventario() {
  const t = useTraduccion();

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-texto">{t('inventario.titulo')}</h1>
        <p className="mt-1 text-sm text-texto-suave">{t('inventario.descripcion')}</p>
      </div>

      <div className="rounded-tarjeta border border-dashed border-borde bg-fondo-elevado px-6 py-12 text-center">
        <p className="text-sm font-medium text-alerta">
          {t('inventario.enConstruccion')}
        </p>
        <p className="mx-auto mt-3 max-w-md text-sm text-texto-suave">
          {t('inventario.enConstruccionDetalle')}
        </p>
      </div>
    </div>
  );
}
