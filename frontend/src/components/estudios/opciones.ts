import type { ClaveTraduccion } from '@/lib/i18n';

/** Los seis campos de selección del formulario de estudios. */
export type GrupoOpciones =
  | 'vigencia'
  | 'prioridad'
  | 'tipo'
  | 'estatus'
  | 'vencimiento'
  | 'aprobacion';

/**
 * Dónde vive el rótulo de cada opción dentro del diccionario.
 *
 * El backend manda la clave y su etiqueta en español; el panel muestra el
 * idioma activo (regla 6), así que aquí se enlaza cada clave con la suya. El
 * mapa está escrito a mano a propósito: `ClaveTraduccion` es una unión de
 * rutas literales, así que armar la clave con una plantilla obligaría a un
 * cast y se perdería la red de seguridad de `npm run typecheck`.
 *
 * Si el catálogo del backend estrena una opción y aquí falta, la tabla cae en
 * la etiqueta en español en vez de mostrar la ruta cruda.
 */
const ETIQUETAS: Record<string, ClaveTraduccion> = {
  'vigencia.una_vez': 'estudios.opciones.vigencia.una_vez',
  'vigencia.1_ano': 'estudios.opciones.vigencia.1_ano',
  'vigencia.2_anos': 'estudios.opciones.vigencia.2_anos',
  'vigencia.3_anos': 'estudios.opciones.vigencia.3_anos',
  'vigencia.4_anos': 'estudios.opciones.vigencia.4_anos',
  'vigencia.5_anos': 'estudios.opciones.vigencia.5_anos',

  'prioridad.alta': 'estudios.opciones.prioridad.alta',
  'prioridad.media': 'estudios.opciones.prioridad.media',
  'prioridad.baja': 'estudios.opciones.prioridad.baja',

  'tipo.interno': 'estudios.opciones.tipo.interno',
  'tipo.externo': 'estudios.opciones.tipo.externo',

  'estatus.pendiente': 'estudios.opciones.estatus.pendiente',
  'estatus.proceso': 'estudios.opciones.estatus.proceso',
  'estatus.ok': 'estudios.opciones.estatus.ok',

  'vencimiento.en_curso': 'estudios.opciones.vencimiento.en_curso',
  'vencimiento.vencido': 'estudios.opciones.vencimiento.vencido',
  'vencimiento.pendiente': 'estudios.opciones.vencimiento.pendiente',

  'aprobacion.ok': 'estudios.opciones.aprobacion.ok',
  'aprobacion.pendiente': 'estudios.opciones.aprobacion.pendiente',
  'aprobacion.proceso': 'estudios.opciones.aprobacion.proceso',
  'aprobacion.na': 'estudios.opciones.aprobacion.na',
};

export function claveEtiqueta(
  grupo: GrupoOpciones,
  clave: string,
): ClaveTraduccion | undefined {
  return ETIQUETAS[`${grupo}.${clave}`];
}

/**
 * Semáforo de una celda de la tabla de registros.
 *
 * El color lo decide el backend (`opcion.semaforo`); aquí solo se traduce a
 * tokens de Tailwind. Se muestra únicamente en los registros ya capturados,
 * no en el formulario: elegir una opción no debe sentirse como acertar o
 * fallar un color.
 */
export const CLASES_CELDA: Record<string, string> = {
  verde: 'bg-exito-suave text-exito',
  amarillo: 'bg-alerta-suave text-alerta',
  rojo: 'bg-error-suave text-error',
  gris: 'bg-fondo-sutil text-texto-tenue',
};
