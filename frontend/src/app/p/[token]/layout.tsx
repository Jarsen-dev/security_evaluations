/**
 * Layout de la página de escaneo de rondines.
 *
 * Sin encabezado, sin pestañas y sin sesión: se abre desde el código QR
 * pegado en el punto de control. Va en **tema claro de alto contraste** por la
 * misma razón que el formulario público: se lee en un celular a la
 * intemperie, muchas veces de noche con una linterna o a pleno sol.
 */
export default function LayoutEscaneo({ children }: { children: React.ReactNode }) {
  return <div className="min-h-screen bg-claro-fondo text-claro-texto">{children}</div>;
}
