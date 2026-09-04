'use client';

import Link from 'next/link';
import { useCallback, useEffect, useRef, useState } from 'react';

import {
  obtenerAvisos,
  obtenerAvisosExtintores,
  obtenerAvisosPciMtto,
} from '@/lib/api';
import { alCambiarAvisos } from '@/lib/avisos';
import { bilingue, useIdioma } from '@/lib/i18n';
import { useSesion } from '@/lib/sesion';
import type {
  AvisoExtintor,
  AvisoPciMtto,
  AvisoVencimiento,
  Modulo,
} from '@/lib/types';
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
 * Campana de avisos, a un lado del selector de idioma.
 *
 * Junta dos fuentes y cada una decide su propia ventana en el servidor: los
 * estudios que vencen dentro del próximo mes o ya vencieron
 * (`GET /api/estudios/avisos`), y los meses sin explicar del control PCI MTTO
 * (`GET /api/controles/pci-mtto/avisos`).
 *
 * Tres reglas que sostienen que sean dos y no una:
 *
 * - **Solo se pide lo que el usuario puede ver.** Pedir el endpoint de un
 *   módulo sin permiso devolvería 403 en cada carga del panel.
 * - **Las peticiones van con `allSettled`.** Que una fuente falle no puede
 *   dejar la campana en blanco: se pintan las que sí respondieron.
 * - **El texto lo pone el panel, no el backend.** Las dos APIs mandan datos
 *   —fechas, meses, días— y aquí se arma la frase con `t()` e `Intl` (regla 6).
 *
 * Solo desaparece cuando el usuario no tiene ninguna de las dos fuentes.
 */

/** Un aviso ya listo para pintarse, venga de donde venga. */
interface AvisoCampana {
  /** Prefijado por origen: los ids de dos módulos no deben confundirse. */
  id: string;
  modulo: Modulo;
  titulo: string;
  cuando: string;
  urgente: boolean;
  href: string;
}
export function Notificaciones() {
  const { t, locale } = useIdioma();
  const { puede } = useSesion();

  const [avisos, setAvisos] = useState<AvisoCampana[]>([]);
  const [abierto, setAbierto] = useState(false);
  const [vistos, setVistos] = useState<string[]>([]);
  const contenedor = useRef<HTMLDivElement>(null);

  const verEstudios = puede('estudios');
  const verControles = puede('controles');
  const tieneAlguna = verEstudios || verControles;

  /** "Vence en 12 días", "Venció hace 3 días"… */
  // Se tipa por lo único que mira —los días— y no por un schema concreto:
  // lo comparten los vencimientos de Estudios y los de Extintores.
  const cuandoVence = useCallback(
    (aviso: { dias: number }): string => {
      if (aviso.dias === 0) return t('avisos.venceHoy');
      if (aviso.dias === 1) return t('avisos.venceManana');
      if (aviso.dias === -1) return t('avisos.vencioAyer');
      if (aviso.dias < 0) return t('avisos.vencioHace', { dias: -aviso.dias });
      return t('avisos.venceEn', { dias: aviso.dias });
    },
    [t],
  );

  const deEstudios = useCallback(
    (aviso: AvisoVencimiento): AvisoCampana => ({
      id: `estudio:${aviso.id}`,
      modulo: 'estudios',
      // El nombre del estudio es dato capturado: no se traduce nunca.
      titulo: aviso.estudio,
      cuando: `${cuandoVence(aviso)} · ${formatearFechaIso(aviso.fecha_vencimiento, locale)}`,
      urgente: aviso.vencido,
      href: '/estudios',
    }),
    [cuandoVence, locale],
  );

  const dePciMtto = useCallback(
    (aviso: AvisoPciMtto): AvisoCampana => {
      const mes = new Intl.DateTimeFormat(locale, {
        month: 'long',
        year: 'numeric',
      }).format(new Date(aviso.anio, aviso.mes - 1, 1));

      return {
        id: `pci:${aviso.id}`,
        modulo: 'controles',
        titulo: t('pciMtto.avisoTitulo'),
        cuando: t('pciMtto.avisoMes', { mes }),
        // Un mes sin explicar siempre corre prisa: por eso lo levantó el
        // sistema en lugar de esperar a que alguien lo capturara.
        urgente: true,
        href: '/controles?control=pci-mtto',
      };
    },
    [locale, t],
  );

  const deExtintor = useCallback(
    (aviso: AvisoExtintor): AvisoCampana => ({
      // Prefijado por origen: los ids de dos módulos no deben confundirse.
      id: `extintor:${aviso.id}`,
      modulo: 'controles',
      // El folio y la ubicación son dato capturado: no se traducen.
      titulo: t('extintores.avisoTitulo', {
        folio: aviso.folio,
        ubicacion: aviso.ubicacion,
      }),
      cuando: `${cuandoVence(aviso)} · ${formatearFechaIso(aviso.fecha_vencimiento, locale)}`,
      urgente: aviso.vencido,
      href: '/controles?control=extintores',
    }),
    [cuandoVence, locale, t],
  );

  const cargar = useCallback(async () => {
    // `allSettled` y no `all`: si una fuente falla o devuelve 403, la campana
    // sigue mostrando la otra en lugar de quedarse vacía.
    const [estudios, pci, extintores] = await Promise.allSettled([
      verEstudios ? obtenerAvisos() : Promise.resolve(null),
      verControles ? obtenerAvisosPciMtto() : Promise.resolve(null),
      verControles ? obtenerAvisosExtintores() : Promise.resolve(null),
    ]);

    const reunidos: AvisoCampana[] = [];

    if (estudios.status === 'fulfilled' && estudios.value !== null) {
      reunidos.push(...estudios.value.avisos.map(deEstudios));
    }

    if (pci.status === 'fulfilled' && pci.value !== null) {
      reunidos.push(...pci.value.avisos.map(dePciMtto));
    }

    if (extintores.status === 'fulfilled' && extintores.value !== null) {
      reunidos.push(...extintores.value.avisos.map(deExtintor));
    }

    // Lo urgente primero; dentro de cada grupo se conserva el orden que dio
    // el servidor, que ya viene por fecha.
    reunidos.sort((a, b) => Number(b.urgente) - Number(a.urgente));

    setAvisos(reunidos);
  }, [verEstudios, verControles, deEstudios, dePciMtto, deExtintor]);

  useEffect(() => {
    if (!tieneAlguna) {
      return;
    }

    setVistos(leerVistos());
    void cargar();

    // Al guardar en cualquiera de las pestañas que la alimentan el conteo pudo
    // cambiar, y al volver a la pestaña puede haber pasado un día.
    const dejarDeEscuchar = alCambiarAvisos(() => void cargar());
    const alVolver = () => void cargar();
    window.addEventListener('focus', alVolver);

    return () => {
      dejarDeEscuchar();
      window.removeEventListener('focus', alVolver);
    };
  }, [tieneAlguna, cargar]);

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

  if (!tieneAlguna) {
    return null;
  }

  const total = avisos.length;
  const hayNuevos = avisos.some((aviso) => !vistos.includes(aviso.id));

  // Un pie por módulo del que haya avisos: el enlace fijo a /estudios dejaría
  // sin salida a quien viene por el aviso de un control.
  const modulos = [...new Set(avisos.map((aviso) => aviso.modulo))];

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
            {bilingue(t('avisos.titulo'))}
          </p>

          {total === 0 ? (
            <p className="px-3 py-3 text-sm text-texto-suave">
              {bilingue(t('avisos.vacio'))}
            </p>
          ) : (
            <ul className="max-h-80 overflow-y-auto">
              {avisos.map((aviso) => (
                <li key={aviso.id} className="border-b border-borde last:border-b-0">
                  <Link
                    href={aviso.href}
                    onClick={() => setAbierto(false)}
                    className="block px-3 py-2 hover:bg-fondo-sutil"
                  >
                    <p className="text-sm text-texto">{bilingue(aviso.titulo)}</p>
                    <p
                      className={cn(
                        'mt-0.5 text-xs',
                        aviso.urgente ? 'font-semibold text-error' : 'text-alerta',
                      )}
                    >
                      {bilingue(aviso.cuando)}
                    </p>
                  </Link>
                </li>
              ))}
            </ul>
          )}

          {modulos.includes('estudios') && (
            <Link
              href="/estudios"
              onClick={() => setAbierto(false)}
              className="block border-t border-borde px-3 py-2 text-sm text-primario hover:bg-fondo-sutil"
            >
              {bilingue(t('avisos.verTodos'))}
            </Link>
          )}

          {modulos.includes('controles') && (
            <Link
              href="/controles?control=pci-mtto"
              onClick={() => setAbierto(false)}
              className="block border-t border-borde px-3 py-2 text-sm text-primario hover:bg-fondo-sutil"
            >
              {bilingue(t('avisos.verControles'))}
            </Link>
          )}
        </div>
      )}
    </div>
  );
}
