'use client';

import { useParams, useRouter } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';

import { Logo } from '@/components/ui/Logo';
import { useColaRespuestas } from '@/hooks/useColaRespuestas';
import {
  ErrorDeApi,
  finalizarIntento,
  iniciarIntento,
  obtenerAreas,
  obtenerCuestionarioPublico,
  obtenerEstadoIntento,
} from '@/lib/api';
import type { Area, CuestionarioPublico } from '@/lib/types';
import { cn } from '@/lib/utils';

type Fase = 'cargando' | 'identidad' | 'contestando' | 'error';

/** Clave de localStorage donde vive el intento en curso de este cuestionario. */
function claveIntento(token: string): string {
  return `intento_${token}`;
}

export default function FormularioPublico() {
  const parametros = useParams<{ token: string }>();
  const token = parametros.token;
  const router = useRouter();

  const [fase, setFase] = useState<Fase>('cargando');
  const [mensajeError, setMensajeError] = useState('');
  const [cuestionario, setCuestionario] = useState<CuestionarioPublico | null>(null);
  const [areas, setAreas] = useState<Area[]>([]);

  const [nombre, setNombre] = useState('');
  const [numeroEmpleado, setNumeroEmpleado] = useState('');
  const [area, setArea] = useState('');
  const [errorIdentidad, setErrorIdentidad] = useState('');
  const [iniciando, setIniciando] = useState(false);

  const [intentoId, setIntentoId] = useState<string | null>(null);
  const [respuestas, setRespuestas] = useState<Record<string, string>>({});
  const [confirmando, setConfirmando] = useState(false);
  const [finalizando, setFinalizando] = useState(false);

  const { encolar, limpiar, pendientes, enviando, sinConexion, errorFatal } =
    useColaRespuestas(token, intentoId);

  // Carga el cuestionario y, si había un intento en curso, lo restaura.
  useEffect(() => {
    let cancelado = false;

    async function preparar() {
      try {
        const [datos, catalogoAreas] = await Promise.all([
          obtenerCuestionarioPublico(token),
          obtenerAreas(),
        ]);

        if (cancelado) {
          return;
        }

        setCuestionario(datos);
        setAreas(catalogoAreas);

        const guardado = window.localStorage.getItem(claveIntento(token));

        if (guardado) {
          try {
            const estado = await obtenerEstadoIntento(guardado);

            if (cancelado) {
              return;
            }

            if (estado.finalizado) {
              // Ya lo había enviado: se limpia para no dejarlo atrapado en un
              // intento cerrado.
              window.localStorage.removeItem(claveIntento(token));
              setFase('identidad');
              return;
            }

            setIntentoId(estado.intento_id);
            setNombre(estado.nombre);
            setNumeroEmpleado(estado.numero_empleado);
            setArea(estado.area);
            setRespuestas(estado.respuestas);
            setFase('contestando');
            return;
          } catch {
            // El intento ya no existe en el servidor (por ejemplo, se borró
            // el cuestionario): se descarta y se empieza de cero.
            window.localStorage.removeItem(claveIntento(token));
          }
        }

        setFase('identidad');
      } catch (error) {
        if (!cancelado) {
          setMensajeError(
            error instanceof ErrorDeApi
              ? error.message
              : 'No se pudo cargar el cuestionario.',
          );
          setFase('error');
        }
      }
    }

    void preparar();

    return () => {
      cancelado = true;
    };
  }, [token]);

  async function comenzar() {
    setErrorIdentidad('');

    if (nombre.trim().length < 2) {
      setErrorIdentidad('Escribe tu nombre completo.');
      return;
    }
    if (numeroEmpleado.trim().length === 0) {
      setErrorIdentidad('Escribe tu número de empleado.');
      return;
    }
    if (area === '') {
      setErrorIdentidad('Selecciona tu área.');
      return;
    }

    setIniciando(true);

    try {
      const intento = await iniciarIntento(token, {
        nombre: nombre.trim(),
        numero_empleado: numeroEmpleado.trim(),
        area,
      });

      window.localStorage.setItem(claveIntento(token), intento.intento_id);
      setIntentoId(intento.intento_id);
      setFase('contestando');
    } catch (error) {
      setErrorIdentidad(
        error instanceof ErrorDeApi
          ? error.message
          : 'No se pudo iniciar el cuestionario.',
      );
      setIniciando(false);
    }
  }

  const responder = useCallback(
    (preguntaId: string, opcionId: string) => {
      setRespuestas((previas) => ({ ...previas, [preguntaId]: opcionId }));
      encolar(preguntaId, opcionId);
    },
    [encolar],
  );

  async function finalizar() {
    setFinalizando(true);

    try {
      const resultado = await finalizarIntento(intentoId ?? '');

      // El resultado viaja por sessionStorage: así la pantalla de gracias no
      // necesita volver a llamar a la API ni exponer el id en la URL.
      window.sessionStorage.setItem(`resultado_${token}`, JSON.stringify(resultado));
      window.localStorage.removeItem(claveIntento(token));
      limpiar();

      router.replace(`/r/${token}/gracias`);
    } catch (error) {
      setMensajeError(
        error instanceof ErrorDeApi
          ? error.message
          : 'No se pudo enviar el cuestionario.',
      );
      setFinalizando(false);
      setConfirmando(false);
    }
  }

  if (fase === 'cargando') {
    return (
      <main className="flex min-h-screen items-center justify-center p-6">
        <p className="text-lg text-claro-suave">Cargando cuestionario…</p>
      </main>
    );
  }

  if (fase === 'error') {
    return (
      <main className="flex min-h-screen items-center justify-center p-6">
        <div className="w-full max-w-md rounded-xl border-2 border-claro-borde bg-claro-superficie p-6 text-center">
          <h1 className="text-xl font-bold">Cuestionario no disponible</h1>
          <p className="mt-3 text-base text-claro-suave">{mensajeError}</p>
        </div>
      </main>
    );
  }

  if (fase === 'identidad') {
    return (
      <main className="mx-auto flex min-h-screen max-w-lg flex-col justify-center p-5">
        {/* Solo en esta pantalla: al pasar a las preguntas, la barra superior
            queda fija y el logo restaría espacio de lectura en el celular. */}
        <Logo alto={88} className="mx-auto mb-6" />

        <h1 className="text-2xl font-bold">{cuestionario?.nombre}</h1>
        {cuestionario?.descripcion && (
          <p className="mt-2 text-base text-claro-suave">{cuestionario.descripcion}</p>
        )}

        <p className="mt-6 text-base font-medium">Antes de empezar, identifícate:</p>

        <div className="mt-4 flex flex-col gap-4">
          <div>
            <label htmlFor="nombre" className="block text-base font-medium">
              Nombre completo
            </label>
            <input
              id="nombre"
              value={nombre}
              onChange={(evento) => setNombre(evento.target.value)}
              autoComplete="name"
              // 16px de tipografía como mínimo: por debajo, iOS hace zoom al
              // enfocar el campo y descuadra el formulario.
              className="mt-1 h-tactil w-full rounded-lg border-2 border-claro-borde bg-white px-4 text-base"
            />
          </div>

          <div>
            <label htmlFor="numero" className="block text-base font-medium">
              Número de empleado
            </label>
            <input
              id="numero"
              value={numeroEmpleado}
              onChange={(evento) => setNumeroEmpleado(evento.target.value)}
              inputMode="numeric"
              className="mt-1 h-tactil w-full rounded-lg border-2 border-claro-borde bg-white px-4 text-base"
            />
          </div>

          <div>
            <label htmlFor="area" className="block text-base font-medium">
              Área
            </label>
            <select
              id="area"
              value={area}
              onChange={(evento) => setArea(evento.target.value)}
              className="mt-1 h-tactil w-full rounded-lg border-2 border-claro-borde bg-white px-4 text-base"
            >
              <option value="">Selecciona tu área</option>
              {areas.map((opcion) => (
                <option key={opcion.value} value={opcion.value}>
                  {opcion.label}
                </option>
              ))}
            </select>
          </div>

          {errorIdentidad && (
            <p
              role="alert"
              className="rounded-lg border-2 border-claro-error bg-red-50 px-4 py-3 text-base font-medium text-claro-error"
            >
              {errorIdentidad}
            </p>
          )}

          <button
            type="button"
            onClick={() => void comenzar()}
            disabled={iniciando}
            className="h-tactil w-full rounded-lg bg-claro-primario text-lg font-semibold text-white disabled:opacity-60"
          >
            {iniciando ? 'Iniciando…' : 'Comenzar'}
          </button>
        </div>
      </main>
    );
  }

  const preguntas = cuestionario?.preguntas ?? [];
  const contestadas = preguntas.filter((pregunta) => respuestas[pregunta.id]).length;
  const todasContestadas = contestadas === preguntas.length && preguntas.length > 0;
  const bloqueadoPorCola = pendientes > 0;

  return (
    <main className="mx-auto max-w-2xl p-4 pb-32">
      <header className="sticky top-0 -mx-4 border-b-2 border-claro-borde bg-claro-fondo px-4 py-3">
        <h1 className="text-lg font-bold">{cuestionario?.nombre}</h1>

        <div className="mt-2 flex items-center gap-3">
          <div
            className="h-2 flex-1 overflow-hidden rounded-full bg-claro-superficie"
            role="progressbar"
            aria-valuenow={contestadas}
            aria-valuemin={0}
            aria-valuemax={preguntas.length}
          >
            <div
              className="h-full bg-claro-primario transition-all"
              style={{
                width: `${preguntas.length === 0 ? 0 : (contestadas / preguntas.length) * 100}%`,
              }}
            />
          </div>
          <span className="shrink-0 text-sm font-medium text-claro-suave">
            Pregunta {Math.min(contestadas + (todasContestadas ? 0 : 1), preguntas.length)} de{' '}
            {preguntas.length}
          </span>
        </div>

        {sinConexion && (
          <p className="mt-2 rounded-md bg-amber-100 px-3 py-2 text-sm font-medium text-amber-900">
            Sin conexión — tus respuestas se guardarán automáticamente cuando
            vuelva la señal.
          </p>
        )}

        {errorFatal && (
          <p
            role="alert"
            className="mt-2 rounded-md bg-red-50 px-3 py-2 text-sm font-medium text-claro-error"
          >
            {errorFatal}
          </p>
        )}
      </header>

      <ol className="mt-5 flex flex-col gap-5">
        {preguntas.map((pregunta, indice) => (
          <li
            key={pregunta.id}
            className="rounded-xl border-2 border-claro-borde bg-claro-superficie p-4"
          >
            <fieldset>
              <legend className="mb-3 text-lg font-semibold leading-snug">
                {indice + 1}. {pregunta.texto}
              </legend>

              <div className="flex flex-col gap-2.5">
                {pregunta.opciones.map((opcion) => {
                  const seleccionada = respuestas[pregunta.id] === opcion.id;

                  return (
                    <label
                      key={opcion.id}
                      className={cn(
                        // min-h de 48px: se contesta con guantes puestos.
                        'flex min-h-tactil cursor-pointer items-center gap-3 rounded-lg border-2 bg-white px-4 py-3 text-base',
                        seleccionada
                          ? 'border-claro-primario bg-blue-50 font-medium'
                          : 'border-claro-borde',
                      )}
                    >
                      <input
                        type="radio"
                        name={`pregunta-${pregunta.id}`}
                        checked={seleccionada}
                        onChange={() => responder(pregunta.id, opcion.id)}
                        className="h-5 w-5 shrink-0 accent-claro-primario"
                      />
                      <span>{opcion.texto}</span>
                    </label>
                  );
                })}
              </div>
            </fieldset>

            {respuestas[pregunta.id] && (
              <p className="mt-2 text-sm text-claro-exito">
                {enviando || pendientes > 0 ? 'Guardando…' : '✓ Guardado'}
              </p>
            )}
          </li>
        ))}
      </ol>

      <div className="fixed inset-x-0 bottom-0 border-t-2 border-claro-borde bg-claro-fondo p-4">
        <div className="mx-auto max-w-2xl">
          <button
            type="button"
            onClick={() => setConfirmando(true)}
            disabled={!todasContestadas || bloqueadoPorCola}
            className="h-tactil w-full rounded-lg bg-claro-exito text-lg font-semibold text-white disabled:bg-gray-300 disabled:text-gray-600"
          >
            {bloqueadoPorCola ? 'Guardando respuestas…' : 'Finalizar'}
          </button>

          {!todasContestadas && (
            <p className="mt-2 text-center text-sm text-claro-suave">
              Te faltan {preguntas.length - contestadas} pregunta(s) por contestar.
            </p>
          )}
        </div>
      </div>

      {confirmando && (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 p-4 sm:items-center">
          <div className="w-full max-w-md rounded-xl bg-white p-5">
            <h2 className="text-lg font-bold">¿Enviar tus respuestas?</h2>
            <p className="mt-2 text-base text-claro-suave">
              Una vez enviado no podrás cambiar tus respuestas.
            </p>

            <div className="mt-5 flex flex-col gap-2">
              <button
                type="button"
                onClick={() => void finalizar()}
                disabled={finalizando}
                className="h-tactil w-full rounded-lg bg-claro-exito text-lg font-semibold text-white disabled:opacity-60"
              >
                {finalizando ? 'Enviando…' : 'Sí, enviar'}
              </button>
              <button
                type="button"
                onClick={() => setConfirmando(false)}
                disabled={finalizando}
                className="h-tactil w-full rounded-lg border-2 border-claro-borde bg-white text-lg font-medium"
              >
                Cancelar
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
