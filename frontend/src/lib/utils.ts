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

/**
 * Formatea una fecha `YYYY-MM-DD` en el idioma activo.
 *
 * No se usa `new Date('2026-08-24')` directo: esa forma se interpreta como
 * medianoche UTC y, con el huso de la planta (UTC-6/-7), al mostrarla en hora
 * local sale el día anterior. Se arma con los componentes para que la fecha
 * sea la misma que se capturó.
 */
export function formatearFechaIso(iso: string, locale: string): string {
  const [anio, mes, dia] = iso.split('-').map(Number);

  if (anio === undefined || mes === undefined || dia === undefined) {
    return iso;
  }

  return new Date(anio, mes - 1, dia).toLocaleDateString(locale, {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  });
}

/** Fecha de hoy en formato `YYYY-MM-DD`, en hora local. */
export function fechaDeHoy(): string {
  const ahora = new Date();
  const mes = String(ahora.getMonth() + 1).padStart(2, '0');
  const dia = String(ahora.getDate()).padStart(2, '0');
  return `${ahora.getFullYear()}-${mes}-${dia}`;
}

/** Primer y último día del mes al que pertenece una fecha `YYYY-MM-DD`. */
export function rangoDelMes(iso: string): { desde: string; hasta: string } {
  const [anio = 0, mes = 1] = iso.split('-').map(Number);
  // El día 0 del mes siguiente es el último del mes pedido.
  const ultimo = new Date(anio, mes, 0).getDate();
  const mesTexto = String(mes).padStart(2, '0');

  return {
    desde: `${anio}-${mesTexto}-01`,
    hasta: `${anio}-${mesTexto}-${String(ultimo).padStart(2, '0')}`,
  };
}
