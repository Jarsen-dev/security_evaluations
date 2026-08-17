'use client';

import QRCode from 'qrcode';
import { useEffect, useRef, useState } from 'react';

import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { useToast } from '@/components/ui/Toast';
import { copiarAlPortapapeles } from '@/lib/navegador';
import type { CuestionarioResumen } from '@/lib/types';

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

const TAMANO_QR = 320;

export function ModalQR({ abierto, cuestionario, onCerrar }: ModalQRProps) {
  const { mostrarToast } = useToast();
  const lienzo = useRef<HTMLCanvasElement>(null);
  const [error, setError] = useState('');

  const url = cuestionario
    ? `${BASE_URL.replace(/\/$/, '')}/r/${cuestionario.token_publico}`
    : '';

  useEffect(() => {
    if (!abierto || !cuestionario || lienzo.current === null) {
      return;
    }

    QRCode.toCanvas(lienzo.current, url, {
      width: TAMANO_QR,
      margin: 2,
      // Fondo blanco y módulos negros: máximo contraste para cámaras de
      // celulares gama baja bajo la luz de la nave.
      color: { dark: '#000000', light: '#ffffff' },
      errorCorrectionLevel: 'M',
    }).catch(() => {
      setError('No se pudo generar el código QR.');
    });
  }, [abierto, cuestionario, url]);

  async function copiarLiga() {
    if (await copiarAlPortapapeles(url)) {
      mostrarToast('Liga copiada al portapapeles.', 'exito');
    } else {
      // La liga ya está visible en el modal, así que se puede seleccionar
      // a mano si hasta el respaldo falla.
      mostrarToast('No se pudo copiar. Selecciona la liga de arriba.', 'error');
    }
  }

  function descargarPng() {
    if (lienzo.current === null || cuestionario === null) {
      return;
    }

    const enlace = document.createElement('a');
    enlace.download = `qr_${cuestionario.nombre.replace(/[^a-z0-9]+/gi, '_').toLowerCase()}.png`;
    enlace.href = lienzo.current.toDataURL('image/png');
    enlace.click();
  }

  return (
    <Modal
      abierto={abierto}
      onCerrar={onCerrar}
      ancho="sm"
      titulo="Código QR del cuestionario"
      descripcion={cuestionario?.nombre}
      pie={
        <Button variante="fantasma" onClick={onCerrar}>
          Cerrar
        </Button>
      }
    >
      <div className="flex flex-col items-center gap-4">
        {BASE_URL_ES_LOCAL && (
          <p
            role="alert"
            className="w-full rounded-md border border-alerta bg-alerta-suave px-3 py-2 text-sm text-texto-suave"
          >
            <span className="font-medium text-alerta">Advertencia: </span>
            la liga apunta a <code>{BASE_URL}</code>. Este código QR no
            funcionará desde un celular. Configura <code>NEXT_PUBLIC_BASE_URL</code>{' '}
            con la IP del servidor en la LAN y reconstruye el frontend.
          </p>
        )}

        {error ? (
          <p className="text-sm text-error">{error}</p>
        ) : (
          <div className="rounded-lg bg-white p-3">
            <canvas ref={lienzo} />
          </div>
        )}

        <p className="w-full break-all rounded-md border border-borde bg-fondo px-3 py-2 text-center text-sm text-texto-suave">
          {url}
        </p>

        <div className="flex w-full gap-2">
          <Button variante="secundario" className="flex-1" onClick={descargarPng}>
            Descargar PNG
          </Button>
          <Button className="flex-1" onClick={() => void copiarLiga()}>
            Copiar liga
          </Button>
        </div>
      </div>
    </Modal>
  );
}
