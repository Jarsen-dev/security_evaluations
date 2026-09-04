import type { ClaveTraduccion } from '@/lib/i18n';
import type { EstadoExtintor } from '@/lib/types';

/**
 * Los cuatro estados del vencimiento, en mapas paralelos.
 *
 * El orden va del más urgente al más tranquilo, y es el que alimenta el
 * `<select>` del filtro: sale de aquí y no escrito a mano, así que agregar un
 * estado no puede dejar el filtro a medias.
 *
 * El color lo decide el servidor (`estado_vencimiento`); aquí solo se pinta.
 * Amarillo es `alerta` y no `naranja`: aquel ya significa otra cosa en el
 * panel —una lectura por encima del rango— y aquí no hay "por encima".
 */
export const ESTADOS_EXTINTOR: ReadonlyArray<EstadoExtintor> = [
  'vencido',
  'critico',
  'por_vencer',
  'vigente',
];

export const CLAVES_SEMAFORO: Record<EstadoExtintor, ClaveTraduccion> = {
  vencido: 'extintores.estadoVencido',
  critico: 'extintores.estadoCritico',
  por_vencer: 'extintores.estadoPorVencer',
  vigente: 'extintores.estadoVigente',
};

/** El punto de color de la celda. Nunca va solo: siempre acompañado de texto. */
export const PUNTOS_SEMAFORO: Record<EstadoExtintor, string> = {
  vencido: 'bg-error',
  critico: 'bg-error',
  por_vencer: 'bg-alerta',
  vigente: 'bg-exito',
};

/** Tinte de la fila entera, para localizar de un vistazo lo que urge. */
export const FILAS_SEMAFORO: Record<EstadoExtintor, string> = {
  vencido: 'bg-error-suave/40',
  critico: 'bg-error-suave/25',
  por_vencer: 'bg-alerta-suave/25',
  vigente: '',
};
