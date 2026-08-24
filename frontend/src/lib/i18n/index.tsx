'use client';

/**
 * Idioma del panel: español, inglés y coreano.
 *
 * En planta hay personal de las tres lenguas, así que el encabezado deja
 * cambiarlo en caliente. Solo cubre la interfaz del panel:
 *
 * - El formulario público `/r/[token]` sigue en español (lo contesta el
 *   personal de piso y se imprime en español).
 * - Los mensajes de la API también: los traduce el backend a español y ahí
 *   se quedan (regla 6 del CLAUDE.md).
 * - El contenido capturado —nombres de cuestionarios, preguntas, áreas,
 *   observaciones— nunca se traduce: es dato, no interfaz.
 *
 * No se usa ninguna librería de i18n: el panel entero ya es de cliente y
 * esto son tres diccionarios y un contexto.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

import { en } from './en';
import { es, type Diccionario } from './es';
import { ko } from './ko';

export type Idioma = 'es' | 'en' | 'ko';

export const IDIOMAS: ReadonlyArray<{ codigo: Idioma; etiqueta: string; corto: string }> = [
  { codigo: 'es', etiqueta: 'Español', corto: 'ES' },
  { codigo: 'en', etiqueta: 'English', corto: 'EN' },
  { codigo: 'ko', etiqueta: '한국어', corto: 'KO' },
];

const DICCIONARIOS: Record<Idioma, Diccionario> = { es, en, ko };

/** Locale para `Intl`: fechas y números también cambian con el idioma. */
const LOCALES: Record<Idioma, string> = {
  es: 'es-MX',
  en: 'en-US',
  ko: 'ko-KR',
};

const CLAVE_ALMACEN = 'esh_idioma';

/**
 * Rutas válidas del diccionario, en notación de punto.
 *
 * Gracias a esto, `t('encabezado.salir')` compila y `t('encabezado.salr')`
 * no: una clave mal escrita se detecta en `npm run typecheck`, no en planta.
 */
type Rutas<T> = {
  [K in keyof T & string]: T[K] extends string ? K : `${K}.${Rutas<T[K]>}`;
}[keyof T & string];

export type ClaveTraduccion = Rutas<Diccionario>;

type Valores = Record<string, string | number>;

interface ContextoIdioma {
  idioma: Idioma;
  locale: string;
  cambiarIdioma: (idioma: Idioma) => void;
  t: (clave: ClaveTraduccion, valores?: Valores) => string;
}

const Contexto = createContext<ContextoIdioma | null>(null);

function esIdioma(valor: string | null): valor is Idioma {
  return valor === 'es' || valor === 'en' || valor === 'ko';
}

/** Recorre el diccionario siguiendo la ruta con puntos. */
function buscar(diccionario: Diccionario, clave: string): string | undefined {
  let actual: unknown = diccionario;

  for (const parte of clave.split('.')) {
    if (typeof actual !== 'object' || actual === null) {
      return undefined;
    }
    actual = (actual as Record<string, unknown>)[parte];
  }

  return typeof actual === 'string' ? actual : undefined;
}

/** Sustituye los marcadores `{nombre}` por sus valores. */
function interpolar(texto: string, valores?: Valores): string {
  if (!valores) {
    return texto;
  }

  return texto.replace(/\{(\w+)\}/g, (coincidencia, nombre: string) => {
    const valor = valores[nombre];
    return valor === undefined ? coincidencia : String(valor);
  });
}

export function ProveedorIdioma({ children }: { children: ReactNode }) {
  // Se arranca siempre en español y el idioma guardado se aplica en un
  // efecto: leer localStorage durante el render daría un HTML distinto al
  // del servidor y Next descartaría la hidratación.
  const [idioma, setIdioma] = useState<Idioma>('es');

  useEffect(() => {
    try {
      const guardado = window.localStorage.getItem(CLAVE_ALMACEN);
      if (esIdioma(guardado)) {
        setIdioma(guardado);
      }
    } catch {
      // Modo privado o almacenamiento bloqueado: se queda en español.
    }
  }, []);

  useEffect(() => {
    // El `lang` del documento importa para los lectores de pantalla y para
    // que el navegador elija la tipografía correcta con el hangul.
    document.documentElement.lang = idioma;
  }, [idioma]);

  const cambiarIdioma = useCallback((nuevo: Idioma) => {
    setIdioma(nuevo);
    try {
      window.localStorage.setItem(CLAVE_ALMACEN, nuevo);
    } catch {
      // Si no se puede guardar, el cambio vale para esta sesión y ya.
    }
  }, []);

  const valor = useMemo<ContextoIdioma>(() => {
    const diccionario = DICCIONARIOS[idioma];

    return {
      idioma,
      locale: LOCALES[idioma],
      cambiarIdioma,
      t: (clave, valores) => {
        // Si a una traducción le falta la clave, se cae al español antes que
        // mostrar la ruta cruda en pantalla.
        const texto = buscar(diccionario, clave) ?? buscar(es, clave) ?? clave;
        return interpolar(texto, valores);
      },
    };
  }, [idioma, cambiarIdioma]);

  return <Contexto.Provider value={valor}>{children}</Contexto.Provider>;
}

export function useIdioma(): ContextoIdioma {
  const contexto = useContext(Contexto);

  if (contexto === null) {
    throw new Error('useIdioma debe usarse dentro de <ProveedorIdioma>.');
  }

  return contexto;
}

/** Atajo para los componentes que solo necesitan traducir. */
export function useTraduccion(): ContextoIdioma['t'] {
  return useIdioma().t;
}
