'use client';

import { useParams } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';

import { ErrorDeApi, escanearPunto } from '@/lib/api';
import type { EscaneoRegistrado } from '@/lib/types';

type Fase = 'registrando' | 'listo' | 'error';

/**
 * Registra la visita a un punto de control.
 *
 * El guardia escanea el QR, esta página se abre y envía el escaneo sola. No
 * hay nada que tocar: ya se está moviendo al siguiente punto, así que lo único
 * que importa es que la confirmación se lea de un vistazo y sin acercarse.
 *
 * En español, como `/r/[token]`: la usa el personal de piso.
 */
export default function PaginaEscaneo() {
  const parametros = useParams<{ token: string }>();
  const token = parametros.token;

  const [fase, setFase] = useState<Fase>('registrando');
  const [punto, setPunto] = useState<EscaneoRegistrado | null>(null);
  const [error, setError] = useState('');
  const yaEnviado = useRef(false);

  useEffect(() => {
    // React 18 monta dos veces en desarrollo; sin este candado el punto
    // quedaría registrado dos veces en cada escaneo.
    if (yaEnviado.current || !token) {
      return;
    }
    yaEnviado.current = true;

    escanearPunto(token)
      .then((registrado) => {
        setPunto(registrado);
        setFase('listo');
      })
      .catch((fallo: unknown) => {
        setError(
          fallo instanceof ErrorDeApi
            ? fallo.message
            : 'No se pudo registrar el punto. Revisa tu conexión e inténtalo de nuevo.',
        );
        setFase('error');
      });
  }, [token]);

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col items-center justify-center px-6 py-10 text-center">
      {fase === 'registrando' && (
        <p className="text-lg text-claro-suave">Registrando…</p>
      )}

      {fase === 'listo' && punto !== null && (
        <>
          {/* La marca de visto es grande a propósito: se distingue de la
              pantalla de error desde lejos, sin leer nada. */}
          <div
            aria-hidden
            className="flex h-24 w-24 items-center justify-center rounded-full bg-claro-exito text-5xl text-white"
          >
            ✓
          </div>

          <h1 className="mt-6 text-3xl font-bold text-claro-texto">
            Punto {punto.numero}
          </h1>
          <p className="mt-2 text-xl text-claro-texto">{punto.nombre}</p>

          {punto.ubicacion && (
            <p className="mt-1 text-base text-claro-suave">{punto.ubicacion}</p>
          )}

          <p className="mt-8 text-2xl font-semibold text-claro-primario">
            {new Date(punto.escaneado_at).toLocaleTimeString('es-MX', {
              hour: '2-digit',
              minute: '2-digit',
            })}
          </p>
          <p className="mt-1 text-sm text-claro-suave">Registrado</p>
        </>
      )}

      {fase === 'error' && (
        <>
          <div
            aria-hidden
            className="flex h-24 w-24 items-center justify-center rounded-full bg-claro-error text-5xl text-white"
          >
            !
          </div>

          <p
            role="alert"
            className="mt-6 text-lg font-medium text-claro-texto"
          >
            {error}
          </p>

          {/* Recargar es el único remedio útil aquí, y con guantes conviene
              que el objetivo sea grande. */}
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="mt-8 h-tactil w-full rounded-lg bg-claro-primario px-6 text-lg font-semibold text-white"
          >
            Intentar de nuevo
          </button>
        </>
      )}
    </main>
  );
}
