'use client';

import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { useTraduccion } from '@/lib/i18n';

interface DialogoConfirmacionProps {
  abierto: boolean;
  titulo: string;
  mensaje: string;
  /** Por omisión, "Eliminar" en el idioma activo. */
  textoConfirmar?: string;
  procesando?: boolean;
  onConfirmar: () => void;
  onCancelar: () => void;
}

/** Confirmación para acciones destructivas: borrar un cuestionario, un registro… */
export function DialogoConfirmacion({
  abierto,
  titulo,
  mensaje,
  textoConfirmar,
  procesando = false,
  onConfirmar,
  onCancelar,
}: DialogoConfirmacionProps) {
  const t = useTraduccion();

  return (
    <Modal
      abierto={abierto}
      onCerrar={onCancelar}
      titulo={titulo}
      ancho="sm"
      pie={
        <>
          <Button variante="fantasma" onClick={onCancelar}>
            {t('comun.cancelar')}
          </Button>
          <Button variante="peligro" onClick={onConfirmar} cargando={procesando}>
            {textoConfirmar ?? t('comun.eliminar')}
          </Button>
        </>
      }
    >
      <p className="text-sm text-texto-suave">{mensaje}</p>
    </Modal>
  );
}
