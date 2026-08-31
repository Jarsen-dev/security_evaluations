'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { MatrizRondines } from '@/components/rondines/MatrizRondines';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { useToast } from '@/components/ui/Toast';
import {
  ErrorDeApi,
  descargarExcelRondines,
  enviarReporteRondines,
  obtenerTablero,
} from '@/lib/api';
import { bilingue, unaLinea, useIdioma } from '@/lib/i18n';
import { turnoEnCurso } from '@/lib/turno';
import type { Tablero, TurnoRondin } from '@/lib/types';

/** Cada cuánto se recarga el tablero mientras alguien lo está mirando. */
const REFRESCO_MS = 60_000;

const CLASES_CAMPO =
  'h-10 rounded-md border border-borde bg-fondo px-3 text-sm text-texto focus:border-primario';

export function PanelTablero() {
  const { t, locale } = useIdioma();
  const { mostrarToast } = useToast();

  // Arranca en null y se resuelve en un efecto: el contenedor del frontend
  // corre en UTC y la planta en UTC-6, así que calcular la fecha durante el
  // render deja el HTML del servidor distinto al del navegador. Mismo patrón
  // que `IndicadorTurno` y `ProveedorIdioma`.
  const [fecha, setFecha] = useState<string | null>(null);
  const [turno, setTurno] = useState<TurnoRondin | null>(null);

  useEffect(() => {
    // El turno vivo, no siempre el de día: a las 22:00 el turno en curso es
    // la noche, y pasada la medianoche esa noche empezó AYER, que es la fecha
    // que entiende la API.
    const actual = turnoEnCurso();
    setFecha(actual.fecha);
    setTurno(actual.turno);
  }, []);

  const [tablero, setTablero] = useState<Tablero | null>(null);
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState('');
  const [actualizado, setActualizado] = useState<Date | null>(null);

  const [correo, setCorreo] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [descargando, setDescargando] = useState(false);

  // Cada carga se sella con un número; solo la más reciente puede escribir en
  // el estado. Sin esto, cambiar rápido de fecha o turno dejaba ganar a la
  // respuesta más lenta, y el refresco automático podía pisar una carga manual.
  const peticion = useRef(0);

  const cargar = useCallback(
    async (silencioso = false) => {
      if (fecha === null || turno === null) {
        return;
      }

      const mia = ++peticion.current;

      if (!silencioso) {
        setCargando(true);
      }

      try {
        const resultado = await obtenerTablero(fecha, turno);
        if (mia !== peticion.current) {
          return;
        }
        setTablero(resultado);
        setActualizado(new Date());
        setErrorCarga('');
      } catch (error: unknown) {
        if (mia !== peticion.current) {
          return;
        }
        // Un refresco silencioso que falla no borra la pantalla: el tablero
        // vive encendido en la caseta y un hipo de red a las 3 a. m. no debe
        // tapar datos válidos con un banner rojo.
        if (!silencioso) {
          setErrorCarga(
            error instanceof ErrorDeApi ? error.message : t('rondines.falloCarga'),
          );
        }
      } finally {
        if (mia === peticion.current) {
          setCargando(false);
        }
      }
    },
    [fecha, turno, t],
  );

  useEffect(() => {
    void cargar();
  }, [cargar]);

  // El tablero se queda encendido en una pantalla de la caseta, así que se
  // refresca solo. Y se PAUSA cuando la pestaña no está a la vista: sin eso,
  // un tablero olvidado le pega a la API toda la noche sin que nadie lo mire.
  const refCargar = useRef(cargar);
  refCargar.current = cargar;

  useEffect(() => {
    let temporizador: ReturnType<typeof setInterval> | null = null;

    const arrancar = () => {
      if (temporizador === null) {
        temporizador = setInterval(() => void refCargar.current(true), REFRESCO_MS);
      }
    };

    const detener = () => {
      if (temporizador !== null) {
        clearInterval(temporizador);
        temporizador = null;
      }
    };

    const alCambiarVisibilidad = () => {
      if (document.visibilityState === 'visible') {
        // Al volver, se recarga de inmediato: lo que hay en pantalla puede
        // llevar horas sin actualizarse.
        void refCargar.current(true);
        arrancar();
      } else {
        detener();
      }
    };

    if (document.visibilityState === 'visible') {
      arrancar();
    }
    document.addEventListener('visibilitychange', alCambiarVisibilidad);

    return () => {
      detener();
      document.removeEventListener('visibilitychange', alCambiarVisibilidad);
    };
  }, []);

  async function descargar() {
    if (fecha === null || turno === null) {
      return;
    }

    setDescargando(true);
    try {
      await descargarExcelRondines(fecha, turno);
    } catch (error: unknown) {
      mostrarToast(
        error instanceof ErrorDeApi ? error.message : t('comun.errorGenerico'),
        'error',
      );
    } finally {
      setDescargando(false);
    }
  }

  async function enviar() {
    if (fecha === null || turno === null) {
      return;
    }

    setEnviando(true);
    try {
      await enviarReporteRondines(fecha, turno, correo.trim());
      mostrarToast(t('rondines.correoEnviado'), 'exito');
      setCorreo('');
    } catch (error: unknown) {
      mostrarToast(
        error instanceof ErrorDeApi ? error.message : t('rondines.falloCorreo'),
        'error',
      );
    } finally {
      setEnviando(false);
    }
  }

  const momento = (iso: string) =>
    new Date(iso).toLocaleString(locale, {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1.5">
            <label
              htmlFor="rondines-fecha"
              className="text-xs font-medium text-texto-suave"
            >
              {bilingue(t('rondines.dia'))}
            </label>
            <input
              id="rondines-fecha"
              type="date"
              className={CLASES_CAMPO}
              value={fecha ?? ''}
              disabled={fecha === null}
              onChange={(evento) => setFecha(evento.target.value)}
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label
              htmlFor="rondines-turno"
              className="text-xs font-medium text-texto-suave"
            >
              {bilingue(t('rondines.turno'))}
            </label>
            <select
              id="rondines-turno"
              className={CLASES_CAMPO}
              value={turno ?? 'dia'}
              disabled={turno === null}
              onChange={(evento) => setTurno(evento.target.value as TurnoRondin)}
            >
              <option value="dia">{unaLinea(t('rondines.turnoDia'))}</option>
              <option value="noche">{unaLinea(t('rondines.turnoNoche'))}</option>
            </select>
          </div>

          {tablero !== null && (
            <p className="pb-2 text-sm text-texto-suave">
              {bilingue(t('rondines.rango', {
                inicio: momento(tablero.inicio),
                fin: momento(tablero.fin),
              }))}
            </p>
          )}

          <div className="ml-auto flex items-center gap-2 pb-0.5">
            {actualizado !== null && (
              <span className="text-xs text-texto-tenue">
                {bilingue(t('rondines.actualizado', {
                  hora: actualizado.toLocaleTimeString(locale, {
                    hour: '2-digit',
                    minute: '2-digit',
                  }),
                }))}
              </span>
            )}
            <Button
              variante="secundario"
              tamano="sm"
              cargando={descargando}
              onClick={() => void descargar()}
            >
              {bilingue(t('rondines.descargar'))}
            </Button>
          </div>
        </div>

        <p className="mt-3 text-sm text-texto-tenue">{bilingue(t('rondines.ayudaTurno'))}</p>
      </Card>

      {errorCarga !== '' && (
        <div
          role="alert"
          className="flex flex-wrap items-center gap-3 rounded-tarjeta border border-error bg-error-suave px-4 py-3 text-sm text-texto"
        >
          <span>{errorCarga}</span>
          <Button variante="secundario" tamano="sm" onClick={() => void cargar()}>
            {bilingue(t('comun.reintentar'))}
          </Button>
        </div>
      )}

      {tablero !== null && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Indicador
            etiqueta={
              tablero.rondin_actual === null
                ? t('rondines.cumplimiento')
                : t('rondines.cumplimientoParcial')
            }
            valor={`${tablero.cumplimiento.toFixed(1)}%`}
          />
          <Indicador
            etiqueta={t('rondines.visitas')}
            valor={`${tablero.visitados} / ${tablero.total}`}
          />
          <Indicador
            etiqueta={t('rondines.rondinEnCurso')}
            valor={
              tablero.rondin_actual === null
                ? t('rondines.fueraDeTurno')
                : t('rondines.rondin', { numero: tablero.rondin_actual + 1 })
            }
          />
          <Indicador
            etiqueta={t('rondines.avance')}
            valor={
              tablero.avance_actual === null
                ? '—'
                : `${tablero.avance_actual} / ${tablero.puntos_activos}`
            }
          />
        </div>
      )}

      {cargando ? (
        <p className="text-sm text-texto-suave">{bilingue(t('comun.cargando'))}</p>
      ) : tablero === null ? null : tablero.puntos_activos === 0 ? (
        <div className="rounded-tarjeta border border-dashed border-borde px-6 py-12 text-center">
          <p className="text-sm font-medium text-texto">{bilingue(t('rondines.sinPuntos'))}</p>
          <p className="mt-2 text-sm text-texto-suave">{bilingue(t('rondines.sinPuntosAyuda'))}</p>
        </div>
      ) : (
        <MatrizRondines tablero={tablero} />
      )}

      <Card>
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex min-w-[16rem] flex-1 flex-col gap-1.5">
            <label
              htmlFor="rondines-correo"
              className="text-xs font-medium text-texto-suave"
            >
              {bilingue(t('rondines.correoDestino'))}
            </label>
            <input
              id="rondines-correo"
              type="email"
              className={CLASES_CAMPO}
              value={correo}
              onChange={(evento) => setCorreo(evento.target.value)}
            />
          </div>

          <Button
            variante="secundario"
            cargando={enviando}
            disabled={correo.trim() === ''}
            onClick={() => void enviar()}
          >
            {bilingue(t('rondines.enviarCorreo'))}
          </Button>
        </div>
      </Card>
    </div>
  );
}

/** Tarjeta de indicador. Molde: `estadisticas/TarjetaKPI.tsx`. */
function Indicador({ etiqueta, valor }: { etiqueta: string; valor: string }) {
  return (
    <Card>
      <p className="text-xs font-medium uppercase tracking-wide text-texto-tenue">
        {bilingue(etiqueta)}
      </p>
      <p className="mt-2 text-2xl font-semibold text-texto">{bilingue(valor)}</p>
    </Card>
  );
}
