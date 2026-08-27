/**
 * Turno de 12 horas de la planta: día de 07:30 a 19:30, noche el resto.
 *
 * Mismos límites que usa el backend para calcular `encabezado.turno` en los
 * controles de silos y tableros (`rondin_service.turno_actual`), y los
 * mismos con los que ya se arman los rondines. Aquí es solo la ayuda visual
 * del encabezado: se apoya en la hora del navegador, no en una llamada a la
 * API, porque no hay nada que ocultar en "qué hora es ahora".
 */
export type Turno = 'dia' | 'noche';

const MINUTOS_INICIO_DIA = 7 * 60 + 30; // 07:30
const MINUTOS_FIN_DIA = 19 * 60 + 30; // 19:30

export function determinarTurno(momento: Date = new Date()): Turno {
  const minutos = momento.getHours() * 60 + momento.getMinutes();
  return minutos >= MINUTOS_INICIO_DIA && minutos < MINUTOS_FIN_DIA ? 'dia' : 'noche';
}
