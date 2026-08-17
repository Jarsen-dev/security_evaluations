'use client';

import { useParams } from 'next/navigation';
import { useEffect, useState } from 'react';

import type { ResultadoIntento } from '@/lib/types';

/**
 * Pantalla de confirmación posterior al envío.
 *
 * El resultado llega por `sessionStorage`, escrito por el formulario justo
 * antes de redirigir: así no hace falta exponer el id del intento en la URL
 * ni volver a consultar la API.
 */
export default function PaginaGracias() {
  const parametros = useParams<{ token: string }>();
  const token = parametros.token;

  const [resultado, setResultado] = useState<ResultadoIntento | null>(null);
  const [cargado, setCargado] = useState(false);

  useEffect(() => {
    try {
      const crudo = window.sessionStorage.getItem(`resultado_${token}`);
      if (crudo) {
        setResultado(JSON.parse(crudo) as ResultadoIntento);
      }
    } catch {
      // Sin resultado se muestra igual el agradecimiento genérico.
    } finally {
      setCargado(true);
    }
  }, [token]);

  if (!cargado) {
    return (
      <main className="flex min-h-screen items-center justify-center p-6">
        <p className="text-lg text-claro-suave">Cargando…</p>
      </main>
    );
  }

  const puntaje = resultado ? Number(resultado.puntaje) : null;

  return (
    <main className="flex min-h-screen items-center justify-center p-5">
      <div className="w-full max-w-md rounded-xl border-2 border-claro-borde bg-claro-superficie p-6 text-center">
        <p className="text-5xl" aria-hidden="true">
          ✓
        </p>

        <h1 className="mt-3 text-2xl font-bold">¡Listo{resultado ? `, ${resultado.nombre.split(' ')[0]}` : ''}!</h1>
        <p className="mt-2 text-base text-claro-suave">
          Tus respuestas se enviaron correctamente.
        </p>

        {resultado && puntaje !== null && (
          <>
            <div
              className={`mt-6 rounded-xl border-2 p-5 ${
                resultado.aprobado
                  ? 'border-claro-exito bg-green-50'
                  : 'border-claro-error bg-red-50'
              }`}
            >
              <p className="text-sm font-medium uppercase tracking-wide text-claro-suave">
                Tu calificación
              </p>
              <p
                className={`mt-1 text-5xl font-bold ${
                  resultado.aprobado ? 'text-claro-exito' : 'text-claro-error'
                }`}
              >
                {puntaje.toFixed(0)}
                <span className="text-2xl">%</span>
              </p>
              <p className="mt-2 text-base font-medium">
                {resultado.correctas} de {resultado.total_preguntas} correctas
              </p>
              <p className="mt-3 text-base font-semibold">
                {resultado.aprobado
                  ? 'Aprobado'
                  : `No aprobado (mínimo ${resultado.umbral_aprobacion}%)`}
              </p>
            </div>

            <p className="mt-5 text-sm text-claro-suave">
              Ya puedes cerrar esta página.
            </p>
          </>
        )}

        {!resultado && (
          <p className="mt-5 text-sm text-claro-suave">Ya puedes cerrar esta página.</p>
        )}
      </div>
    </main>
  );
}
