import { redirect } from 'next/navigation';

/**
 * Raíz del sitio: manda al panel.
 *
 * En la práctica el middleware resuelve `/` antes de que esta página se
 * renderice. Se conserva como respaldo.
 *
 * `force-dynamic` no es opcional: prerenderizada, Next servía este
 * `redirect()` desde el caché sin la cabecera `Location`, y el navegador se
 * quedaba cargando ante un 307 sin destino.
 */
export const dynamic = 'force-dynamic';

export default function PaginaInicio() {
  redirect('/cuestionarios');
}
