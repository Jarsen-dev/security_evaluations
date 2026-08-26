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

// --- Usuarios y permisos ---------------------------------------------------

/** Módulos del panel sobre los que se otorgan permisos. */
export type Modulo = 'cuestionarios' | 'controles' | 'inventario' | 'estudios';

/** Lo que puede hacer un usuario dentro de un módulo. */
export interface PermisoModulo {
  /** Modificar y eliminar. Ver y crear ya vienen con el acceso. */
  editar: boolean;
}

/**
 * Permisos por módulo. Un módulo AUSENTE significa que el usuario no tiene
 * acceso a esa pestaña, así que la clave es opcional a propósito.
 */
export type Permisos = Partial<Record<Modulo, PermisoModulo>>;

/** Usuario de la sesión actual (`GET /api/auth/me`). */
export interface Admin {
  id: string;
  nombre: string;
  username: string;
  email: string | null;
  activo: boolean;
  es_superadmin: boolean;
  permisos: Permisos;
  last_login_at: string | null;
}

/** Usuario tal como lo lista la pestaña de Administración. */
export interface Usuario extends Admin {
  created_at: string;
}

/** Alta de un usuario. */
export interface UsuarioCrearPayload {
  nombre: string;
  username: string;
  email: string;
  password: string;
  permisos: Permisos;
}

/** Edición de un usuario. `password` vacío conserva la actual. */
export interface UsuarioActualizarPayload {
  nombre: string;
  username: string;
  email: string;
  password?: string;
  permisos: Permisos;
}

// --- Bitácora --------------------------------------------------------------

/** Un renglón de actividad registrada. */
export interface RegistroBitacora {
  id: number;
  creado_at: string;
  usuario_id: string | null;
  username: string;
  accion: string;
  modulo: string;
  /** Redactada por el backend, ya en español: es dato, no interfaz. */
  descripcion: string;
  metodo: string;
  ruta: string;
  estado: number;
  ip: string | null;
}

/** Página de la bitácora. */
export interface BitacoraPaginada {
  total: number;
  page: number;
  size: number;
  items: RegistroBitacora[];
}

/** Filtros de la pantalla de logs. */
export interface FiltrosBitacora {
  fecha?: string;
  hora_desde?: string;
  hora_hasta?: string;
  usuario?: string;
}

// --- Mantenimiento ---------------------------------------------------------

/** Un botón de acceso a pgAdmin. */
export interface AccesoPgAdmin {
  entorno: 'local' | 'produccion';
  url: string;
  disponible: boolean;
}

/** Accesos y credenciales de pgAdmin (`GET /api/administracion/mantenimiento`). */
export interface Mantenimiento {
  accesos: AccesoPgAdmin[];
  email: string;
  password: string;
  configurado: boolean;
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

// --- Controles ESH ---------------------------------------------------------

/** Clasificación de una lectura de manómetro, calculada en el servidor. */
export type SemaforoRayser = 'verde' | 'rojo' | 'naranja';

export interface LecturaManometro {
  valor: string;
  semaforo: SemaforoRayser;
}

/**
 * Registro diario del control de presiones.
 *
 * No incluye las imágenes: solo los identificadores de sus fotos, que se piden
 * una por una a `/api/controles/fotos/{id}`.
 */
export interface RegistroRayser {
  id: string;
  fecha: string;
  manometros: LecturaManometro[];
  observaciones: string | null;
  fotos: string[];
  fuera_de_rango: boolean;
  responsable: string;
  creado_at: string;
}

/** Rango de operación de los manómetros, servido por la API. */
export interface RangoRayser {
  minimo: string;
  maximo: string;
  normal: string;
  manometros: number;
}

/** Respuestas posibles de un punto de la inspección de SQP. */
export type ValorSqp = 'si' | 'no' | 'na';

export interface PuntoSqp {
  orden: number;
  codigo: string;
  seccion: string;
  texto: string;
}

export interface CatalogoSqp {
  secciones: string[];
  puntos: PuntoSqp[];
  renglones_sustancias: number;
}

export interface RespuestaSqpPayload {
  orden: number;
  valor: ValorSqp;
  observaciones?: string | null;
}

export interface InspeccionSqpPayload {
  fecha: string;
  area: string;
  encargado: string;
  cargo?: string | null;
  sustancias?: string | null;
  respuestas: RespuestaSqpPayload[];
}

export interface InspeccionSqpResumen {
  id: string;
  fecha: string;
  area: string;
  area_label: string;
  encargado: string;
  responsable: string;
  total_no: number;
  creado_at: string;
}

// --- Controles de lista de verificación (OK / NO OK) -----------------------

export type ValorChecklist = 'ok' | 'no_ok';

export interface PuntoControl {
  orden: number;
  clave: string;
  etiqueta: string;
  /** Texto coreano del formato bilingüe; solo lo traen silos y tableros. */
  etiqueta_ko: string | null;
  categoria: string | null;
  /** Unidad de la lectura que pide el punto ("°C"); null si no pide ninguna. */
  medicion: string | null;
}

export type TipoCampo = 'texto' | 'texto_largo' | 'hora' | 'numero' | 'opcion';

/** Campo del encabezado o de un bloque del formato. */
export interface CampoFormato {
  clave: string;
  etiqueta: string;
  etiqueta_ko: string | null;
  tipo: TipoCampo;
  opciones: string[];
  unidad: string | null;
  obligatorio: boolean;
}

export interface SeccionFormato {
  clave: string;
  titulo: string;
  titulo_ko: string | null;
  campos: CampoFormato[];
  /** El bloque de anomalía solo aplica cuando hay algún punto en NO. */
  solo_con_hallazgos: boolean;
}

/** Definición de un control: sus puntos y sus límites, servida por la API. */
export interface CatalogoChecklist {
  clave: string;
  titulo: string;
  titulo_ko: string | null;
  subtitulo: string | null;
  puntos: PuntoControl[];
  max_fotos: number;
  /** Cómo se rotulan las dos respuestas: OK/NO OK o SÍ/NO. */
  estilo_valores: 'ok_no_ok' | 'si_no';
  encabezado: CampoFormato[];
  secciones: SeccionFormato[];
  nota: string | null;
  nota_ko: string | null;
  /**
   * Formato por inspección: lleva encabezado, admite varios registros el mismo
   * día y su Excel se descarga por registro, no por mes.
   */
  por_inspeccion: boolean;
}

export interface PuntoChecklist {
  orden: number;
  clave: string;
  etiqueta: string;
  etiqueta_ko: string | null;
  categoria: string | null;
  valor: ValorChecklist;
  observaciones: string | null;
  medicion: string | null;
  fotos: string[];
}

export interface RegistroChecklist {
  id: string;
  fecha: string;
  puntos: PuntoChecklist[];
  hay_hallazgos: boolean;
  encabezado: Record<string, string>;
  secciones: Record<string, Record<string, string>>;
  responsable: string;
  creado_at: string;
}

// --- Pláticas diarias de seguridad -----------------------------------------

/**
 * Área del formato de pláticas.
 *
 * No son las mismas que `Area`: aquellas son las del cuestionario y estas las
 * columnas de esta hoja, con la abreviatura que usa el personal de piso.
 */
export interface AreaPlatica {
  clave: string;
  etiqueta: string;
}

export interface Platica {
  id: string;
  fecha: string;
  tema: string;
  areas: AreaPlatica[];
  fotos: string[];
  responsable: string;
  creado_at: string;
}

// --- Estudios y capacitaciones ---------------------------------------------

/**
 * Una opción de un campo de selección, como la sirve
 * `GET /api/estudios/catalogo`.
 *
 * `etiqueta` viene en español y solo se usa de respaldo: el rótulo que ve el
 * usuario sale del diccionario del idioma activo (regla 6).
 */
export interface OpcionEstudio {
  clave: string;
  etiqueta: string;
  /** Cómo se abrevia en la tabla ("IN" en lugar de "Interno"). */
  corto: string;
  /** `'verde'`, `'amarillo'`, `'rojo'`, `'gris'` o vacío si no se semaforiza. */
  semaforo: string;
  /** Solo la prioridad: 1 alta, 2 media, 3 baja. */
  numero: number | null;
}

/** Todas las listas de opciones del formulario de estudios. */
export interface CatalogoEstudios {
  vigencias: OpcionEstudio[];
  prioridades: OpcionEstudio[];
  tipos: OpcionEstudio[];
  estatus: OpcionEstudio[];
  vencimientos: OpcionEstudio[];
  aprobaciones: OpcionEstudio[];
  /** Clave del vencimiento que habilita el campo de fecha. */
  vencimiento_con_fecha: string;
  /** Clave del estatus que habilita el campo de link. */
  estatus_con_link: string;
}

/** Lo que se envía al dar de alta o al editar un estudio. */
export interface EstudioPayload {
  despacho: string;
  estudio: string;
  estudio_ko: string | null;
  vigencia: string;
  prioridad: string;
  tipo: string;
  estatus: string;
  vencimiento: string;
  fecha_vencimiento: string | null;
  aprobado: string;
  pagado: string;
  link: string | null;
}

export interface Estudio extends EstudioPayload {
  id: string;
  responsable: string;
  creado_at: string;
  actualizado_at: string | null;
}

/** Un estudio que vence pronto o que ya venció. */
export interface AvisoVencimiento {
  id: string;
  estudio: string;
  despacho: string;
  fecha_vencimiento: string;
  /** Días que faltan; negativo si la fecha ya pasó. */
  dias: number;
  vencido: boolean;
}

/** Lo que dibuja la campana del encabezado. */
export interface Avisos {
  total: number;
  vencidos: number;
  avisos: AvisoVencimiento[];
}
