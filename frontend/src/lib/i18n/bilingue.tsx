import type { ReactNode } from 'react';

/**
 * Separador con el que `t()` pega el español al coreano.
 *
 * Es un salto de línea a propósito y no un carácter exótico: donde no cabe
 * markup —`title`, `alt`, `aria-label`, un toast, un mensaje de zod— el
 * navegador ya lo muestra como dos renglones sin que nadie haga nada.
 */
export const SEPARADOR = '\n';

/**
 * Parte el string bilingüe que `t()` devuelve en coreano y pinta el español
 * debajo, como subtítulo y más chico.
 *
 * Deja pasar de largo cualquier otra cosa —un string sin separador, un número,
 * `null`, un nodo ya armado—, así que es idempotente y se puede envolver sin
 * miedo a aplicarlo dos veces sobre el mismo valor.
 *
 * La maqueta importa: `flex-col` SIN `items-*` (queda en `stretch`) para que
 * las dos líneas hereden el `text-align` de quien las contiene y se centren
 * solas dentro de un botón centrado, o se alineen a la izquierda dentro de la
 * etiqueta de un campo. Y `opacity-75` en lugar de un token de color, para que
 * el subtítulo herede el color actual y funcione igual sobre `bg-primario` que
 * sobre el gris de una tabla.
 */
export function bilingue(valor: ReactNode): ReactNode {
  if (typeof valor !== 'string') {
    return valor;
  }

  const corte = valor.indexOf(SEPARADOR);

  if (corte === -1) {
    return valor;
  }

  return (
    <span className="inline-flex flex-col align-middle leading-tight">
      <span>{valor.slice(0, corte)}</span>
      <span className="text-subtitulo font-normal opacity-75">
        {valor.slice(corte + 1)}
      </span>
    </span>
  );
}

/**
 * Aplana el string bilingüe a una sola línea.
 *
 * Para los sitios donde el salto de línea no sirve o estorba: las leyendas y
 * los tooltips de recharts (son SVG, y ahí el salto se colapsa a un espacio) y
 * los textos que se vuelven a meter dentro de otro `t()` como valor de
 * interpolación.
 */
export function unaLinea(valor: string): string {
  return valor.replace(SEPARADOR, ' / ');
}
