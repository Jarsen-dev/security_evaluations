'use client';

import QRCode from 'qrcode';
import { useCallback, useEffect, useRef, useState } from 'react';

import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { useToast } from '@/components/ui/Toast';
import { ErrorDeApi, obtenerConfigWifi } from '@/lib/api';
import { bilingue, useTraduccion } from '@/lib/i18n';
import { copiarAlPortapapeles } from '@/lib/navegador';
import type { ConfigWifi, CuestionarioResumen } from '@/lib/types';
import { contenidoQrWifi } from '@/lib/wifi';

interface ModalQRProps {
  abierto: boolean;
  cuestionario: CuestionarioResumen | null;
  onCerrar: () => void;
}

const BASE_URL = process.env.NEXT_PUBLIC_BASE_URL ?? '';
/**
 * Un QR que apunte a localhost es inútil: al escanearlo, el celular intenta
 * abrir su propio localhost y no llega a ningún lado.
 */
const BASE_URL_ES_LOCAL = /localhost|127\.0\.0\.1/i.test(BASE_URL);

const TAMANO_QR = 260;

/** Opciones comunes de los dos códigos. */
const OPCIONES_QR = {
  width: TAMANO_QR,
  margin: 2,
  // Fondo blanco y módulos negros: máximo contraste para cámaras de
  // celulares gama baja bajo la luz de la nave.
  color: { dark: '#000000', light: '#ffffff' },
  errorCorrectionLevel: 'M' as const,
};

/** Normaliza el nombre del cuestionario para usarlo como nombre de archivo. */
function nombreArchivo(nombre: string, sufijo: string): string {
  const limpio = nombre.replace(/[^a-z0-9]+/gi, '_').toLowerCase();
  return `qr_${sufijo}_${limpio}.png`;
}

function descargarLienzo(lienzo: HTMLCanvasElement | null, nombre: string): void {
  if (lienzo === null) {
    return;
  }

  const enlace = document.createElement('a');
  enlace.download = nombre;
  enlace.href = lienzo.toDataURL('image/png');
  enlace.click();
}

export function ModalQR({ abierto, cuestionario, onCerrar }: ModalQRProps) {
  const t = useTraduccion();
  const { mostrarToast } = useToast();

  const lienzoCuestionario = useRef<HTMLCanvasElement>(null);
  const lienzoWifi = useRef<HTMLCanvasElement>(null);

  const [error, setError] = useState('');
  const [wifi, setWifi] = useState<ConfigWifi | null>(null);

  const url = cuestionario
    ? `${BASE_URL.replace(/\/$/, '')}/r/${cuestionario.token_publico}`
    : '';

  // --- QR del cuestionario ---
  useEffect(() => {
    if (!abierto || !cuestionario || lienzoCuestionario.current === null) {
      return;
    }

    QRCode.toCanvas(lienzoCuestionario.current, url, OPCIONES_QR).catch(() => {
      setError(t('qr.falloCuestionario'));
    });
  }, [abierto, cuestionario, url, t]);

  // --- Configuración de la red ---
  useEffect(() => {
    if (!abierto) {
      return;
    }

    let cancelado = false;

    obtenerConfigWifi()
      .then((datos) => {
        if (!cancelado) {
          setWifi(datos);
        }
      })
      .catch((problema) => {
        // Que falle la red no debe impedir compartir el cuestionario: el QR
        // principal se muestra igual y solo se omite el de WiFi.
        if (!cancelado) {
          setWifi(null);
          if (problema instanceof ErrorDeApi && problema.status !== 401) {
            setError(t('qr.falloWifi'));
          }
        }
      });

    return () => {
      cancelado = true;
    };
  }, [abierto, t]);

  const contenidoWifi = wifi ? contenidoQrWifi(wifi) : null;

  // --- QR de la red ---
  useEffect(() => {
    if (!abierto || contenidoWifi === null || lienzoWifi.current === null) {
      return;
    }

    QRCode.toCanvas(lienzoWifi.current, contenidoWifi, OPCIONES_QR).catch(() => {
      setError(t('qr.falloQrRed'));
    });
  }, [abierto, contenidoWifi, t]);

  const copiarLiga = useCallback(async () => {
    if (await copiarAlPortapapeles(url)) {
      mostrarToast(t('qr.ligaCopiada'), 'exito');
    } else {
      // La liga ya está visible en el modal, así que se puede seleccionar
      // a mano si hasta el respaldo falla.
      mostrarToast(t('qr.falloCopia'), 'error');
    }
  }, [mostrarToast, url, t]);

  return (
    <Modal
      abierto={abierto}
      onCerrar={onCerrar}
      ancho="md"
      titulo={t('qr.titulo')}
      descripcion={cuestionario?.nombre}
      pie={
        <Button variante="fantasma" onClick={onCerrar}>
          {bilingue(t('comun.cerrar'))}
        </Button>
      }
    >
      <div className="flex flex-col gap-4">
        {BASE_URL_ES_LOCAL && (
          <p
            role="alert"
            className="rounded-md border border-alerta bg-alerta-suave px-3 py-2 text-sm text-texto-suave"
          >
            <span className="font-medium text-alerta">{bilingue(t('qr.advertencia'))} </span>
            {bilingue(t('qr.baseLocal', { url: BASE_URL }))}
          </p>
        )}

        {error && (
          <p className="rounded-md border border-error bg-error-suave px-3 py-2 text-sm text-error">
            {error}
          </p>
        )}

        <div className="grid gap-4 sm:grid-cols-2">
          {/* --- Cuestionario --- */}
          <section className="flex flex-col items-center gap-3 rounded-tarjeta border border-borde p-4">
            <div className="text-center">
              <h3 className="font-medium text-texto">{bilingue(t('qr.cuestionario'))}</h3>
              <p className="text-xs text-texto-tenue">{bilingue(t('qr.escanearContestar'))}</p>
            </div>

            <div className="rounded-lg bg-white p-2.5">
              <canvas ref={lienzoCuestionario} />
            </div>

            <p className="w-full break-all text-center text-xs text-texto-suave">
              {url}
            </p>

            <div className="flex w-full flex-col gap-2">
              <Button
                variante="secundario"
                tamano="sm"
                onClick={() =>
                  descargarLienzo(
                    lienzoCuestionario.current,
                    nombreArchivo(cuestionario?.nombre ?? 'cuestionario', 'cuestionario'),
                  )
                }
              >
                {bilingue(t('qr.descargarPng'))}
              </Button>
              <Button tamano="sm" onClick={() => void copiarLiga()}>
                {bilingue(t('qr.copiarLiga'))}
              </Button>
            </div>
          </section>

          {/* --- Red WiFi --- */}
          <section className="flex flex-col items-center gap-3 rounded-tarjeta border border-borde p-4">
            <div className="text-center">
              <h3 className="font-medium text-texto">{bilingue(t('qr.red'))}</h3>
              <p className="text-xs text-texto-tenue">{bilingue(t('qr.escanearConectar'))}</p>
            </div>

            {contenidoWifi !== null && wifi !== null ? (
              <>
                <div className="rounded-lg bg-white p-2.5">
                  <canvas ref={lienzoWifi} />
                </div>

                <p className="w-full break-all text-center text-xs text-texto-suave">
                  {wifi.ssid}
                </p>

                <div className="flex w-full flex-col gap-2">
                  <Button
                    variante="secundario"
                    tamano="sm"
                    onClick={() =>
                      descargarLienzo(
                        lienzoWifi.current,
                        nombreArchivo(wifi.ssid, 'wifi'),
                      )
                    }
                  >
                    {bilingue(t('qr.descargarPng'))}
                  </Button>
                </div>
              </>
            ) : (
              <div className="flex flex-1 items-center">
                <p className="text-center text-sm text-texto-tenue">
                  {bilingue(t('qr.sinRed'))}
                  <br />
                  <span className="text-xs">{bilingue(t('qr.sinRedDetalle'))}</span>
                </p>
              </div>
            )}
          </section>
        </div>

        <p className="text-center text-xs text-texto-tenue">{bilingue(t('qr.nota'))}</p>
      </div>
    </Modal>
  );
}
