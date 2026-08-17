'use client';

import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';

interface DialogoConfirmacionProps {
  abierto: boolean;
  titulo: string;
  mensaje: string;
  textoConfirmar?: string;
  procesando?: boolean;
  onConfirmar: () => void;
  onCancelar: () => void;
}

/** Confirmación para acciones destructivas, como eliminar un cuestionario. */
export function DialogoConfirmacion({
  abierto,
  titulo,
  mensaje,
  textoConfirmar = 'Eliminar',
  procesando = false,
  onConfirmar,
  onCancelar,
}: DialogoConfirmacionProps) {
  return (
    <Modal
      abierto={abierto}
      onCerrar={onCancelar}
      titulo={titulo}
      ancho="sm"
      pie={
        <>
          <Button variante="fantasma" onClick={onCancelar}>
            Cancelar
          </Button>
          <Button variante="peligro" onClick={onConfirmar} cargando={procesando}>
            {textoConfirmar}
          </Button>
        </>
      }
    >
      <p className="text-sm text-texto-suave">{mensaje}</p>
    </Modal>
  );
}
