'use client';

import QRCode from 'qrcode';
import { useEffect, useRef, useState } from 'react';

import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { useToast } from '@/components/ui/Toast';
import { useTraduccion } from '@/lib/i18n';
import { copiarAlPortapapeles } from '@/lib/navegador';
import type { PuntoRondin } from '@/lib/types';

const BASE_URL = process.env.NEXT_PUBLIC_BASE_URL ?? '';

const TAMANO_QR = 260;

const OPCIONES_QR = {
  width: TAMANO_QR,
  margin: 2,
  // Fondo blanco y módulos negros: máximo contraste para cámaras de celulares
  // gama baja bajo la luz de la nave.
  color: { dark: '#000000', light: '#ffffff' },
  errorCorrectionLevel: 'M' as const,
};

/**
 * El código QR de un punto, para revisarlo o reimprimir uno suelto.
 *
 * La hoja con todos los puntos se descarga aparte, desde el botón de imprimir.
 */
export function ModalQrPunto({
  punto,
  onCerrar,
}: {
  punto: PuntoRondin | null;
  onCerrar: () => void;
}) {
  const t = useTraduccion();
  const { mostrarToast } = useToast();
  const lienzo = useRef<HTMLCanvasElement>(null);
  const [error, setError] = useState('');

  const liga = punto === null ? '' : `${BASE_URL.replace(/\/$/, '')}/p/${punto.token_publico}`;

  useEffect(() => {
    if (punto === null || lienzo.current === null) {
      return;
    }

    setError('');
    QRCode.toCanvas(lienzo.current, liga, OPCIONES_QR).catch(() => {
      setError(t('comun.errorGenerico'));
    });
  }, [punto, liga, t]);

  async function copiar() {
    // `copiarAlPortapapeles` y no `navigator.clipboard`: entrando por la IP de
    // la LAN el contexto no es seguro y esa API ni siquiera existe (regla 5).
    const copiado = await copiarAlPortapapeles(liga);
    mostrarToast(
      copiado ? t('puntosRondin.ligaCopiada') : t('puntosRondin.falloCopiar', { liga }),
      copiado ? 'exito' : 'error',
    );
  }

  function descargar() {
    if (lienzo.current === null || punto === null) {
      return;
    }

    const enlace = document.createElement('a');
    enlace.href = lienzo.current.toDataURL('image/png');
    enlace.download = `punto_${punto.numero}.png`;
    enlace.click();
  }

  return (
    <Modal
      abierto={punto !== null}
      onCerrar={onCerrar}
      ancho="sm"
      titulo={
        punto === null ? '' : `${t('puntosRondin.codigo')} — ${t('rondines.punto')} ${punto.numero}`
      }
      pie={
        <>
          <Button variante="secundario" onClick={() => void copiar()}>
            {t('cuestionarios.liga')}
          </Button>
          <Button onClick={descargar}>{t('puntosRondin.descargarQr')}</Button>
        </>
      }
    >
      <div className="flex flex-col items-center gap-4">
        {/* Fondo blanco fijo: el panel es oscuro y un QR sobre gris no se lee. */}
        <div className="rounded-tarjeta bg-white p-4">
          <canvas ref={lienzo} />
        </div>

        {punto !== null && (
          <p className="text-center text-sm text-texto">
            {punto.nombre}
            {punto.ubicacion && (
              <span className="block text-texto-tenue">{punto.ubicacion}</span>
            )}
          </p>
        )}

        <p className="break-all text-center font-mono text-xs text-texto-tenue">{liga}</p>

        {error !== '' && (
          <p role="alert" className="text-sm text-error">
            {error}
          </p>
        )}
      </div>
    </Modal>
  );
}
