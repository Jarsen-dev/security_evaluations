import type { Config } from 'tailwindcss';

/**
 * Tokens de color del proyecto.
 *
 * Regla: nunca usar valores arbitrarios sueltos (`bg-[#123456]`) en los
 * componentes. Si hace falta un color nuevo, se agrega aquí con un nombre
 * que describa su función, no su tono.
 *
 * Hay dos paletas:
 *   - la oscura, para el panel de administración (uso frecuente, interiores);
 *   - `claro`, exclusiva del formulario público `/r/[token]`, que se contesta
 *     en celulares bajo la luz de la nave industrial y necesita alto contraste.
 */
const config: Config = {
  content: [
    './src/app/**/*.{ts,tsx}',
    './src/components/**/*.{ts,tsx}',
    './src/hooks/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        // --- Panel de administración (tema oscuro) ---
        fondo: {
          DEFAULT: '#0e1116',
          elevado: '#161b22',
          sutil: '#1c2129',
        },
        borde: {
          DEFAULT: '#2a313c',
          fuerte: '#3d4654',
        },
        texto: {
          DEFAULT: '#e6edf3',
          suave: '#9aa7b5',
          tenue: '#6b7683',
        },
        primario: {
          DEFAULT: '#2f81f7',
          hover: '#1f6feb',
          suave: '#132a45',
        },
        exito: {
          DEFAULT: '#3fb950',
          suave: '#122b17',
        },
        alerta: {
          DEFAULT: '#d29922',
          suave: '#2e2410',
        },
        error: {
          DEFAULT: '#f85149',
          suave: '#3a1414',
        },
        // Tercer color del semáforo de los controles: una lectura por encima
        // del rango normal no es lo mismo que una por debajo, y `alerta` ya
        // significa otra cosa en el panel.
        naranja: {
          DEFAULT: '#f0883e',
          suave: '#3a2410',
        },

        // --- Formulario público (tema claro, alto contraste) ---
        claro: {
          fondo: '#ffffff',
          superficie: '#f4f6f8',
          borde: '#c9d1d9',
          texto: '#111820',
          suave: '#48525e',
          primario: '#0b5cd5',
          exito: '#0f7b2f',
          error: '#c02626',
        },
      },
      fontFamily: {
        // Los respaldos coreanos son obligatorios: sin ellos, Windows dibuja
        // el hangul con una serif de sistema que desentona con todo el panel.
        sans: [
          'system-ui',
          '-apple-system',
          'Segoe UI',
          'Roboto',
          'Malgun Gothic',
          'Apple SD Gothic Neo',
          'Noto Sans KR',
          'sans-serif',
        ],
      },
      spacing: {
        // Altura mínima de un objetivo táctil: los operadores contestan
        // el formulario con guantes puestos.
        tactil: '3rem',
      },
      borderRadius: {
        tarjeta: '0.625rem',
      },
    },
  },
  plugins: [],
};

export default config;
