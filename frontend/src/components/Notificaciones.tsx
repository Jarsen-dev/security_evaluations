'use client';

import Link from 'next/link';
import { useCallback, useEffect, useRef, useState } from 'react';

import { obtenerAvisos } from '@/lib/api';
import { alCambiarVencimientos } from '@/lib/avisos';
import { useIdioma } from '@/lib/i18n';
import { useSesion } from '@/lib/sesion';
import type { AvisoVencimiento } from '@/lib/types';
import { formatearFechaIso } from '@/lib/utils';
import { cn } from '@/lib/utils';

/**
 * Qué avisos ya vio esta persona, para no repintar el punto de "nuevo" cada
 * vez que abre el panel. Es una comodidad por navegador, no un dato del
 * sistema: si se pierde, lo único que pasa es que el punto vuelve a salir.
 */
const CLAVE_VISTOS = 'esh_avisos_vistos';

function leerVistos(): string[] {
  if (typeof window === 'undefined') {
    return [];
  }

  try {
    const guardado = window.localStorage.getItem(CLAVE_VISTOS);
    const datos: unknown = guardado === null ? [] : JSON.parse(guardado);
    return Array.isArray(datos) ? datos.filter((id): id is string => typeof id === 'string') : [];
  } catch {
    // Almacenamiento bloqueado o contenido corrupto: se empieza de cero.
    return [];
  }
}

function guardarVistos(ids: string[]): void {
  try {
    window.localStorage.setItem(CLAVE_VISTOS, JSON.stringify(ids));
  } catch {
    // Sin almacenamiento el aviso sigue funcionando; solo no se recuerda.
  }
}

/**
 * Campana de vencimientos, a un lado del selector de idioma.
 *
 * Avisa de los estudios que vencen dentro del próximo mes y de los que ya
 * vencieron. La ventana la decide el backend: aquí solo se dibuja lo que
 * devuelve `GET /api/estudios/avisos`.
 *
 * No se dibuja para quien no tiene el módulo de estudios: pedir ese endpoint
 * le devolvería 403 en cada carga del panel.
 */
export function Notificaciones() {
  const { t, locale } = useIdioma();
  const { puede } = useSesion();

  const [avisos, setAvisos] = useState<AvisoVencimiento[]>([]);
  const [abierto, setAbierto] = useState(false);
  const [vistos, setVistos] = useState<string[]>([]);
  const contenedor = useRef<HTMLDivElement>(null);

  const tieneAcceso = puede('estudios');

  const cargar = useCallback(async () => {
    try {
      setAvisos((await obtenerAvisos()).avisos);
    } catch {
      // Un fallo aquí no debe estorbar el panel: la campana se queda sin
      // contador hasta la siguiente carga, y el resto sigue funcionando.
      setAvisos([]);
    }
  }, []);

  useEffect(() => {
    if (!tieneAcceso) {
      return;
    }

    setVistos(leerVistos());
    void cargar();

    // Al guardar o borrar un estudio la fecha pudo cambiar, y al volver a la
    // pestaña puede haber pasado un día.
    const dejarDeEscuchar = alCambiarVencimientos(() => void cargar());
    const alVolver = () => void cargar();
    window.addEventListener('focus', alVolver);

    return () => {
      dejarDeEscuchar();
      window.removeEventListener('focus', alVolver);
    };
  }, [tieneAcceso, cargar]);

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

  if (!tieneAcceso) {
    return null;
  }

  const total = avisos.length;
  const hayNuevos = avisos.some((aviso) => !vistos.includes(aviso.id));

  function alternar() {
    const siguiente = !abierto;
    setAbierto(siguiente);

    if (siguiente && total > 0) {
      // Abrirla cuenta como haberlos leído: el conteo sigue, el punto no.
      const ids = avisos.map((aviso) => aviso.id);
      setVistos(ids);
      guardarVistos(ids);
    }
  }

  /** "Vence en 12 días", "Venció hace 3 días"… */
  function cuando(aviso: AvisoVencimiento): string {
    if (aviso.dias === 0) return t('avisos.venceHoy');
    if (aviso.dias === 1) return t('avisos.venceManana');
    if (aviso.dias === -1) return t('avisos.vencioAyer');
    if (aviso.dias < 0) return t('avisos.vencioHace', { dias: -aviso.dias });
    return t('avisos.venceEn', { dias: aviso.dias });
  }

  return (
    <div className="relative" ref={contenedor}>
      <button
        type="button"
        onClick={alternar}
        aria-haspopup="menu"
        aria-expanded={abierto}
        aria-label={t('avisos.abrir')}
        title={t('avisos.abrir')}
        className={cn(
          'relative inline-flex h-8 items-center gap-1.5 rounded-md border border-borde px-2.5',
          'text-sm font-medium text-texto-suave transition-colors',
          'hover:border-borde-fuerte hover:text-texto',
        )}
      >
        <span aria-hidden="true">🔔</span>
        {total > 0 && (
          <span
            className={cn(
              'rounded-full px-1.5 text-xs font-semibold',
              hayNuevos ? 'bg-error text-white' : 'bg-fondo-sutil text-texto-suave',
            )}
          >
            {total}
          </span>
        )}
      </button>

      {abierto && (
        <div
          role="menu"
          className="absolute right-0 z-40 mt-1 w-80 rounded-md border border-borde bg-fondo-elevado py-1 shadow-xl"
        >
          <p className="border-b border-borde px-3 py-2 text-sm font-semibold text-texto">
            {t('avisos.titulo')}
          </p>

          {total === 0 ? (
            <p className="px-3 py-3 text-sm text-texto-suave">{t('avisos.vacio')}</p>
          ) : (
            <ul className="max-h-80 overflow-y-auto">
              {avisos.map((aviso) => (
                <li key={aviso.id} className="border-b border-borde px-3 py-2 last:border-b-0">
                  <p className="text-sm text-texto">{aviso.estudio}</p>
                  <p className="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs">
                    <span className={aviso.vencido ? 'font-semibold text-error' : 'text-alerta'}>
                      {cuando(aviso)}
                    </span>
                    <span className="text-texto-tenue">
                      {formatearFechaIso(aviso.fecha_vencimiento, locale)}
                    </span>
                  </p>
                </li>
              ))}
            </ul>
          )}

          <Link
            href="/estudios"
            onClick={() => setAbierto(false)}
            className="block border-t border-borde px-3 py-2 text-sm text-primario hover:bg-fondo-sutil"
          >
            {t('avisos.verTodos')}
          </Link>
        </div>
      )}
    </div>
  );
}
