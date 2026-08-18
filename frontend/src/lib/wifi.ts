/**
 * Construcción del contenido de un código QR de acceso a WiFi.
 *
 * El formato lo entienden de forma nativa las cámaras de Android y de iOS:
 *
 *     WIFI:T:WPA;S:NombreRed;P:contrasena;H:false;;
 *
 * No es un estándar ISO, pero es el de facto desde que lo introdujo Android
 * y hoy funciona en cualquier celular de planta.
 */

import type { ConfigWifi } from './types';

/**
 * Escapa los caracteres que el formato usa como separadores.
 *
 * Sin esto, una contraseña con `;` o `:` corta el payload a la mitad y el
 * celular se conecta con una contraseña truncada, o directamente falla.
 */
function escapar(valor: string): string {
  return valor.replace(/([\\;,:"])/g, '\\$1');
}

/**
 * Envuelve en comillas los valores que son solo dígitos hexadecimales.
 *
 * El formato permite dar la contraseña como hexadecimal crudo; si no se
 * entrecomilla, una contraseña como "12345678" o "abcdef" se interpretaría
 * como hex y el celular intentaría conectarse con otra clave.
 */
function protegerHexadecimal(valor: string): string {
  return /^[0-9a-fA-F]+$/.test(valor) ? `"${valor}"` : valor;
}

/** Devuelve el texto que se codifica en el QR, o `null` si falta la red. */
export function contenidoQrWifi(wifi: ConfigWifi): string | null {
  if (!wifi.configurado || wifi.ssid.trim() === '') {
    return null;
  }

  const ssid = escapar(protegerHexadecimal(wifi.ssid));
  const partes = [`WIFI:T:${wifi.seguridad}`, `S:${ssid}`];

  // Una red abierta no lleva contraseña; incluir P vacío confunde a algunos
  // lectores, así que se omite.
  if (wifi.seguridad !== 'nopass' && wifi.password !== '') {
    partes.push(`P:${escapar(protegerHexadecimal(wifi.password))}`);
  }

  if (wifi.oculta) {
    partes.push('H:true');
  }

  // El formato cierra con punto y coma doble.
  return `${partes.join(';')};;`;
}
