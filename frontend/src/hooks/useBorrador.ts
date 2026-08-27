'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { borrarBorrador, guardarBorrador, leerBorrador } from '@/lib/borradores';
import { fechaDeHoy } from '@/lib/utils';

/**
 * Autoguardado del formulario en curso.
 *
 * Vive junto a `useColaRespuestas`, que es el otro sitio donde el proyecto se
 * niega a perder trabajo del operador por algo que no fue su culpa. Aquí lo
 * que se pierde no es la red, es un clic en la pestaña equivocada.
 *
 * Quien lo usa conserva sus `useState` como siempre; solo pasa un retrato
 * serializable de ellos y una forma de volver a aplicarlos.
 */

/** Un teclazo no debe pegarle a IndexedDB: las ráfagas se colapsan. */
const ESPERA_ESCRITURA_MS = 500;

interface Resultado {
  /** `false` hasta que se intentó leer el borrador. Nada se escribe antes. */
  cargado: boolean;
  /** El borrador restaurado se escribió otro día: la hoja se archiva con hoy. */
  esDeOtroDia: boolean;
  /** Día en que se escribió, `YYYY-MM-DD`; `null` si no había borrador. */
  fecha: string | null;
  /** Tira el borrador guardado. No toca el estado del formulario. */
  descartar: () => void;
}

export function useBorrador<T>(
  /** `${username}:${control}`. Con `null` el hook queda inerte (sin sesión). */
  id: string | null,
  /** Retrato de este render. Se guarda tal cual, `File` incluidos. */
  datos: T,
  /**
   * `false` cuando la hoja está en blanco. Un formulario intacto no genera
   * borrador, y al reiniciarlo el registro se borra en vez de reescribirse
   * vacío: así "reiniciar" de verdad deja limpio.
   */
  hayContenido: boolean,
  /** Aplica un borrador leído a los `useState` del formulario. */
  restaurar: (datos: T) => void,
): Resultado {
  const [cargado, setCargado] = useState(false);
  const [fecha, setFecha] = useState<string | null>(null);

  // `restaurar` y `datos` cambian de identidad en cada render. Van por ref
  // para que no arrastren a los efectos: es el mismo motivo por el que `t`
  // se mantiene estable en `lib/i18n/index.tsx`.
  const restaurarRef = useRef(restaurar);
  restaurarRef.current = restaurar;

  const datosRef = useRef(datos);
  datosRef.current = datos;

  useEffect(() => {
    if (id === null) {
      return;
    }

    let cancelado = false;
    setCargado(false);
    setFecha(null);

    void leerBorrador<T>(id).then((guardado) => {
      if (cancelado) {
        return;
      }

      if (guardado !== null) {
        restaurarRef.current(guardado.datos);
        setFecha(guardado.fecha);
      }

      // Hasta aquí no se escribe nada: si se marcara `cargado` antes de
      // restaurar, el efecto de abajo guardaría el formulario vacío encima
      // del borrador y lo borraría justo antes de recuperarlo.
      setCargado(true);
    });

    return () => {
      cancelado = true;
    };
  }, [id]);

  useEffect(() => {
    if (id === null || !cargado) {
      return;
    }

    const temporizador = setTimeout(() => {
      if (hayContenido) {
        void guardarBorrador(id, fechaDeHoy(), datosRef.current);
      } else {
        void borrarBorrador(id);
      }
    }, ESPERA_ESCRITURA_MS);

    return () => clearTimeout(temporizador);
    // `datos` va en las dependencias aunque se lea por ref: es lo que marca
    // que hubo un cambio y hay que reprogramar la escritura.
  }, [id, cargado, hayContenido, datos]);

  const descartar = useCallback(() => {
    if (id !== null) {
      void borrarBorrador(id);
    }
    // Se olvida la fecha para que el aviso de "otro día" no quede colgado
    // sobre una hoja que ya se vació.
    setFecha(null);
  }, [id]);

  return {
    cargado,
    esDeOtroDia: fecha !== null && fecha !== fechaDeHoy(),
    fecha,
    descartar,
  };
}
