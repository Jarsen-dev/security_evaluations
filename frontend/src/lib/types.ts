/** Tipos compartidos entre el cliente HTTP y los componentes. */

/** Área de la planta, tal como la devuelve `GET /api/areas`. */
export interface Area {
  /** Valor guardado en la base de datos, sin acentos (ej. `Almacen`). */
  value: string;
  /** Etiqueta que se muestra al usuario, con acentos (ej. `Almacén`). */
  label: string;
}

/** Respuesta de `GET /api/health`. */
export interface EstadoSalud {
  status: string;
  db: string;
  version: string;
}

/** Datos de la red WiFi para el QR de acceso (`GET /api/wifi`). */
export interface ConfigWifi {
  configurado: boolean;
  ssid: string;
  password: string;
  seguridad: string;
  oculta: boolean;
}

/** Administrador de la sesión actual (`GET /api/auth/me`). */
export interface Admin {
  id: string;
  username: string;
  last_login_at: string | null;
}

/** Credenciales del formulario de acceso. */
export interface Credenciales {
  username: string;
  password: string;
}

/** Respuesta simple con mensaje, usada por endpoints como logout. */
export interface Mensaje {
  mensaje: string;
}

// --- Cuestionarios ---------------------------------------------------------

/** Opción de respuesta vista por el administrador. */
export interface Opcion {
  id: string;
  orden: number;
  texto: string;
  es_correcta: boolean;
}

/** Pregunta con sus opciones. */
export interface Pregunta {
  id: string;
  orden: number;
  texto: string;
  puntos: number;
  opciones: Opcion[];
}

/** Detalle completo de un cuestionario. */
export interface Cuestionario {
  id: string;
  nombre: string;
  descripcion: string | null;
  token_publico: string;
  activo: boolean;
  permitir_multiples_intentos: boolean;
  created_at: string;
  updated_at: string;
  preguntas: Pregunta[];
}

/** Fila del listado, con los conteos que muestra cada tarjeta. */
export interface CuestionarioResumen {
  id: string;
  nombre: string;
  descripcion: string | null;
  token_publico: string;
  activo: boolean;
  permitir_multiples_intentos: boolean;
  created_at: string;
  updated_at: string;
  total_preguntas: number;
  total_respuestas: number;
}

/**
 * Opción dentro del constructor.
 *
 * `id` existe solo si la opción ya está guardada; `idLocal` es una clave
 * estable para React mientras la opción vive únicamente en el navegador.
 */
export interface OpcionBorrador {
  idLocal: string;
  id?: string;
  texto: string;
  es_correcta: boolean;
}

/** Pregunta dentro del constructor, antes de guardarse. */
export interface PreguntaBorrador {
  idLocal: string;
  id?: string;
  texto: string;
  puntos: number;
  opciones: OpcionBorrador[];
}

/** Cuerpo que espera la API al crear o actualizar preguntas. */
export interface PreguntaPayload {
  id?: string;
  texto: string;
  puntos: number;
  opciones: Array<{ id?: string; texto: string; es_correcta: boolean }>;
}

/** Cuerpo de creación de un cuestionario. */
export interface CuestionarioCrearPayload {
  nombre: string;
  descripcion: string | null;
  permitir_multiples_intentos: boolean;
  preguntas: PreguntaPayload[];
}

/** Cuerpo de actualización: todos los campos son opcionales. */
export interface CuestionarioActualizarPayload {
  nombre?: string;
  descripcion?: string | null;
  activo?: boolean;
  permitir_multiples_intentos?: boolean;
  preguntas?: PreguntaPayload[];
}

// --- Formulario público ----------------------------------------------------
// Estos tipos son el espejo de app/schemas/publico.py: NUNCA deben incluir
// `es_correcta`. Si aparece aquí, es que el backend lo está filtrando.

export interface OpcionPublica {
  id: string;
  orden: number;
  texto: string;
}

export interface PreguntaPublica {
  id: string;
  orden: number;
  texto: string;
  opciones: OpcionPublica[];
}

export interface CuestionarioPublico {
  nombre: string;
  descripcion: string | null;
  total_preguntas: number;
  preguntas: PreguntaPublica[];
}

/** Datos de identidad que se piden antes de contestar. */
export interface IdentidadRespondiente {
  nombre: string;
  numero_empleado: string;
  area: string;
}

export interface IntentoIniciado {
  intento_id: string;
  nombre: string;
  total_preguntas: number;
}

/** Estado de un intento en curso, para restaurarlo tras recargar. */
export interface EstadoIntento {
  intento_id: string;
  nombre: string;
  numero_empleado: string;
  area: string;
  finalizado: boolean;
  /** pregunta_id -> opcion_id, sin marcas de acierto. */
  respuestas: Record<string, string>;
}

export interface ResultadoIntento {
  intento_id: string;
  nombre: string;
  total_preguntas: number;
  correctas: number;
  puntaje: string;
  aprobado: boolean;
  umbral_aprobacion: number;
  finalizado_at: string;
}

// --- Importación desde Excel ----------------------------------------------

/** Problema detectado en una fila del archivo. */
export interface ErrorImportacion {
  fila: number;
  mensaje: string;
}

/** Reporte que devuelve `POST /api/cuestionarios/importar-excel`. */
export interface ResultadoImportacion {
  importadas: number;
  errores: ErrorImportacion[];
  /** Preguntas parseadas; se agregan al constructor sin guardarse todavía. */
  preguntas: PreguntaPayload[];
}

/** Cuerpo de error estándar de la API. Todos los mensajes vienen en español. */
export interface ErrorApi {
  detail: string;
  errores?: Array<{ campo: string; mensaje: string }>;
}

// --- Estadísticas ----------------------------------------------------------

export interface ParticipacionResumen {
  recibidas: number;
  meta: number | null;
  porcentaje: number | null;
}

export interface Resumen {
  total_respuestas: number;
  total_en_progreso: number;
  participacion: ParticipacionResumen;
  promedio_general: number | null;
  tasa_aprobacion: number | null;
  aprobados: number;
  umbral_aprobacion: number;
}

export interface EstadisticaArea {
  area: string;
  label: string;
  intentos: number;
  promedio: number | null;
  minimo: number | null;
  maximo: number | null;
  aprobados: number;
  porcentaje_aprobacion: number | null;
  meta: number | null;
  porcentaje_participacion: number | null;
}

export interface DesgloseOpcion {
  opcion_id: string;
  texto: string;
  es_correcta: boolean;
  elegida: number;
  porcentaje: number;
}

export interface EstadisticaPregunta {
  pregunta_id: string;
  orden: number;
  texto: string;
  total_respuestas: number;
  correctas: number;
  incorrectas: number;
  porcentaje_acierto: number | null;
  porcentaje_error: number | null;
  opciones: DesgloseOpcion[];
}

export interface RangoDistribucion {
  rango: string;
  cantidad: number;
}

export interface PuntoLineaTiempo {
  fecha: string;
  cantidad: number;
  promedio: number | null;
}

export interface IntentoFila {
  id: string;
  nombre: string;
  numero_empleado: string;
  area: string;
  area_label: string;
  iniciado_at: string;
  finalizado_at: string | null;
  duracion_segundos: number | null;
  correctas: number;
  total_preguntas: number;
  puntaje: string | null;
}

export interface IntentosPaginados {
  total: number;
  page: number;
  size: number;
  items: IntentoFila[];
}

/** Opción dentro del detalle de un intento (panel de administración). */
export interface OpcionRespondida {
  id: string;
  orden: number;
  texto: string;
  es_correcta: boolean;
  elegida: boolean;
}

export interface PreguntaRespondida {
  pregunta_id: string;
  orden: number;
  texto: string;
  puntos: number;
  respondida: boolean;
  acerto: boolean;
  opciones: OpcionRespondida[];
}

/** Respuestas completas de una persona, para el modal de la tabla. */
export interface DetalleIntento {
  id: string;
  nombre: string;
  numero_empleado: string;
  area: string;
  area_label: string;
  iniciado_at: string;
  finalizado_at: string | null;
  duracion_segundos: number | null;
  correctas: number;
  total_preguntas: number;
  sin_responder: number;
  puntaje: string | null;
  aprobado: boolean;
  umbral_aprobacion: number;
  cuestionario_nombre: string;
  preguntas: PreguntaRespondida[];
}

export interface MetaArea {
  area: string;
  label: string;
  headcount: number | null;
}

/** Filtros compartidos por todos los endpoints del dashboard. */
export interface FiltrosEstadisticas {
  cuestionario_id: string;
  area?: string;
  desde?: string;
  hasta?: string;
}

/** Columnas por las que se puede ordenar la tabla de intentos. */
export type ColumnaOrdenable =
  | 'nombre'
  | 'numero_empleado'
  | 'area'
  | 'finalizado_at'
  | 'puntaje';
