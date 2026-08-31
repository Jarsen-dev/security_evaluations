'use client';

/**
 * Aviso interno de que algo que la campana muestra cambió.
 *
 * La campana vive en el encabezado y las pestañas que la alimentan —Estudios y
 * el control PCI MTTO— en el contenido: no comparten estado de React, así que
 * al guardar se lanza un evento del navegador y la campana se recarga. Es más
 * liviano que subir un contexto al layout solo para esto.
 *
 * El evento no dice QUÉ cambió a propósito: la campana vuelve a preguntar a
 * las fuentes a las que el usuario tiene acceso, que es barato y evita que
 * cada módulo tenga que conocer a los demás.
 *
 * `Event` existe en cualquier contexto, también por la IP de la LAN (regla 5).
 */
const EVENTO = 'esh:avisos-cambiaron';

/** Lo llaman las pestañas que alimentan la campana, después de guardar. */
export function avisarCambioDeAvisos(): void {
  window.dispatchEvent(new Event(EVENTO));
}

/** Lo usa la campana; devuelve la función para dejar de escuchar. */
export function alCambiarAvisos(alCambiar: () => void): () => void {
  window.addEventListener(EVENTO, alCambiar);
  return () => window.removeEventListener(EVENTO, alCambiar);
}
