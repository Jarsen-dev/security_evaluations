/**
 * Layout del formulario público.
 *
 * Deliberadamente sin nada del panel de administración: ni encabezado, ni
 * pestañas, ni sesión. Y en tema CLARO de alto contraste, no oscuro: se
 * contesta en celulares bajo la luz de la nave industrial, donde una
 * pantalla oscura se vuelve un espejo.
 */
export default function LayoutPublico({ children }: { children: React.ReactNode }) {
  return <div className="min-h-screen bg-claro-fondo text-claro-texto">{children}</div>;
}
