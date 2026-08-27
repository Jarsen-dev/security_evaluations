'use client';

import { useState } from 'react';

import { Button } from '@/components/ui/Button';
import { DialogoConfirmacion } from '@/components/ui/DialogoConfirmacion';
import { useIdioma, useTraduccion } from '@/lib/i18n';
import { formatearFechaIso } from '@/lib/utils';

/**
 * Aviso de que lo restaurado se capturó **otro día**.
 *
 * Importa porque estas hojas se archivan con la fecha de hoy: un borrador de
 * ayer restaurado en silencio guardaría las observaciones de ayer con la fecha
 * de hoy sin que nadie lo note. No se descarta solo —sería perder trabajo—
 * pero se avisa y el botón de reiniciar queda a la mano.
 *
 * Va arriba del formulario, con el token `alerta`, que en estas hojas ya
 * significa "falta revisar esto".
 */
export function AvisoBorrador({ fecha }: { fecha: string | null }) {
  const { t, locale } = useIdioma();

  if (fecha === null) {
    return null;
  }

  return (
    <p
      role="status"
      className="rounded-md border border-alerta bg-alerta-suave px-3 py-2 text-sm text-texto-suave"
    >
      {t('borrador.deOtroDia', { fecha: formatearFechaIso(fecha, locale) })}
    </p>
  );
}

interface BotonReiniciarProps {
  /** Si hay algo que tirar. Con `false` no se dibuja: sería ruido. */
  hayContenido: boolean;
  /** Vacía el formulario y descarta el borrador. */
  onReiniciar: () => void;
  deshabilitado?: boolean;
}

/**
 * Botón de reiniciar la hoja, para el pie del formulario.
 *
 * `fantasma` para que no compita con el de confirmar, y **siempre** con
 * confirmación: borra fotos que no están en ningún otro lado.
 */
export function BotonReiniciar({
  hayContenido,
  onReiniciar,
  deshabilitado,
}: BotonReiniciarProps) {
  const t = useTraduccion();
  const [confirmando, setConfirmando] = useState(false);

  if (!hayContenido) {
    return null;
  }

  return (
    <>
      <Button
        variante="fantasma"
        onClick={() => setConfirmando(true)}
        disabled={deshabilitado}
      >
        {t('borrador.reiniciar')}
      </Button>

      <DialogoConfirmacion
        abierto={confirmando}
        titulo={t('borrador.confirmarTitulo')}
        mensaje={t('borrador.confirmarMensaje')}
        // Por omisión diría "Eliminar", que aquí despista: no se borra un
        // registro guardado, se vacía la hoja que se está llenando.
        textoConfirmar={t('borrador.reiniciar')}
        onConfirmar={() => {
          onReiniciar();
          setConfirmando(false);
        }}
        onCancelar={() => setConfirmando(false)}
      />
    </>
  );
}
