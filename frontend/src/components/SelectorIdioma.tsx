'use client';

import { useEffect, useRef, useState } from 'react';

import { IDIOMAS, useIdioma, type Idioma } from '@/lib/i18n';
import { cn } from '@/lib/utils';

/**
 * Menú para cambiar el idioma del panel.
 *
 * Sin banderas: ni el inglés ni el coreano corresponden a un solo país, y en
 * planta se lee mejor el código de dos letras.
 */
export function SelectorIdioma() {
  const { idioma, cambiarIdioma, t } = useIdioma();
  const [abierto, setAbierto] = useState(false);
  const contenedor = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!abierto) {
      return;
    }

    function alHacerClic(evento: MouseEvent) {
      if (!contenedor.current?.contains(evento.target as Node)) {
        setAbierto(false);
      }
    }

    function alPresionarTecla(evento: KeyboardEvent) {
      if (evento.key === 'Escape') {
        setAbierto(false);
      }
    }

    document.addEventListener('mousedown', alHacerClic);
    document.addEventListener('keydown', alPresionarTecla);

    return () => {
      document.removeEventListener('mousedown', alHacerClic);
      document.removeEventListener('keydown', alPresionarTecla);
    };
  }, [abierto]);

  const actual =
    IDIOMAS.find((opcion) => opcion.codigo === idioma) ?? { corto: 'ES' };

  function elegir(codigo: Idioma) {
    cambiarIdioma(codigo);
    setAbierto(false);
  }

  return (
    <div className="relative" ref={contenedor}>
      <button
        type="button"
        onClick={() => setAbierto((previo) => !previo)}
        aria-haspopup="menu"
        aria-expanded={abierto}
        aria-label={t('encabezado.cambiarIdioma')}
        title={t('encabezado.cambiarIdioma')}
        className={cn(
          'inline-flex h-8 items-center gap-1.5 rounded-md border border-borde px-2.5',
          'text-sm font-medium text-texto-suave transition-colors',
          'hover:border-borde-fuerte hover:text-texto',
        )}
      >
        <span aria-hidden="true">🌐</span>
        {actual.corto}
      </button>

      {abierto && (
        <div
          role="menu"
          className="absolute right-0 z-40 mt-1 min-w-[9rem] rounded-md border border-borde bg-fondo-elevado py-1 shadow-xl"
        >
          {IDIOMAS.map((opcion) => (
            <button
              key={opcion.codigo}
              type="button"
              role="menuitemradio"
              aria-checked={opcion.codigo === idioma}
              onClick={() => elegir(opcion.codigo)}
              className={cn(
                'flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm transition-colors',
                opcion.codigo === idioma
                  ? 'bg-primario-suave text-primario'
                  : 'text-texto-suave hover:bg-fondo-sutil hover:text-texto',
              )}
            >
              {opcion.etiqueta}
              <span className="text-xs text-texto-tenue">{opcion.corto}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
