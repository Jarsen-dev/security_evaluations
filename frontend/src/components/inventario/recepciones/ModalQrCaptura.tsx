'use client';

import QRCode from 'qrcode';
import { useEffect, useRef, useState } from 'react';

import { Modal } from '@/components/ui/Modal';
import { crearSesionQr, estadoSesionQr } from '@/lib/api';
import { bilingue, useTraduccion } from '@/lib/i18n';

const BASE_URL = process.env.NEXT_PUBLIC_BASE_URL ?? '';

const OPCIONES_QR = {
  width: 260,
  margin: 2,
  // Fondo blanco y módulos negros: máximo contraste para cámaras de gama baja
  // bajo la luz de la nave.
  color: { dark: '#000000', light: '#ffffff' },
  errorCorrectionLevel: 'M' as const,
};

/** Cada cuánto se pregunta si el celular ya mandó la foto. */
const MS_SONDEO = 2000;

/**
 * Handoff de la foto entre el celular y la PC.
 *
 * La PC abre una sesión, pinta el QR que apunta a `/re/{sesion}` y pregunta
 * cada dos segundos si ya llegó la foto. Cuando llega, avisa hacia arriba y
 * quien la usa dispara la extracción.
 *
 * El sondeo se detiene al cerrar el modal: sin eso, un modal olvidado abierto
 * le pegaría a la API toda la tarde.
 */
export function ModalQrCaptura({
  abierto,
  onCerrar,
  onFotoLista,
}: {
  abierto: boolean;
  onCerrar: () => void;
  onFotoLista: (sesionId: string) => void;
}) {
  const t = useTraduccion();
  const lienzo = useRef<HTMLCanvasElement>(null);
  const [sesion, setSesion] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [recibida, setRecibida] = useState(false);

  // Abre la sesión al abrir el modal, y la olvida al cerrarlo para que la
  // siguiente vez se genere una nueva (la anterior ya expiró o se usó).
  useEffect(() => {
    if (!abierto) {
      setSesion(null);
      setError('');
      setRecibida(false);
      return;
    }

    let cancelado = false;

    crearSesionQr()
      .then((nueva) => {
        if (!cancelado) setSesion(nueva.id);
      })
      .catch(() => {
        if (!cancelado) setError(t('recepciones.qrFallo'));
      });

    return () => {
      cancelado = true;
    };
  }, [abierto, t]);

  const liga = sesion === null ? '' : `${BASE_URL.replace(/\/$/, '')}/re/${sesion}`;

  useEffect(() => {
    if (sesion === null || lienzo.current === null) {
      return;
    }

    QRCode.toCanvas(lienzo.current, liga, OPCIONES_QR).catch(() => {
      setError(t('recepciones.qrFallo'));
    });
  }, [sesion, liga, t]);

  // El sondeo. Se limpia siempre en el return del efecto.
  useEffect(() => {
    if (!abierto || sesion === null || recibida) {
      return;
    }

    const temporizador = setInterval(() => {
      void estadoSesionQr(sesion)
        .then((estado) => {
          if (estado === 'subida') {
            setRecibida(true);
            onFotoLista(sesion);
          }
        })
        .catch(() => {
          // Un 409 aquí significa que la sesión venció: se avisa y se deja de
          // preguntar, en vez de insistir contra algo que ya no existe.
          setError(t('recepciones.qrExpirada'));
          setSesion(null);
        });
    }, MS_SONDEO);

    return () => clearInterval(temporizador);
  }, [abierto, sesion, recibida, onFotoLista, t]);

  return (
    <Modal
      abierto={abierto}
      onCerrar={onCerrar}
      titulo={t('recepciones.qrTitulo')}
      descripcion={t('recepciones.qrAyuda')}
      ancho="sm"
    >
      <div className="flex flex-col items-center gap-4">
        {error !== '' ? (
          <p role="alert" className="text-sm text-error">
            {error}
          </p>
        ) : (
          <>
            {/* Fondo blanco fijo: el panel es oscuro y un QR sobre fondo
                oscuro no lo lee ninguna cámara. */}
            <div className="rounded-tarjeta bg-white p-3">
              <canvas ref={lienzo} />
            </div>
            <p className="text-sm text-texto-suave" aria-live="polite">
              {bilingue(recibida ? t('recepciones.qrRecibida') : t('recepciones.qrEsperando'))}
            </p>
          </>
        )}
      </div>
    </Modal>
  );
}
