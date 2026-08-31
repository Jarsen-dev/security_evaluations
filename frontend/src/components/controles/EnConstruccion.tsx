import { bilingue, useTraduccion } from '@/lib/i18n';

/**
 * Aviso para los controles que todavía se llevan en papel.
 *
 * Las pestañas se muestran desde ahora aunque no capturen nada: así se ve la
 * forma final del módulo y quien lo usa sabe qué falta por migrar.
 */
export function EnConstruccion({ nombre }: { nombre: string }) {
  const t = useTraduccion();

  return (
    <div className="rounded-tarjeta border border-dashed border-borde bg-fondo-elevado px-6 py-12 text-center">
      <p className="text-base font-medium text-texto">{bilingue(nombre)}</p>
      <p className="mt-1 text-sm font-medium text-alerta">
        {bilingue(t('controles.enConstruccion'))}
      </p>
      <p className="mx-auto mt-3 max-w-md text-sm text-texto-suave">
        {bilingue(t('controles.enConstruccionDetalle'))}
      </p>
    </div>
  );
}
