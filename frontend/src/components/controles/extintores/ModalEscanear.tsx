'use client';

import { useEffect, useRef } from 'react';
import QRCode from 'qrcode';

import { Modal } from '@/components/ui/Modal';
import { bilingue, useTraduccion } from '@/lib/i18n';

const BASE_URL = process.env.NEXT_PUBLIC_BASE_URL ?? '';
const TAMANO_QR = 200;

/**
 * Cómo se revisa un extintor desde el celular.
 *
 * **No abre un escáner dentro del panel, y no es un descuido.** `getUserMedia`
 * no existe entrando por la IP de la LAN —ahí el navegador no está en contexto
 * seguro (regla 5)— y por el dominio Nginx la bloquea con
 * `Permissions-Policy: camera=()`. Toda librería de escaneo en vivo lee de esa
 * API, así que un botón-escáner funcionaría en una sola de las dos vías de
 * acceso y fallaría en silencio en la otra.
 *
 * Lo que sí funciona siempre es la cámara **nativa** del teléfono, que no pasa
 * por Permissions-Policy porque no es el navegador: se apunta al QR pegado en
 * el aparato y el sistema abre su revisión. Este modal lo explica, y de paso
 * ofrece un QR para abrir la pestaña en el celular sin teclear la dirección.
 */
export function ModalEscanear({
  abierto,
  onCerrar,
}: {
  abierto: boolean;
  onCerrar: () => void;
}) {
  const t = useTraduccion();
  const lienzo = useRef<HTMLCanvasElement>(null);

  const liga = `${BASE_URL.replace(/\/$/, '')}/controles?control=extintores`;

  useEffect(() => {
    if (!abierto || lienzo.current === null) {
      return;
    }
    void QRCode.toCanvas(lienzo.current, liga, {
      width: TAMANO_QR,
      margin: 2,
      color: { dark: '#000000', light: '#ffffff' },
      errorCorrectionLevel: 'M',
    });
  }, [abierto, liga]);

  return (
    <Modal
      abierto={abierto}
      onCerrar={onCerrar}
      titulo={t('extintores.escanearTitulo')}
      ancho="sm"
    >
      <div className="flex flex-col items-center gap-4">
        <p className="text-sm text-texto-suave">
          {bilingue(t('extintores.escanearDetalle'))}
        </p>

        {/* Fondo blanco fijo: el panel es oscuro y un QR invertido no se lee. */}
        <div className="rounded-lg bg-white p-2.5">
          <canvas ref={lienzo} />
        </div>

        <p className="text-center text-sm text-texto-suave">
          {bilingue(t('extintores.escanearAbrirAqui'))}
        </p>
        <p className="break-all text-center text-xs text-texto-tenue">{liga}</p>
      </div>
    </Modal>
  );
}
