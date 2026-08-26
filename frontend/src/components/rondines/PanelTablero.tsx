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
import { useIdioma } from '@/lib/i18n';
import { fechaDeHoy } from '@/lib/utils';
import type { Tablero, TurnoRondin } from '@/lib/types';

/** Cada cuánto se recarga el tablero mientras alguien lo está mirando. */
const REFRESCO_MS = 60_000;

const CLASES_CAMPO =
  'h-10 rounded-md border border-borde bg-fondo px-3 text-sm text-texto focus:border-primario';

export function PanelTablero() {
  const { t, locale } = useIdioma();
  const { mostrarToast } = useToast();

  const [fecha, setFecha] = useState(fechaDeHoy);
  const [turno, setTurno] = useState<TurnoRondin>('dia');

  const [tablero, setTablero] = useState<Tablero | null>(null);
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState('');
  const [actualizado, setActualizado] = useState<Date | null>(null);

  const [correo, setCorreo] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [descargando, setDescargando] = useState(false);

  const cargar = useCallback(
    async (silencioso = false) => {
      if (!silencioso) {
        setCargando(true);
      }

      try {
        setTablero(await obtenerTablero(fecha, turno));
        setActualizado(new Date());
        setErrorCarga('');
      } catch (error: unknown) {
        setErrorCarga(
          error instanceof ErrorDeApi ? error.message : t('rondines.falloCarga'),
        );
      } finally {
        setCargando(false);
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
              {t('rondines.dia')}
            </label>
            <input
              id="rondines-fecha"
              type="date"
              className={CLASES_CAMPO}
              value={fecha}
              onChange={(evento) => setFecha(evento.target.value)}
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label
              htmlFor="rondines-turno"
              className="text-xs font-medium text-texto-suave"
            >
              {t('rondines.turno')}
            </label>
            <select
              id="rondines-turno"
              className={CLASES_CAMPO}
              value={turno}
              onChange={(evento) => setTurno(evento.target.value as TurnoRondin)}
            >
              <option value="dia">{t('rondines.turnoDia')}</option>
              <option value="noche">{t('rondines.turnoNoche')}</option>
            </select>
          </div>

          {tablero !== null && (
            <p className="pb-2 text-sm text-texto-suave">
              {t('rondines.rango', {
                inicio: momento(tablero.inicio),
                fin: momento(tablero.fin),
              })}
            </p>
          )}

          <div className="ml-auto flex items-center gap-2 pb-0.5">
            {actualizado !== null && (
              <span className="text-xs text-texto-tenue">
                {t('rondines.actualizado', {
                  hora: actualizado.toLocaleTimeString(locale, {
                    hour: '2-digit',
                    minute: '2-digit',
                  }),
                })}
              </span>
            )}
            <Button
              variante="secundario"
              tamano="sm"
              cargando={descargando}
              onClick={() => void descargar()}
            >
              {t('rondines.descargar')}
            </Button>
          </div>
        </div>

        <p className="mt-3 text-sm text-texto-tenue">{t('rondines.ayudaTurno')}</p>
      </Card>

      {errorCarga !== '' && (
        <div
          role="alert"
          className="flex flex-wrap items-center gap-3 rounded-tarjeta border border-error bg-error-suave px-4 py-3 text-sm text-texto"
        >
          <span>{errorCarga}</span>
          <Button variante="secundario" tamano="sm" onClick={() => void cargar()}>
            {t('comun.reintentar')}
          </Button>
        </div>
      )}

      {tablero !== null && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Indicador
            etiqueta={t('rondines.cumplimiento')}
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
        <p className="text-sm text-texto-suave">{t('comun.cargando')}</p>
      ) : tablero === null ? null : tablero.puntos_activos === 0 ? (
        <div className="rounded-tarjeta border border-dashed border-borde px-6 py-12 text-center">
          <p className="text-sm font-medium text-texto">{t('rondines.sinPuntos')}</p>
          <p className="mt-2 text-sm text-texto-suave">{t('rondines.sinPuntosAyuda')}</p>
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
              {t('rondines.correoDestino')}
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
            {t('rondines.enviarCorreo')}
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
        {etiqueta}
      </p>
      <p className="mt-2 text-2xl font-semibold text-texto">{valor}</p>
    </Card>
  );
}
