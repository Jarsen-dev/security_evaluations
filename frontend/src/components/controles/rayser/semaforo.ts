import type { ClaveTraduccion } from '@/lib/i18n';
import type { SemaforoRayser } from '@/lib/types';

/**
 * Clases del semáforo de presiones, en un solo lugar.
 *
 * El servidor manda la clasificación ya resuelta; el formulario la repite en
 * vivo mientras se teclea, antes de guardar.
 */
export const CLASES_SEMAFORO: Record<SemaforoRayser, string> = {
  verde: 'border-exito bg-exito-suave text-exito',
  rojo: 'border-error bg-error-suave text-error',
  naranja: 'border-naranja bg-naranja-suave text-naranja',
};

/** Etiqueta de cada estado: el color nunca es la única señal. */
export const CLAVES_SEMAFORO: Record<SemaforoRayser, ClaveTraduccion> = {
  verde: 'rayser.semaforo.verde',
  rojo: 'rayser.semaforo.rojo',
  naranja: 'rayser.semaforo.naranja',
};

export const PUNTOS_SEMAFORO: Record<SemaforoRayser, string> = {
  verde: 'bg-exito',
  rojo: 'bg-error',
  naranja: 'bg-naranja',
};

/**
 * Clasifica una lectura contra el rango de operación.
 *
 * Devuelve `null` mientras el campo esté vacío o no sea un número: pintar de
 * rojo un campo a medio teclear sería ruido, no una alerta.
 */
export function clasificar(
  valor: string,
  minimo: number,
  maximo: number,
): SemaforoRayser | null {
  const numero = Number(valor.replace(',', '.'));

  if (valor.trim() === '' || Number.isNaN(numero)) {
    return null;
  }

  if (numero < minimo) {
    return 'rojo';
  }

  if (numero > maximo) {
    return 'naranja';
  }

  return 'verde';
}
