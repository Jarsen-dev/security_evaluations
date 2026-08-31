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

/**
 * El turno vivo ahora mismo, con la fecha de INICIO que espera la API.
 *
 * La noche del 25 al 26 se consulta pidiendo el **25** con turno `noche`, así
 * que entre la medianoche y las 07:30 hay que restar un día: a las 02:00 del
 * 26 el turno en curso es la noche que arrancó el 25.
 *
 * Solo debe llamarse en el navegador (dentro de un efecto), nunca durante el
 * render: el contenedor del frontend corre en UTC y la planta en UTC-6.
 */
export function turnoEnCurso(momento: Date = new Date()): {
  fecha: string;
  turno: Turno;
} {
  const turno = determinarTurno(momento);

  const inicio = new Date(momento);
  const minutos = momento.getHours() * 60 + momento.getMinutes();
  if (turno === 'noche' && minutos < MINUTOS_INICIO_DIA) {
    inicio.setDate(inicio.getDate() - 1);
  }

  const mes = String(inicio.getMonth() + 1).padStart(2, '0');
  const dia = String(inicio.getDate()).padStart(2, '0');

  return { fecha: `${inicio.getFullYear()}-${mes}-${dia}`, turno };
}
