/**
 * Utilidades que compensan las APIs restringidas a "contextos seguros".
 *
 * El navegador solo considera seguro a HTTPS y a `localhost`. Este sistema
 * corre por HTTP sobre una IP de LAN (`http://192.168.1.50:8080`), así que
 * ahí `crypto.randomUUID` y `navigator.clipboard` sencillamente NO EXISTEN.
 *
 * Es una diferencia que no se nota al desarrollar en localhost y revienta en
 * planta, así que todo lo que dependa de esas APIs debe pasar por aquí.
 */

/**
 * Genera un identificador único para uso local (claves de React).
 *
 * No es criptográficamente sensible: solo distingue elementos de una lista
 * mientras viven en el navegador.
 */
export function idUnico(): string {
  // Camino normal: HTTPS o localhost.
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }

  // getRandomValues SÍ está disponible en contextos no seguros, a diferencia
  // de randomUUID. Es el camino que se usa en planta.
  if (typeof crypto !== 'undefined' && typeof crypto.getRandomValues === 'function') {
    const bytes = crypto.getRandomValues(new Uint8Array(16));
    return Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
  }

  // Último recurso para navegadores muy viejos.
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

/**
 * Copia texto al portapapeles con respaldo para contextos no seguros.
 *
 * Devuelve `true` si lo logró. El respaldo usa `document.execCommand`, que
 * está obsoleto pero es lo único que funciona por HTTP y sigue soportado en
 * los navegadores de escritorio y de celular que se usan en planta.
 */
export async function copiarAlPortapapeles(texto: string): Promise<boolean> {
  if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(texto);
      return true;
    } catch {
      // Permiso denegado: se intenta con el respaldo de abajo.
    }
  }

  if (typeof document === 'undefined') {
    return false;
  }

  const area = document.createElement('textarea');
  area.value = texto;
  // Fuera de la vista, pero no `display:none`: un elemento oculto así no se
  // puede seleccionar y la copia falla.
  area.style.position = 'fixed';
  area.style.top = '-9999px';
  area.style.opacity = '0';
  area.setAttribute('readonly', '');
  document.body.appendChild(area);

  try {
    area.select();
    area.setSelectionRange(0, texto.length);
    return document.execCommand('copy');
  } catch {
    return false;
  } finally {
    document.body.removeChild(area);
  }
}
