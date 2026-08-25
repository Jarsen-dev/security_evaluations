'use client';

import { useTraduccion } from '@/lib/i18n';
import { useSesion } from '@/lib/sesion';
import type { Modulo } from '@/lib/types';

/**
 * Corta una pestaña completa cuando el usuario no tiene acceso a su módulo.
 *
 * El encabezado ya no ofrece la pestaña, pero la URL se puede teclear. Sin
 * esto la pantalla se dibujaba entera y cada consulta devolvía 403, dejando
 * un formulario que no sirve para nada junto a un mensaje de error suelto.
 *
 * Es cosmética, igual que esconder los botones: quien autoriza de verdad es
 * la API en cada endpoint.
 */
export function GuardiaModulo({
  modulo,
  children,
}: {
  modulo: Modulo;
  children: React.ReactNode;
}) {
  const t = useTraduccion();
  const { puede, cargando } = useSesion();

  if (cargando) {
    return <p className="text-sm text-texto-suave">{t('comun.cargando')}</p>;
  }

  if (!puede(modulo)) {
    return (
      <div
        role="alert"
        className="rounded-tarjeta border border-error bg-error-suave px-4 py-3 text-sm text-texto"
      >
        {t('comun.sinAcceso')}
      </div>
    );
  }

  return <>{children}</>;
}
