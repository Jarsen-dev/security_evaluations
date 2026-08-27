'use client';

import { useParams } from 'next/navigation';
import { useRef, useState } from 'react';

import { ErrorDeApi, subirFotoSesion } from '@/lib/api';
import { REDUCCION_DOCUMENTO, reducirImagen } from '@/lib/imagen';

/**
 * Captura de la foto de una remisión desde el celular.
 *
 * Es pública: el celular no inició sesión en el panel. Lo que la protege es la
 * sesión que abre la PC — identificador no adivinable, diez minutos de vida y
 * un solo uso.
 *
 * En español y sin diccionario, como `/r/[token]` y `/p/[token]`: la usa el
 * personal de piso.
 *
 * La cámara se abre con `<input type="file" capture>` y **nunca** con
 * `getUserMedia`: por HTTP en la IP de la LAN esa API no existe, y por el
 * dominio Nginx la bloquea con `Permissions-Policy: camera=()`.
 */
type Fase = 'listo' | 'enviando' | 'enviada' | 'error';

export default function PaginaCaptura() {
  const { sesion } = useParams<{ sesion: string }>();
  const entrada = useRef<HTMLInputElement>(null);
  const [fase, setFase] = useState<Fase>('listo');
  const [mensaje, setMensaje] = useState('');

  async function enviar(archivo: File) {
    setFase('enviando');

    try {
      // Se reduce en el navegador: una foto de celular son varios MB y en la
      // WiFi de planta esa subida se puede eternizar.
      const reducida = await reducirImagen(archivo, REDUCCION_DOCUMENTO);
      await subirFotoSesion(sesion, reducida);
      setFase('enviada');
    } catch (error: unknown) {
      setMensaje(
        error instanceof ErrorDeApi
          ? error.message
          : 'No se pudo enviar la foto. Revisa tu conexión e inténtalo otra vez.',
      );
      setFase('error');
    }
  }

  if (fase === 'enviada') {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center gap-6 px-6 text-center">
        <div className="flex h-24 w-24 items-center justify-center rounded-full bg-claro-exito">
          <svg
            viewBox="0 0 24 24"
            className="h-14 w-14 text-white"
            fill="none"
            stroke="currentColor"
            strokeWidth={3}
            aria-hidden
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
          </svg>
        </div>
        <h1 className="text-3xl font-bold">Foto enviada</h1>
        <p className="max-w-sm text-xl text-claro-suave">
          Regresa a la computadora: ahí aparecen los datos para revisarlos.
        </p>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-8 px-6 text-center">
      <h1 className="text-3xl font-bold">Foto de la remisión</h1>
      <p className="max-w-sm text-xl text-claro-suave">
        Toma la foto de la hoja completa, con buena luz y sin sombras encima.
      </p>

      {fase === 'error' && (
        <p
          role="alert"
          className="max-w-sm rounded-lg border-2 border-claro-error px-4 py-3 text-lg text-claro-error"
        >
          {mensaje}
        </p>
      )}

      <button
        type="button"
        disabled={fase === 'enviando'}
        onClick={() => entrada.current?.click()}
        className="min-h-tactil w-full max-w-sm rounded-lg bg-claro-primario px-6 py-5 text-2xl font-semibold text-white disabled:opacity-60"
      >
        {fase === 'enviando' ? 'Enviando…' : 'Tomar foto'}
      </button>

      <input
        ref={entrada}
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        onChange={(evento) => {
          const archivo = evento.target.files?.[0];
          // Se limpia el valor para poder reintentar con la misma foto.
          evento.target.value = '';
          if (archivo) void enviar(archivo);
        }}
      />
    </main>
  );
}
