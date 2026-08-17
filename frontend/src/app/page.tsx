import { redirect } from 'next/navigation';

/**
 * Raíz del sitio: manda al panel.
 *
 * Si no hay cookie de sesión, el middleware intercepta /cuestionarios y
 * redirige al login.
 */
export default function PaginaInicio() {
  redirect('/cuestionarios');
}
