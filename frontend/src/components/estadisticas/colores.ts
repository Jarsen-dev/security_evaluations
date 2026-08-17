/**
 * Colores de las gráficas.
 *
 * Recharts necesita valores de color reales, no clases de Tailwind, así que
 * los tokens se replican aquí. Si cambia la paleta de `tailwind.config.ts`,
 * hay que actualizar este archivo también.
 */

export const COLORES = {
  primario: '#2f81f7',
  meta: '#3d4654',
  exito: '#3fb950',
  alerta: '#d29922',
  error: '#f85149',
  texto: '#9aa7b5',
  rejilla: '#2a313c',
  fondoTooltip: '#161b22',
} as const;

/** Colores del histograma: rojo en los reprobados, verde en los altos. */
export const COLOR_POR_RANGO: Record<string, string> = {
  '0-59': COLORES.error,
  '60-69': COLORES.alerta,
  '70-79': COLORES.primario,
  '80-89': COLORES.primario,
  '90-100': COLORES.exito,
};

/** Estilo común del tooltip, para que las cinco gráficas se vean igual. */
export const ESTILO_TOOLTIP = {
  backgroundColor: COLORES.fondoTooltip,
  border: `1px solid ${COLORES.rejilla}`,
  borderRadius: '0.5rem',
  fontSize: '0.8125rem',
  color: '#e6edf3',
} as const;
