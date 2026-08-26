'use client';

/**
 * Aviso interno de que los vencimientos cambiaron.
 *
 * La campana vive en el encabezado y la pestaña de Estudios en el contenido:
 * no comparten estado de React, así que al guardar o borrar un estudio se
 * lanza un evento del navegador y la campana se recarga. Es más liviano que
 * subir un contexto al layout solo para esto.
 *
 * `Event` existe en cualquier contexto, también por la IP de la LAN (regla 5).
 */
const EVENTO = 'esh:avisos-cambiaron';

/** Lo llama la pestaña de Estudios después de guardar o borrar. */
export function avisarCambioDeVencimientos(): void {
  window.dispatchEvent(new Event(EVENTO));
}

/** Lo usa la campana; devuelve la función para dejar de escuchar. */
export function alCambiarVencimientos(alCambiar: () => void): () => void {
  window.addEventListener(EVENTO, alCambiar);
  return () => window.removeEventListener(EVENTO, alCambiar);
}
