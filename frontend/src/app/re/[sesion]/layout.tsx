/**
 * Layout de la página de captura desde el celular.
 *
 * Tema claro de alto contraste y sin nada del panel: se abre a pulso en la
 * nave, con guantes y bajo la luz del techo. Misma decisión que `/r/` y `/p/`.
 */
export default function LayoutCaptura({ children }: { children: React.ReactNode }) {
  return <div className="min-h-screen bg-claro-fondo text-claro-texto">{children}</div>;
}
