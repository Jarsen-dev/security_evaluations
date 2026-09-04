'use client';

import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { bilingue, useTraduccion } from '@/lib/i18n';

/**
 * La pregunta de las unidades a granel.
 *
 * No sirve `ui/DialogoConfirmacion`: aquel es confirmar o cancelar, y aquí
 * **«No» también guarda** —solo que sin descontar—. Mapearlo a cancelar
 * perdería el registro de un consumo que sí ocurrió.
 *
 * Cerrar con Escape no contesta: se vuelve al formulario. Que un «no» implícito
 * descontara 0 en silencio es el peor error posible aquí, porque no se nota
 * hasta el conteo físico.
 */
export function ModalTermino({
  abierto,
  unidad,
  consumo,
  guardando,
  onResponder,
  onCancelar,
}: {
  abierto: boolean;
  unidad: string;
  consumo: number;
  guardando: boolean;
  onResponder: (termino: boolean) => void;
  onCancelar: () => void;
}) {
  const t = useTraduccion();

  return (
    <Modal
      abierto={abierto}
      onCerrar={onCancelar}
      titulo={t('controlInsumos.terminoTitulo')}
      ancho="sm"
      pie={
        <>
          <Button variante="fantasma" onClick={onCancelar} disabled={guardando}>
            {bilingue(t('comun.cancelar'))}
          </Button>
          <Button
            variante="secundario"
            onClick={() => onResponder(false)}
            disabled={guardando}
          >
            {bilingue(t('controlInsumos.terminoNo'))}
          </Button>
          <Button
            variante="primario"
            onClick={() => onResponder(true)}
            cargando={guardando}
          >
            {bilingue(t('controlInsumos.terminoSi'))}
          </Button>
        </>
      }
    >
      <p className="text-sm text-texto-suave">
        {bilingue(t('controlInsumos.terminoDetalle', { unidad, consumo }))}
      </p>
    </Modal>
  );
}
