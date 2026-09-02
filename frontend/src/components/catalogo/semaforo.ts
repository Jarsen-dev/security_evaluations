import type { ClaveTraduccion } from '@/lib/i18n';
import type { EstadoInsumo } from '@/lib/types';

/**
 * Colores y etiquetas del semáforo de existencias, en un solo lugar.
 *
 * Mismo reparto de colores que el semáforo de los manómetros de Rayser, para
 * que signifiquen lo mismo en todo el panel: rojo falta, naranja sobra. El
 * amarillo del tramo intermedio reutiliza `alerta`, y el gris de "sin topes"
 * el par sutil del panel: no hay tokens propios para esos dos y no se
 * inventan valores arbitrarios.
 *
 * El servidor manda el estado ya resuelto en cada insumo; esto solo lo pinta,
 * y `clasificar` lo repite en vivo mientras se llena el formulario.
 */
export const CLASES_SEMAFORO: Record<EstadoInsumo, string> = {
  bajo: 'border-error bg-error-suave text-error',
  medio: 'border-alerta bg-alerta-suave text-alerta',
  normal: 'border-exito bg-exito-suave text-exito',
  excedido: 'border-naranja bg-naranja-suave text-naranja',
  sin_topes: 'border-borde bg-fondo-sutil text-texto-tenue',
};

/**
 * Los cinco estados, en el orden en que se ofrecen en el filtro: del que pide
 * acción al que no la pide. El backend valida contra la misma lista.
 */
export const ESTADOS_INSUMO: ReadonlyArray<EstadoInsumo> = [
  'bajo',
  'medio',
  'normal',
  'excedido',
  'sin_topes',
];

/** Etiqueta de cada estado: el color nunca es la única señal. */
export const CLAVES_SEMAFORO: Record<EstadoInsumo, ClaveTraduccion> = {
  bajo: 'semaforoInsumo.bajo',
  medio: 'semaforoInsumo.medio',
  normal: 'semaforoInsumo.normal',
  excedido: 'semaforoInsumo.excedido',
  sin_topes: 'semaforoInsumo.sinTopes',
};

export const PUNTOS_SEMAFORO: Record<EstadoInsumo, string> = {
  bajo: 'bg-error',
  medio: 'bg-alerta',
  normal: 'bg-exito',
  excedido: 'bg-naranja',
  sin_topes: 'bg-borde-fuerte',
};

/**
 * Tinte de la fila en la tabla de existencias.
 *
 * Muy tenue a propósito: es una ayuda para barrer la tabla de un vistazo, no
 * la señal principal —esa es el punto de color con su etiqueta—, y con el
 * fondo saturado el texto de la fila deja de leerse.
 */
export const FILAS_SEMAFORO: Record<EstadoInsumo, string> = {
  bajo: 'bg-error-suave/40',
  medio: 'bg-alerta-suave/40',
  normal: 'bg-exito-suave/40',
  excedido: 'bg-naranja-suave/40',
  sin_topes: '',
};

/**
 * Clasifica una existencia contra sus topes mientras se teclea.
 *
 * Devuelve `null` si algún campo está vacío o no es un número: pintar de rojo
 * un formulario a medio llenar sería ruido, no una alerta. La misma cascada
 * vive en `estado_insumo()` del backend, que es quien decide de verdad; aquí
 * se repite solo para la vista previa del modal.
 */
export function clasificar(
  existencia: string,
  minimo: string,
  maximo: string,
): EstadoInsumo | null {
  const campos = [existencia, minimo, maximo];
  const numeros = campos.map((valor) => Number(valor));

  if (campos.some((valor) => valor.trim() === '') || numeros.some((n) => Number.isNaN(n))) {
    return null;
  }

  const [cantidad, topeMinimo, topeMaximo] = numeros as [number, number, number];

  // Sin máximo no hay contra qué medir: se dice eso y no se inventa un color.
  if (topeMaximo <= 0) {
    return 'sin_topes';
  }

  if (cantidad > topeMaximo) {
    return 'excedido';
  }

  // Enteros multiplicando cruzado, igual que el backend: con `0.35 * maximo`
  // el color de la frontera exacta depende del redondeo del flotante.
  if (cantidad < topeMinimo || cantidad * 100 <= topeMaximo * 35) {
    return 'bajo';
  }

  if (cantidad * 100 <= topeMaximo * 75) {
    return 'medio';
  }

  return 'normal';
}
