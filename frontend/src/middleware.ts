import { NextResponse, type NextRequest } from 'next/server';

/**
 * Guardia de navegación del panel.
 *
 * IMPORTANTE: esto solo comprueba que la cookie de sesión exista. No valida
 * la firma del JWT, y no debe hacerlo: la llave secreta vive en el backend.
 * La autorización real la aplica la API en cada endpoint; este middleware
 * únicamente evita el parpadeo de cargar el panel para luego rebotar al
 * login. Un token vencido o falsificado pasa de aquí, pero recibe 401 en la
 * primera llamada a la API y `ProveedorSesion` redirige al login.
 *
 * Tampoco comprueba PERMISOS, por lo mismo: no puede leer el contenido del
 * token. Quien entre a /administracion sin ser superadministrador verá la
 * pantalla pedir los datos y recibir un 403 de la API.
 */

const COOKIE_SESION = 'evaluaciones_sesion';

const RUTAS_PROTEGIDAS = [
  '/cuestionarios',
  '/controles',
  '/inventario',
  '/estudios',
  '/catalogo',
  '/rondines',
  '/administracion',
];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  // `cookies.has()` da true con una cookie de valor vacío; se exige contenido
  // para que `evaluaciones_sesion=` no pase el guardia.
  const tieneSesion = (request.cookies.get(COOKIE_SESION)?.value ?? '').length > 0;

  const esRutaProtegida = RUTAS_PROTEGIDAS.some(
    (ruta) => pathname === ruta || pathname.startsWith(`${ruta}/`),
  );

  // La raíz se resuelve aquí, no con un `redirect()` en la página: Next
  // prerenderizaba esa redirección y la respuesta cacheada perdía la cabecera
  // `Location`, dejando un 307 sin destino que colgaba al navegador. Además
  // así se llega al destino final en un solo salto.
  if (pathname === '/') {
    const url = request.nextUrl.clone();
    url.pathname = tieneSesion ? '/cuestionarios' : '/login';
    return NextResponse.redirect(url);
  }

  if (esRutaProtegida && !tieneSesion) {
    const url = request.nextUrl.clone();
    url.pathname = '/login';
    return NextResponse.redirect(url);
  }

  if (pathname === '/login' && tieneSesion) {
    const url = request.nextUrl.clone();
    url.pathname = '/cuestionarios';
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  /*
   * Se excluyen los recursos estáticos y, sobre todo, las rutas públicas
   * `/r/` (formulario) y `/re/` (captura de la foto de una remisión desde el
   * celular): ninguna lleva sesión y jamás deben redirigirse al login.
   *
   * `/p/` se retiró con el escaneo propio: los rondines los captura AppSheet.
   */
  matcher: ['/((?!api|_next/static|_next/image|favicon.ico|r/|re/).*)'],
};
