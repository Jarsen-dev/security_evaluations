/** Utilidades pequeñas compartidas por los componentes. */

/**
 * Une clases de Tailwind descartando las condicionales que no aplican.
 *
 * Equivale a `clsx` para el uso que le damos; se implementa aquí para no
 * sumar una dependencia por diez líneas.
 */
export function cn(...clases: Array<string | false | null | undefined>): string {
  return clases.filter(Boolean).join(' ');
}
