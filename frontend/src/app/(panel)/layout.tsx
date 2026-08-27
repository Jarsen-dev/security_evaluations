import { EncabezadoPanel } from '@/components/EncabezadoPanel';
import { ProveedorToast } from '@/components/ui/Toast';
import { ProveedorIdioma } from '@/lib/i18n';
import { ProveedorSesion } from '@/lib/sesion';

/**
 * Layout del panel de administración: encabezado con las pestañas y el
 * selector de idioma.
 *
 * El grupo de rutas `(panel)` no aparece en la URL, así que /cuestionarios,
 * /controles, /inventario y /administracion comparten este layout sin
 * prefijo. El formulario público `/r/[token]` queda fuera y no hereda nada
 * de aquí: sigue en español y sin sesión.
 */
export default function LayoutPanel({ children }: { children: React.ReactNode }) {
  return (
    <ProveedorIdioma>
      <ProveedorToast>
        <ProveedorSesion>
          <div className="min-h-screen bg-fondo">
            <EncabezadoPanel />
            {/* 96rem (antes 80rem/max-w-7xl): en laptops de plantilla de
                ~1366-1440px el contenedor angosto dejaba menos ancho útil que
                la pantalla, y forzaba scroll lateral en tablas y en la barra
                de pestañas de Controles (ver el comentario en Pestanas.tsx).
                Sigue habiendo margen a los lados en monitores anchos. */}
            <main className="mx-auto max-w-[96rem] px-6 py-8">{children}</main>
          </div>
        </ProveedorSesion>
      </ProveedorToast>
    </ProveedorIdioma>
  );
}
