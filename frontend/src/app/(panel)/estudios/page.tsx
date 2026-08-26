'use client';

import { GuardiaModulo } from '@/components/GuardiaModulo';
import { PanelEstudios } from '@/components/estudios/PanelEstudios';

/**
 * Estudios normativos y capacitaciones.
 *
 * A diferencia de Controles, no tiene sub-pestañas: es una sola tabla con su
 * formulario, así que no hay nada que llevar en la query.
 */
export default function PaginaEstudios() {
  return (
    <GuardiaModulo modulo="estudios">
      <PanelEstudios />
    </GuardiaModulo>
  );
}
