import { EncabezadoPanel } from '@/components/EncabezadoPanel';
import { ProveedorToast } from '@/components/ui/Toast';

/**
 * Layout del panel de administración: encabezado con las dos pestañas.
 *
 * El grupo de rutas `(panel)` no aparece en la URL, así que /cuestionarios y
 * /estadisticas comparten este layout sin prefijo. El formulario público
 * `/r/[token]` queda fuera y no hereda nada de aquí.
 */
export default function LayoutPanel({ children }: { children: React.ReactNode }) {
  return (
    <ProveedorToast>
      <div className="min-h-screen bg-fondo">
        <EncabezadoPanel />
        <main className="mx-auto max-w-7xl px-6 py-8">{children}</main>
      </div>
    </ProveedorToast>
  );
}
