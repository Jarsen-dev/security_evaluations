'use client';

import { useEffect, useRef } from 'react';
import QRCode from 'qrcode';

import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { bilingue, useTraduccion } from '@/lib/i18n';
import type { Extintor } from '@/lib/types';

const BASE_URL = process.env.NEXT_PUBLIC_BASE_URL ?? '';
const BASE_URL_ES_LOCAL = /localhost|127\.0\.0\.1/i.test(BASE_URL);
const TAMANO_QR = 220;

/**
 * La etiqueta QR de un extintor.
 *
 * **El QR lleva `NEXT_PUBLIC_BASE_URL` y no `window.location.origin`.** Es el
 * caso contrario al del QR de captura de recepciones: aquella sesión dura diez
 * minutos y tiene que caer en el despliegue que la creó; esta etiqueta se pega
 * al aparato y tiene que seguir funcionando dentro de un año, así que apunta al
 * dominio público, igual que el QR impreso de los cuestionarios.
 *
 * La vista previa es solo eso: lo que se imprime sale del PDF del backend, que
 * es el único que puede garantizar los 3 x 3 cm exactos.
 */
export function ModalQrExtintor({
  extintor,
  enCola,
  imprimiendo,
  onImprimir,
  onEncolar,
  onCerrar,
}: {
  extintor: Extintor | null;
  enCola: boolean;
  imprimiendo: boolean;
  onImprimir: () => void;
  onEncolar: () => void;
  onCerrar: () => void;
}) {
  const t = useTraduccion();
  const lienzo = useRef<HTMLCanvasElement>(null);

  const liga =
    extintor === null
      ? ''
      : `${BASE_URL.replace(/\/$/, '')}/controles?control=extintores&extintor=${extintor.id}`;

  useEffect(() => {
    if (extintor === null || lienzo.current === null) {
      return;
    }
    void QRCode.toCanvas(lienzo.current, liga, {
      width: TAMANO_QR,
      margin: 2,
      color: { dark: '#000000', light: '#ffffff' },
      errorCorrectionLevel: 'M',
    });
  }, [extintor, liga]);

  return (
    <Modal
      abierto={extintor !== null}
      onCerrar={onCerrar}
      titulo={t('extintores.qrTitulo')}
      ancho="sm"
      pie={
        <>
          <Button variante="fantasma" onClick={onCerrar}>
            {bilingue(t('comun.cerrar'))}
          </Button>
          <Button variante="secundario" onClick={onEncolar} disabled={enCola}>
            {bilingue(
              enCola ? t('extintores.yaEnCola') : t('extintores.anadirACola'),
            )}
          </Button>
          <Button onClick={onImprimir} cargando={imprimiendo}>
            {bilingue(t('extintores.imprimirIndividual'))}
          </Button>
        </>
      }
    >
      <div className="flex flex-col items-center gap-3">
        {extintor !== null && (
          <p className="text-center text-sm text-texto">
            {/* Datos del aparato: no se traducen. */}
            <span className="font-semibold">{extintor.folio}</span>
            <span className="text-texto-suave">
              {' '}
              · {extintor.tipo} · {extintor.ubicacion}
            </span>
          </p>
        )}

        <div className="rounded-lg bg-white p-2.5">
          <canvas ref={lienzo} />
        </div>

        <p className="text-center text-sm text-texto-suave">
          {bilingue(t('extintores.qrDetalle'))}
        </p>

        {BASE_URL_ES_LOCAL && (
          <p
            role="alert"
            className="rounded-md border border-alerta bg-alerta-suave px-3 py-2 text-sm text-alerta"
          >
            {bilingue(t('extintores.qrLocal'))}
          </p>
        )}
      </div>
    </Modal>
  );
}
