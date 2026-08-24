import { EncabezadoPanel } from '@/components/EncabezadoPanel';
import { ProveedorToast } from '@/components/ui/Toast';
import { ProveedorIdioma } from '@/lib/i18n';

/**
 * Layout del panel de administración: encabezado con las pestañas y el
 * selector de idioma.
 *
 * El grupo de rutas `(panel)` no aparece en la URL, así que /cuestionarios,
 * /controles e /inventario comparten este layout sin prefijo. El formulario
 * público `/r/[token]` queda fuera y no hereda nada de aquí: sigue en
 * español y sin sesión.
 */
export default function LayoutPanel({ children }: { children: React.ReactNode }) {
  return (
    <ProveedorIdioma>
      <ProveedorToast>
        <div className="min-h-screen bg-fondo">
          <EncabezadoPanel />
          <main className="mx-auto max-w-7xl px-6 py-8">{children}</main>
        </div>
      </ProveedorToast>
    </ProveedorIdioma>
  );
}
