import type { ClaveTraduccion } from '@/lib/i18n';
import type { EstadoInsumo } from '@/lib/types';

/**
 * Colores y etiquetas del semáforo de existencias, en un solo lugar.
 *
 * Mismo reparto de colores que el semáforo de los manómetros de Rayser, para
 * que signifiquen lo mismo en todo el panel: rojo falta, naranja sobra.
 *
 * El servidor manda el estado ya resuelto en cada insumo; esto solo lo pinta,
 * y `clasificar` lo repite en vivo mientras se llena el formulario.
 */
export const CLASES_SEMAFORO: Record<EstadoInsumo, string> = {
  bajo: 'border-error bg-error-suave text-error',
  normal: 'border-exito bg-exito-suave text-exito',
  excedido: 'border-naranja bg-naranja-suave text-naranja',
};

/** Etiqueta de cada estado: el color nunca es la única señal. */
export const CLAVES_SEMAFORO: Record<EstadoInsumo, ClaveTraduccion> = {
  bajo: 'semaforoInsumo.bajo',
  normal: 'semaforoInsumo.normal',
  excedido: 'semaforoInsumo.excedido',
};

export const PUNTOS_SEMAFORO: Record<EstadoInsumo, string> = {
  bajo: 'bg-error',
  normal: 'bg-exito',
  excedido: 'bg-naranja',
};

/**
 * Clasifica una existencia contra su rango mientras se teclea.
 *
 * Devuelve `null` si algún campo está vacío o no es un número: pintar de rojo
 * un formulario a medio llenar sería ruido, no una alerta. La misma regla vive
 * en `estado_insumo()` del backend, que es quien decide de verdad.
 */
export function clasificar(
  cantidad: string,
  minimo: string,
  maximo: string,
): EstadoInsumo | null {
  const numeros = [cantidad, minimo, maximo].map((valor) => Number(valor));

  if ([cantidad, minimo, maximo].some((v) => v.trim() === '') ||
      numeros.some((n) => Number.isNaN(n))) {
    return null;
  }

  const [existencia, topeMinimo, topeMaximo] = numeros as [number, number, number];

  if (existencia < topeMinimo) {
    return 'bajo';
  }

  if (existencia > topeMaximo) {
    return 'excedido';
  }

  return 'normal';
}
