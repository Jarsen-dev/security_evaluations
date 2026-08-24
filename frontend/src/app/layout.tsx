import type { Metadata, Viewport } from 'next';

import './globals.css';

export const metadata: Metadata = {
  title: 'Sistema ESH',
  description:
    'Sistema interno del departamento de seguridad: evaluaciones de ' +
    'conocimientos y controles ESH.',
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  // El formulario público se contesta en celulares: sin esto, iOS hace zoom
  // automático al enfocar un input.
  maximumScale: 5,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  );
}
