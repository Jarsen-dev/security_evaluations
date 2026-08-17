'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { ErrorDeApi, guardarRespuesta } from '@/lib/api';

/**
 * Cola de autoguardado tolerante a cortes de red.
 *
 * La cobertura WiFi de la nave es irregular: si un PATCH falla, la respuesta
 * no puede perderse. Se encola en `localStorage` y se reintenta con espera
 * exponencial hasta que entre. La cola sobrevive a una recarga de la página.
 *
 * Es un mapa `pregunta_id -> opcion_id`, no una lista: si el operador cambia
 * de opinión tres veces sin conexión, solo importa su última elección.
 */

const BASE_ESPERA_MS = 1000;
const MAX_ESPERA_MS = 30000;

type Cola = Record<string, string>;

function claveCola(token: string): string {
  return `cola_${token}`;
}

function leerCola(token: string): Cola {
  if (typeof window === 'undefined') {
    return {};
  }

  try {
    const crudo = window.localStorage.getItem(claveCola(token));
    return crudo ? (JSON.parse(crudo) as Cola) : {};
  } catch {
    // localStorage lleno, deshabilitado o con JSON corrupto: se arranca con
    // una cola vacía en lugar de romper el formulario.
    return {};
  }
}

function escribirCola(token: string, cola: Cola): void {
  try {
    if (Object.keys(cola).length === 0) {
      window.localStorage.removeItem(claveCola(token));
    } else {
      window.localStorage.setItem(claveCola(token), JSON.stringify(cola));
    }
  } catch {
    // Si no se puede persistir, la cola sigue viva en memoria.
  }
}

export function useColaRespuestas(token: string, intentoId: string | null) {
  const [cola, setCola] = useState<Cola>({});
  const [enviando, setEnviando] = useState(false);
  const [huboFallo, setHuboFallo] = useState(false);
  const [errorFatal, setErrorFatal] = useState('');

  const intentosFallidos = useRef(0);
  const temporizador = useRef<ReturnType<typeof setTimeout> | null>(null);
  const procesando = useRef(false);

  // Recupera lo que quedó pendiente de una sesión anterior.
  useEffect(() => {
    setCola(leerCola(token));
  }, [token]);

  const encolar = useCallback(
    (preguntaId: string, opcionId: string) => {
      setCola((previa) => {
        const nueva = { ...previa, [preguntaId]: opcionId };
        escribirCola(token, nueva);
        return nueva;
      });
    },
    [token],
  );

  const procesar = useCallback(async () => {
    if (procesando.current || intentoId === null) {
      return;
    }

    const entradas = Object.entries(cola);
    if (entradas.length === 0) {
      return;
    }

    const primera = entradas[0];
    if (!primera) {
      return;
    }

    const [preguntaId, opcionId] = primera;

    procesando.current = true;
    setEnviando(true);

    try {
      await guardarRespuesta(intentoId, preguntaId, opcionId);

      intentosFallidos.current = 0;
      setHuboFallo(false);
      setCola((previa) => {
        const nueva = { ...previa };
        // Solo se descarta si sigue siendo la misma opción: si el operador
        // cambió de respuesta mientras se enviaba, hay que reenviar.
        if (nueva[preguntaId] === opcionId) {
          delete nueva[preguntaId];
        }
        escribirCola(token, nueva);
        return nueva;
      });
    } catch (error) {
      // 409 (ya finalizado) y 404 (opción inválida) no se arreglan
      // reintentando: se descarta la entrada y se avisa.
      if (error instanceof ErrorDeApi && (error.status === 409 || error.status === 404)) {
        setErrorFatal(error.message);
        setCola((previa) => {
          const nueva = { ...previa };
          delete nueva[preguntaId];
          escribirCola(token, nueva);
          return nueva;
        });
      } else {
        intentosFallidos.current += 1;
        setHuboFallo(true);
      }
    } finally {
      procesando.current = false;
      setEnviando(false);
    }
  }, [cola, intentoId, token]);

  // Dispara el procesamiento con espera exponencial tras cada fallo.
  useEffect(() => {
    if (intentoId === null || Object.keys(cola).length === 0) {
      return;
    }

    const espera =
      intentosFallidos.current === 0
        ? 0
        : Math.min(BASE_ESPERA_MS * 2 ** (intentosFallidos.current - 1), MAX_ESPERA_MS);

    temporizador.current = setTimeout(() => {
      void procesar();
    }, espera);

    return () => {
      if (temporizador.current !== null) {
        clearTimeout(temporizador.current);
      }
    };
  }, [cola, intentoId, procesar]);

  // Reintenta de inmediato cuando el navegador recupera la conexión, sin
  // esperar a que venza el backoff.
  useEffect(() => {
    function alReconectar() {
      intentosFallidos.current = 0;
      void procesar();
    }

    window.addEventListener('online', alReconectar);
    return () => window.removeEventListener('online', alReconectar);
  }, [procesar]);

  const limpiar = useCallback(() => {
    setCola({});
    escribirCola(token, {});
  }, [token]);

  return {
    encolar,
    limpiar,
    pendientes: Object.keys(cola).length,
    enviando,
    sinConexion: huboFallo,
    errorFatal,
  };
}
