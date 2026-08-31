/**
 * Cliente HTTP tipado del proyecto.
 *
 * En el navegador las peticiones son relativas (`/api/...`): Nginx las enruta
 * al backend, así que el frontend y la API comparten origen y la cookie de
 * sesión viaja sola. En el servidor (Server Components) no existe origen
 * relativo, así que se usa la URL interna de Docker.
 */

import type {
  Admin,
  Area,
  AreaPlatica,
  Avisos,
  AvisosPciMtto,
  BitacoraPaginada,
  CatalogoChecklist,
  CatalogoEstudios,
  EscaneoRegistrado,
  CapturaPciMtto,
  CatalogoSqp,
  CierreHallazgo,
  CierrePayload,
  ConfigWifi,
  Credenciales,
  Cuestionario,
  CuestionarioActualizarPayload,
  CuestionarioCrearPayload,
  CuestionarioResumen,
  CuestionarioPublico,
  DetalleCierre,
  DetalleIntento,
  ErrorApi,
  EstadisticaArea,
  EstadisticaPregunta,
  EstadoIntento,
  EstadoSalud,
  Estudio,
  EstudioPayload,
  FiltrosBitacora,
  FiltrosCatalogo,
  FiltrosEstadisticas,
  FiltrosIncidencias,
  IdentidadRespondiente,
  Incidencia,
  IntentoIniciado,
  InspeccionSqpPayload,
  InspeccionSqpResumen,
  Insumo,
  InsumoPayload,
  ListadoPciMtto,
  RegistroPciMtto,
  Recepcion,
  RecepcionPayload,
  RecepcionesPaginadas,
  ResultadoOcr,
  SesionQr,
  TipoDocumento,
  FiltrosRecepciones,
  EstadoSesionQr,
  InsumosPaginados,
  IntentosPaginados,
  Mantenimiento,
  Mensaje,
  MetaArea,
  Platica,
  PuntoRondin,
  PuntoRondinPayload,
  PuntoLineaTiempo,
  RangoDistribucion,
  RangoRayser,
  RegistroChecklist,
  RegistroRayser,
  Resumen,
  Tablero,
  TurnoRondin,
  PreguntaPayload,
  ResultadoImportacion,
  ResultadoImportacionInsumos,
  ResultadoIntento,
  Usuario,
  UsuarioActualizarPayload,
  UsuarioCrearPayload,
  ValorChecklist,
} from './types';

const EN_SERVIDOR = typeof window === 'undefined';

function baseUrl(): string {
  if (EN_SERVIDOR) {
    return `${process.env.API_INTERNAL_URL ?? 'http://backend:8000'}/api`;
  }
  return '/api';
}

/**
 * Lo que se le dice al operador cuando el servidor no contestó a tiempo.
 *
 * Menciona el historial a propósito: en las recepciones la foto se guarda
 * ANTES de procesarla, así que un tiempo agotado no significa que no haya
 * quedado nada. Reintentar a ciegas duplicaría el documento.
 */
const MENSAJE_TIEMPO_AGOTADO =
  'El servidor no respondió a tiempo. La foto puede haberse guardado; ' +
  'revisa el historial antes de reintentar.';

/** Error de la API con el mensaje en español ya extraído. */
export class ErrorDeApi extends Error {
  readonly status: number;
  readonly errores?: ErrorApi['errores'];

  constructor(status: number, mensaje: string, errores?: ErrorApi['errores']) {
    super(mensaje);
    this.name = 'ErrorDeApi';
    this.status = status;
    this.errores = errores;
  }
}

async function solicitar<T>(ruta: string, init?: RequestInit): Promise<T> {
  let respuesta: Response;

  try {
    respuesta = await fetch(`${baseUrl()}${ruta}`, {
      ...init,
      // Necesario para que viaje la cookie httpOnly de sesión del admin.
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        ...init?.headers,
      },
      cache: 'no-store',
    });
  } catch (error: unknown) {
    // fetch solo lanza por fallo de red o por aborto, no por códigos 4xx/5xx.
    // `AbortSignal.timeout` lanza un DOMException con el texto en inglés, que
    // no le dice nada al operador: se traduce y se le indica qué hacer.
    if (error instanceof DOMException && error.name === 'TimeoutError') {
      throw new ErrorDeApi(0, MENSAJE_TIEMPO_AGOTADO);
    }
    throw new ErrorDeApi(0, 'No se pudo conectar con el servidor. Revisa tu conexión.');
  }

  if (!respuesta.ok) {
    let mensaje = `Error ${respuesta.status} al comunicarse con el servidor.`;
    let errores: ErrorApi['errores'];

    try {
      const cuerpo = (await respuesta.json()) as ErrorApi;
      if (cuerpo.detail) {
        mensaje = cuerpo.detail;
      }
      errores = cuerpo.errores;
    } catch {
      // Respuesta sin cuerpo JSON (502 de Nginx, por ejemplo): se conserva
      // el mensaje genérico construido arriba.
    }

    throw new ErrorDeApi(respuesta.status, mensaje, errores);
  }

  if (respuesta.status === 204) {
    return undefined as T;
  }

  return (await respuesta.json()) as T;
}

export const api = {
  get: <T>(ruta: string, senal?: AbortSignal): Promise<T> =>
    solicitar<T>(ruta, { method: 'GET', signal: senal }),

  post: <T>(ruta: string, cuerpo?: unknown, senal?: AbortSignal): Promise<T> =>
    solicitar<T>(ruta, {
      method: 'POST',
      body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
      signal: senal,
    }),

  put: <T>(ruta: string, cuerpo?: unknown): Promise<T> =>
    solicitar<T>(ruta, {
      method: 'PUT',
      body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
    }),

  patch: <T>(ruta: string, cuerpo?: unknown): Promise<T> =>
    solicitar<T>(ruta, {
      method: 'PATCH',
      body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
    }),

  delete: <T>(ruta: string): Promise<T> => solicitar<T>(ruta, { method: 'DELETE' }),
};

// --- Endpoints concretos ---------------------------------------------------

export const obtenerSalud = (): Promise<EstadoSalud> => api.get<EstadoSalud>('/health');

export const obtenerAreas = (): Promise<Area[]> => api.get<Area[]>('/areas');

/**
 * Red WiFi configurada en el servidor, para el QR de acceso.
 *
 * Requiere sesión: la respuesta incluye la contraseña de la red.
 */
export const obtenerConfigWifi = (): Promise<ConfigWifi> =>
  api.get<ConfigWifi>('/wifi');

// --- Autenticación ---------------------------------------------------------

/** Inicia sesión. El JWT llega en una cookie httpOnly, no en el cuerpo. */
export const iniciarSesion = (credenciales: Credenciales): Promise<Admin> =>
  api.post<Admin>('/auth/login', credenciales);

export const cerrarSesion = (): Promise<Mensaje> => api.post<Mensaje>('/auth/logout');

/** Devuelve el admin de la sesión; lanza ErrorDeApi con status 401 si no hay. */
export const obtenerAdminActual = (): Promise<Admin> => api.get<Admin>('/auth/me');

// --- Cuestionarios ---------------------------------------------------------

export const listarCuestionarios = (): Promise<CuestionarioResumen[]> =>
  api.get<CuestionarioResumen[]>('/cuestionarios');

export const obtenerCuestionario = (id: string): Promise<Cuestionario> =>
  api.get<Cuestionario>(`/cuestionarios/${id}`);

export const crearCuestionario = (
  datos: CuestionarioCrearPayload,
): Promise<Cuestionario> => api.post<Cuestionario>('/cuestionarios', datos);

export const actualizarCuestionario = (
  id: string,
  datos: CuestionarioActualizarPayload,
): Promise<Cuestionario> => api.put<Cuestionario>(`/cuestionarios/${id}`, datos);

export const eliminarCuestionario = (id: string): Promise<void> =>
  api.delete<void>(`/cuestionarios/${id}`);

export const duplicarCuestionario = (id: string): Promise<Cuestionario> =>
  api.post<Cuestionario>(`/cuestionarios/${id}/duplicar`);

export const agregarPregunta = (
  cuestionarioId: string,
  datos: PreguntaPayload,
): Promise<Cuestionario> =>
  api.post<Cuestionario>(`/cuestionarios/${cuestionarioId}/preguntas`, datos);

/** Reordena en lote: espera la lista completa de preguntas con su nuevo orden. */
export const reordenarPreguntas = (
  cuestionarioId: string,
  preguntas: Array<{ id: string; orden: number }>,
): Promise<Cuestionario> =>
  api.put<Cuestionario>(`/cuestionarios/${cuestionarioId}/preguntas/orden`, {
    preguntas,
  });

// --- Estadísticas ----------------------------------------------------------

/** Convierte los filtros a query string, omitiendo los vacíos. */
function consulta(filtros: FiltrosEstadisticas, extra: Record<string, string> = {}): string {
  const parametros = new URLSearchParams({ cuestionario_id: filtros.cuestionario_id });

  if (filtros.area) parametros.set('area', filtros.area);
  if (filtros.desde) parametros.set('desde', filtros.desde);
  if (filtros.hasta) parametros.set('hasta', filtros.hasta);

  for (const [clave, valor] of Object.entries(extra)) {
    parametros.set(clave, valor);
  }

  return parametros.toString();
}

export const obtenerResumen = (filtros: FiltrosEstadisticas): Promise<Resumen> =>
  api.get<Resumen>(`/estadisticas/resumen?${consulta(filtros)}`);

export const obtenerPorArea = (filtros: FiltrosEstadisticas): Promise<EstadisticaArea[]> =>
  api.get<EstadisticaArea[]>(`/estadisticas/por-area?${consulta(filtros)}`);

export const obtenerPorPregunta = (
  filtros: FiltrosEstadisticas,
): Promise<EstadisticaPregunta[]> =>
  api.get<EstadisticaPregunta[]>(`/estadisticas/por-pregunta?${consulta(filtros)}`);

export const obtenerDistribucion = (
  filtros: FiltrosEstadisticas,
): Promise<RangoDistribucion[]> =>
  api.get<RangoDistribucion[]>(`/estadisticas/distribucion?${consulta(filtros)}`);

export const obtenerLineaTiempo = (
  filtros: FiltrosEstadisticas,
): Promise<PuntoLineaTiempo[]> =>
  api.get<PuntoLineaTiempo[]>(`/estadisticas/linea-tiempo?${consulta(filtros)}`);

export const obtenerIntentos = (
  filtros: FiltrosEstadisticas,
  opciones: {
    page: number;
    size: number;
    orden_por: string;
    descendente: boolean;
    /** Texto a buscar en el nombre o el número de empleado. */
    busqueda?: string;
  },
): Promise<IntentosPaginados> =>
  api.get<IntentosPaginados>(
    `/estadisticas/intentos?${consulta(filtros, {
      page: String(opciones.page),
      size: String(opciones.size),
      orden_por: opciones.orden_por,
      descendente: String(opciones.descendente),
      // Solo viaja si tiene contenido: un parámetro vacío ensucia la URL.
      ...(opciones.busqueda ? { busqueda: opciones.busqueda } : {}),
    })}`,
  );

/**
 * Descarga un archivo del servidor y dispara el guardado en el navegador.
 *
 * Devuelve el nombre con el que se guardó. Comparte la mecánica con
 * `descargarReporte`: pide con `fetch` para poder mostrar un error legible
 * en vez de navegar a una página con JSON crudo.
 */
async function descargarArchivo(ruta: string, nombrePorDefecto: string): Promise<void> {
  const respuesta = await fetch(`${baseUrl()}${ruta}`, {
    credentials: 'include',
    cache: 'no-store',
  }).catch(() => {
    throw new ErrorDeApi(0, 'No se pudo conectar con el servidor.');
  });

  if (!respuesta.ok) {
    let mensaje = 'No se pudo generar el archivo.';
    try {
      const error = (await respuesta.json()) as ErrorApi;
      if (error.detail) {
        mensaje = error.detail;
      }
    } catch {
      // Sin cuerpo JSON: se conserva el mensaje genérico.
    }
    throw new ErrorDeApi(respuesta.status, mensaje);
  }

  const disposicion = respuesta.headers.get('content-disposition') ?? '';
  const coincidencia = /filename="([^"]+)"/.exec(disposicion);
  const nombre = coincidencia?.[1] ?? nombrePorDefecto;

  const blob = await respuesta.blob();
  const url = URL.createObjectURL(blob);

  const enlace = document.createElement('a');
  enlace.href = url;
  enlace.download = nombre;
  document.body.appendChild(enlace);
  enlace.click();
  enlace.remove();

  URL.revokeObjectURL(url);
}

/**
 * Descarga el cuestionario en PDF para contestarlo en papel.
 *
 * Sale en blanco: no marca la respuesta correcta.
 */
export const descargarCuestionarioPdf = (id: string): Promise<void> =>
  descargarArchivo(`/cuestionarios/${id}/imprimir`, 'cuestionario.pdf');

/**
 * Descarga un reporte y dispara el guardado en el navegador.
 *
 * Se usa `fetch` en lugar de un enlace directo para poder mostrar un error
 * legible: con un `<a href>`, un fallo del servidor navegaría a una página
 * con JSON crudo y el usuario perdería el dashboard.
 */
export async function descargarReporte(
  formato: 'excel' | 'powerpoint',
  filtros: FiltrosEstadisticas,
): Promise<void> {
  const respuesta = await fetch(
    `${baseUrl()}/estadisticas/exportar/${formato}?${consulta(filtros)}`,
    { credentials: 'include', cache: 'no-store' },
  ).catch(() => {
    throw new ErrorDeApi(0, 'No se pudo conectar con el servidor.');
  });

  if (!respuesta.ok) {
    let mensaje = 'No se pudo generar el reporte.';
    try {
      const error = (await respuesta.json()) as ErrorApi;
      if (error.detail) {
        mensaje = error.detail;
      }
    } catch {
      // Sin cuerpo JSON: se conserva el mensaje genérico.
    }
    throw new ErrorDeApi(respuesta.status, mensaje);
  }

  // El nombre del archivo lo decide el servidor; se lee del encabezado.
  const disposicion = respuesta.headers.get('content-disposition') ?? '';
  const coincidencia = /filename="([^"]+)"/.exec(disposicion);
  const nombre = coincidencia?.[1] ?? `reporte.${formato === 'excel' ? 'xlsx' : 'pptx'}`;

  const blob = await respuesta.blob();
  const url = URL.createObjectURL(blob);

  const enlace = document.createElement('a');
  enlace.href = url;
  enlace.download = nombre;
  document.body.appendChild(enlace);
  enlace.click();
  enlace.remove();

  // Liberar el objeto: si no, el blob se queda en memoria hasta recargar.
  URL.revokeObjectURL(url);
}

/** Respuestas de un intento, con aciertos y errores por pregunta. */
export const obtenerDetalleIntento = (intentoId: string): Promise<DetalleIntento> =>
  api.get<DetalleIntento>(`/estadisticas/intentos/${intentoId}`);

export const obtenerMetas = (): Promise<MetaArea[]> => api.get<MetaArea[]>('/metas-area');

export const guardarMetas = (
  metas: Array<{ area: string; headcount: number }>,
): Promise<MetaArea[]> => api.put<MetaArea[]>('/metas-area', { metas });

// --- Importación desde Excel ----------------------------------------------

/**
 * Sube el archivo y devuelve el reporte de importación.
 *
 * No pasa por `solicitar()` porque `FormData` necesita que el navegador fije
 * el Content-Type con su propio boundary: forzar application/json rompería
 * la subida.
 */
export async function importarExcel(archivo: File): Promise<ResultadoImportacion> {
  const cuerpo = new FormData();
  cuerpo.append('archivo', archivo);

  let respuesta: Response;

  try {
    respuesta = await fetch(`${baseUrl()}/cuestionarios/importar-excel`, {
      method: 'POST',
      body: cuerpo,
      credentials: 'include',
      cache: 'no-store',
    });
  } catch {
    throw new ErrorDeApi(0, 'No se pudo conectar con el servidor.');
  }

  if (!respuesta.ok) {
    let mensaje = 'No se pudo importar el archivo.';
    try {
      const error = (await respuesta.json()) as ErrorApi;
      if (error.detail) {
        mensaje = error.detail;
      }
    } catch {
      // Respuesta sin JSON: se conserva el mensaje genérico.
    }
    throw new ErrorDeApi(respuesta.status, mensaje);
  }

  return (await respuesta.json()) as ResultadoImportacion;
}

/** URL de descarga de la plantilla. La cookie de sesión viaja sola. */
export const URL_PLANTILLA_EXCEL = '/api/cuestionarios/plantilla-excel';

// --- Formulario público (sin autenticación) --------------------------------

export const obtenerCuestionarioPublico = (token: string): Promise<CuestionarioPublico> =>
  api.get<CuestionarioPublico>(`/publico/${token}`);

export const iniciarIntento = (
  token: string,
  identidad: IdentidadRespondiente,
): Promise<IntentoIniciado> =>
  api.post<IntentoIniciado>(`/publico/${token}/intento`, identidad);

export const obtenerEstadoIntento = (intentoId: string): Promise<EstadoIntento> =>
  api.get<EstadoIntento>(`/publico/intento/${intentoId}`);

/** Autoguardado. La respuesta no revela si la opción elegida era correcta. */
export const guardarRespuesta = (
  intentoId: string,
  preguntaId: string,
  opcionId: string,
): Promise<{ pregunta_id: string; opcion_id: string; guardado: boolean }> =>
  api.patch(`/publico/intento/${intentoId}`, {
    pregunta_id: preguntaId,
    opcion_id: opcionId,
  });

export const finalizarIntento = (intentoId: string): Promise<ResultadoIntento> =>
  api.post<ResultadoIntento>(`/publico/intento/${intentoId}/finalizar`);

// --- Controles ESH ---------------------------------------------------------

export const obtenerRangoRayser = (): Promise<RangoRayser> =>
  api.get<RangoRayser>('/controles/rayser/rango');

export const listarRayser = (desde: string, hasta: string): Promise<RegistroRayser[]> =>
  api.get<RegistroRayser[]>(
    `/controles/rayser?${new URLSearchParams({ desde, hasta }).toString()}`,
  );

export const eliminarRegistroRayser = (id: string): Promise<void> =>
  api.delete<void>(`/controles/rayser/${id}`);

/**
 * URL de una foto de evidencia. La cookie de sesión viaja sola.
 *
 * Un solo endpoint para los tres controles: Rayser, las listas de verificación
 * y las pláticas.
 */
export const urlFotoControl = (id: string): string => `/api/controles/fotos/${id}`;

/**
 * Registra la lectura del día.
 *
 * No pasa por `solicitar()` porque el cuerpo es `FormData`: forzar
 * `Content-Type: application/json` rompería el multipart de la foto (mismo
 * motivo que en `importarExcel`).
 */
async function enviarFormulario<T>(
  ruta: string,
  cuerpo: FormData,
  senal?: AbortSignal,
  /** El cierre de hallazgo se actualiza con PUT; el resto crea con POST. */
  metodo: 'POST' | 'PUT' = 'POST',
): Promise<T> {
  let respuesta: Response;

  try {
    respuesta = await fetch(`${baseUrl()}${ruta}`, {
      method: metodo,
      body: cuerpo,
      credentials: 'include',
      cache: 'no-store',
      signal: senal,
    });
  } catch (error: unknown) {
    if (error instanceof DOMException && error.name === 'TimeoutError') {
      throw new ErrorDeApi(0, MENSAJE_TIEMPO_AGOTADO);
    }
    throw new ErrorDeApi(0, 'No se pudo conectar con el servidor.');
  }

  if (!respuesta.ok) {
    let mensaje = 'No se pudo guardar el registro.';
    let errores: ErrorApi['errores'];

    try {
      const error = (await respuesta.json()) as ErrorApi;
      if (error.detail) {
        mensaje = error.detail;
      }
      errores = error.errores;
    } catch {
      // Sin cuerpo JSON: se conserva el mensaje genérico.
    }

    throw new ErrorDeApi(respuesta.status, mensaje, errores);
  }

  return (await respuesta.json()) as T;
}

export function registrarRayser(datos: {
  fecha: string;
  lecturas: string[];
  observaciones: string;
  fotos: File[];
}): Promise<RegistroRayser> {
  const cuerpo = new FormData();
  cuerpo.append('fecha', datos.fecha);
  datos.lecturas.forEach((lectura, indice) => {
    cuerpo.append(`manometro_${indice + 1}`, lectura);
  });
  cuerpo.append('observaciones', datos.observaciones);
  datos.fotos.forEach((foto) => cuerpo.append('fotos', foto));

  return enviarFormulario<RegistroRayser>('/controles/rayser', cuerpo);
}

export const descargarExcelRayser = (desde: string, hasta: string): Promise<void> =>
  descargarArchivo(
    `/controles/rayser/exportar/excel?${new URLSearchParams({ desde, hasta }).toString()}`,
    'rayser.xlsx',
  );

export const obtenerCatalogoSqp = (): Promise<CatalogoSqp> =>
  api.get<CatalogoSqp>('/controles/sqp/catalogo');

export const listarInspeccionesSqp = (): Promise<InspeccionSqpResumen[]> =>
  api.get<InspeccionSqpResumen[]>('/controles/sqp');

/**
 * Guarda una inspección de SQP con la evidencia de sus puntos inconformes.
 *
 * Va como `multipart` y no como JSON porque ahora lleva fotos, igual que las
 * listas de verificación: el JSON viaja en `datos` y las imágenes en campos
 * `fotos_{orden}`.
 */
export function registrarInspeccionSqp(
  datos: InspeccionSqpPayload,
  fotos: Record<number, File[]> = {},
): Promise<InspeccionSqpResumen> {
  const cuerpo = new FormData();
  cuerpo.append('datos', JSON.stringify(datos));

  for (const [orden, archivos] of Object.entries(fotos)) {
    archivos.forEach((foto) => cuerpo.append(`fotos_${orden}`, foto));
  }

  return enviarFormulario<InspeccionSqpResumen>('/controles/sqp', cuerpo);
}

export const descargarExcelSqp = (id: string): Promise<void> =>
  descargarArchivo(`/controles/sqp/${id}/exportar/excel`, 'inspeccion_sqp.xlsx');

// --- Controles de lista de verificación (OK / NO OK) -----------------------

export const obtenerCatalogoChecklist = (control: string): Promise<CatalogoChecklist> =>
  api.get<CatalogoChecklist>(`/controles/checklist/${control}/catalogo`);

export const listarChecklist = (
  control: string,
  desde: string,
  hasta: string,
): Promise<RegistroChecklist[]> =>
  api.get<RegistroChecklist[]>(
    `/controles/checklist/${control}?${new URLSearchParams({ desde, hasta }).toString()}`,
  );

/**
 * Registra el recorrido del día.
 *
 * La parte estructurada viaja como JSON en un campo del multipart y las fotos
 * en campos `fotos_{orden}`, uno por punto: así el registro y sus evidencias
 * se guardan en una sola petición, sin quedar a medias si se cae la red.
 */
export function registrarChecklist(
  control: string,
  datos: {
    fecha: string;
    puntos: Array<{
      orden: number;
      valor: ValorChecklist;
      observaciones: string;
      /** Lectura del punto; solo la piden los puntos con `medicion`. */
      medicion?: string;
    }>;
    fotos: Record<number, File[]>;
    /** Encabezado del formato. Vacío en los controles de rejilla. */
    encabezado: Record<string, string>;
    /** Bloques del pie del formato, por clave de sección. */
    secciones: Record<string, Record<string, string>>;
  },
): Promise<RegistroChecklist> {
  const cuerpo = new FormData();
  cuerpo.append('fecha', datos.fecha);
  cuerpo.append(
    'puntos',
    JSON.stringify(
      datos.puntos.map((punto) => ({
        orden: punto.orden,
        valor: punto.valor,
        observaciones: punto.observaciones || null,
        medicion: punto.medicion || null,
      })),
    ),
  );

  // Los formatos por inspección (silos, tableros) viven de estos dos campos:
  // sin ellos el servidor recibe el encabezado vacío y responde 422
  // ("Planta: falta capturarlo") aunque la pantalla se vea llena.
  cuerpo.append('encabezado', JSON.stringify(datos.encabezado));
  cuerpo.append('secciones', JSON.stringify(datos.secciones));

  for (const [orden, fotos] of Object.entries(datos.fotos)) {
    fotos.forEach((foto) => cuerpo.append(`fotos_${orden}`, foto));
  }

  return enviarFormulario<RegistroChecklist>(`/controles/checklist/${control}`, cuerpo);
}

/** Excel de una inspección suelta, con el formato de su hoja. */
export const descargarExcelInspeccion = (
  control: string,
  id: string,
): Promise<void> =>
  descargarArchivo(
    `/controles/checklist/${control}/${id}/exportar/excel`,
    `${control}.xlsx`,
  );

export const eliminarRegistroChecklist = (
  control: string,
  id: string,
): Promise<void> => api.delete<void>(`/controles/checklist/${control}/${id}`);

export const descargarExcelChecklist = (
  control: string,
  desde: string,
  hasta: string,
): Promise<void> =>
  descargarArchivo(
    `/controles/checklist/${control}/exportar/excel?${new URLSearchParams({
      desde,
      hasta,
    }).toString()}`,
    `${control}.xlsx`,
  );

// --- Pláticas diarias de seguridad -----------------------------------------

export const obtenerAreasPlaticas = (): Promise<AreaPlatica[]> =>
  api.get<AreaPlatica[]>('/controles/platicas/areas');

export const listarPlaticas = (desde: string, hasta: string): Promise<Platica[]> =>
  api.get<Platica[]>(
    `/controles/platicas?${new URLSearchParams({ desde, hasta }).toString()}`,
  );

export function registrarPlatica(datos: {
  fecha: string;
  tema: string;
  areas: string[];
  fotos: File[];
}): Promise<Platica> {
  const cuerpo = new FormData();
  cuerpo.append('fecha', datos.fecha);
  cuerpo.append('tema', datos.tema);
  cuerpo.append('areas', JSON.stringify(datos.areas));
  datos.fotos.forEach((foto) => cuerpo.append('fotos', foto));

  return enviarFormulario<Platica>('/controles/platicas', cuerpo);
}

export const eliminarPlatica = (id: string): Promise<void> =>
  api.delete<void>(`/controles/platicas/${id}`);

export const descargarExcelPlaticas = (desde: string, hasta: string): Promise<void> =>
  descargarArchivo(
    `/controles/platicas/exportar/excel?${new URLSearchParams({ desde, hasta }).toString()}`,
    'platicas_esh.xlsx',
  );

// --- Administración: usuarios ----------------------------------------------

export const listarUsuarios = (): Promise<Usuario[]> =>
  api.get<Usuario[]>('/administracion/usuarios');

export const crearUsuario = (datos: UsuarioCrearPayload): Promise<Usuario> =>
  api.post<Usuario>('/administracion/usuarios', datos);

export const actualizarUsuario = (
  id: string,
  datos: UsuarioActualizarPayload,
): Promise<Usuario> => api.put<Usuario>(`/administracion/usuarios/${id}`, datos);

export const cambiarEstadoUsuario = (id: string, activo: boolean): Promise<Usuario> =>
  api.patch<Usuario>(`/administracion/usuarios/${id}/activo`, { activo });

export const eliminarUsuario = (id: string): Promise<void> =>
  api.delete<void>(`/administracion/usuarios/${id}`);

// --- Administración: bitácora ----------------------------------------------

/** Arma la query de la bitácora omitiendo los filtros vacíos. */
function consultaBitacora(filtros: FiltrosBitacora, pagina: number): string {
  const parametros = new URLSearchParams({ page: String(pagina) });

  if (filtros.fecha) parametros.set('fecha', filtros.fecha);
  if (filtros.hora_desde) parametros.set('hora_desde', filtros.hora_desde);
  if (filtros.hora_hasta) parametros.set('hora_hasta', filtros.hora_hasta);
  if (filtros.usuario) parametros.set('usuario', filtros.usuario);

  return parametros.toString();
}

export const listarBitacora = (
  filtros: FiltrosBitacora,
  pagina = 1,
): Promise<BitacoraPaginada> =>
  api.get<BitacoraPaginada>(`/administracion/bitacora?${consultaBitacora(filtros, pagina)}`);

/** Usuarios con actividad registrada, incluidos los ya eliminados. */
export const listarUsuariosBitacora = (): Promise<string[]> =>
  api.get<string[]>('/administracion/bitacora/usuarios');

// --- Administración: mantenimiento -----------------------------------------

export const obtenerMantenimiento = (): Promise<Mantenimiento> =>
  api.get<Mantenimiento>('/administracion/mantenimiento');

// --- Estudios y capacitaciones ---------------------------------------------

export const obtenerCatalogoEstudios = (): Promise<CatalogoEstudios> =>
  api.get<CatalogoEstudios>('/estudios/catalogo');

export const listarEstudios = (): Promise<Estudio[]> => api.get<Estudio[]>('/estudios');

export const crearEstudio = (datos: EstudioPayload): Promise<Estudio> =>
  api.post<Estudio>('/estudios', datos);

export const actualizarEstudio = (id: string, datos: EstudioPayload): Promise<Estudio> =>
  api.put<Estudio>(`/estudios/${id}`, datos);

export const eliminarEstudio = (id: string): Promise<void> =>
  api.delete<void>(`/estudios/${id}`);

/** Estudios que vencen dentro de un mes y los que ya vencieron. */
export const obtenerAvisos = (): Promise<Avisos> => api.get<Avisos>('/estudios/avisos');

export const descargarExcelEstudios = (): Promise<void> =>
  descargarArchivo('/estudios/exportar/excel', 'estudios.xlsx');
// --- Catálogo de insumos ---------------------------------------------------

/** Arma la query del catálogo omitiendo los filtros vacíos. */
function consultaCatalogo(filtros: FiltrosCatalogo, pagina: number): string {
  const parametros = new URLSearchParams({ page: String(pagina) });

  if (filtros.busqueda) parametros.set('busqueda', filtros.busqueda);
  if (filtros.categoria) parametros.set('categoria', filtros.categoria);
  if (filtros.estado) parametros.set('estado', filtros.estado);

  return parametros.toString();
}

export const listarInsumos = (
  filtros: FiltrosCatalogo,
  pagina = 1,
): Promise<InsumosPaginados> =>
  api.get<InsumosPaginados>(`/catalogo?${consultaCatalogo(filtros, pagina)}`);

/** Categorías válidas; nunca se escriben a mano en el frontend. */
export const obtenerCategoriasInsumo = (): Promise<string[]> =>
  api
    .get<{ categorias: string[] }>('/catalogo/categorias')
    .then((datos) => datos.categorias);

/** Unidades de medida válidas; mismo patrón que las categorías. */
export const obtenerUnidadesInsumo = (): Promise<string[]> =>
  api
    .get<{ unidades: string[] }>('/catalogo/unidades')
    .then((datos) => datos.unidades);

export const crearInsumo = (datos: InsumoPayload): Promise<Insumo> =>
  api.post<Insumo>('/catalogo', datos);

export const actualizarInsumo = (id: string, datos: InsumoPayload): Promise<Insumo> =>
  api.put<Insumo>(`/catalogo/${id}`, datos);

export const eliminarInsumo = (id: string): Promise<void> =>
  api.delete<void>(`/catalogo/${id}`);

/**
 * Carga masiva del catálogo.
 *
 * Va por `enviarFormulario` y no por `solicitar`: forzar
 * `Content-Type: application/json` rompería el multipart.
 */
export function importarCatalogoExcel(
  archivo: File,
): Promise<ResultadoImportacionInsumos> {
  const cuerpo = new FormData();
  cuerpo.append('archivo', archivo);
  return enviarFormulario<ResultadoImportacionInsumos>('/catalogo/importar-excel', cuerpo);
}

/** La cookie httpOnly viaja sola, así que basta un <a download>. */
export const URL_PLANTILLA_CATALOGO = '/api/catalogo/plantilla-excel';

// --- Rondines de seguridad -------------------------------------------------

export const obtenerTablero = (fecha: string, turno: TurnoRondin): Promise<Tablero> =>
  api.get<Tablero>(
    `/rondines/tablero?${new URLSearchParams({ fecha, turno }).toString()}`,
  );

export const listarPuntosRondin = (): Promise<PuntoRondin[]> =>
  api.get<PuntoRondin[]>('/rondines/puntos');

export const crearPuntoRondin = (datos: PuntoRondinPayload): Promise<PuntoRondin> =>
  api.post<PuntoRondin>('/rondines/puntos', datos);

export const actualizarPuntoRondin = (
  id: string,
  datos: PuntoRondinPayload,
): Promise<PuntoRondin> => api.put<PuntoRondin>(`/rondines/puntos/${id}`, datos);

export const eliminarPuntoRondin = (id: string): Promise<void> =>
  api.delete<void>(`/rondines/puntos/${id}`);

export const descargarExcelRondines = (
  fecha: string,
  turno: TurnoRondin,
): Promise<void> =>
  descargarArchivo(
    `/rondines/exportar/excel?${new URLSearchParams({ fecha, turno }).toString()}`,
    `rondines_${fecha}_${turno}.xlsx`,
  );

export const enviarReporteRondines = (
  fecha: string,
  turno: TurnoRondin,
  destinatario: string,
): Promise<Mensaje> =>
  api.post<Mensaje>('/rondines/reporte/enviar', { fecha, turno, destinatario });

/** La cookie httpOnly viaja sola, así que basta un <a download>. */
/**
 * Hoja imprimible con los códigos QR de los puntos activos.
 *
 * Va por `descargarArchivo` y no por un `<a download>`: el endpoint responde
 * 422 cuando no hay puntos activos, y un ancla guardaría el JSON del error
 * como si fuera el PDF.
 */
export const descargarQrPuntos = (): Promise<void> =>
  descargarArchivo('/rondines/puntos/imprimir', 'qr_puntos_rondin.pdf');

/**
 * Registra el escaneo de un punto. NO lleva sesión: la llama la página que
 * abre el código QR pegado en la planta.
 */
export const escanearPunto = (token: string): Promise<EscaneoRegistrado> =>
  api.post<EscaneoRegistrado>(`/publico/rondin/${token}`);

// --- Recepciones de mercancía ----------------------------------------------

/** Arma la query del historial omitiendo los filtros vacíos. */
function consultaRecepciones(filtros: FiltrosRecepciones, pagina: number): string {
  const parametros = new URLSearchParams({ page: String(pagina) });

  if (filtros.busqueda) parametros.set('busqueda', filtros.busqueda);
  if (filtros.tipo_documento) parametros.set('tipo_documento', filtros.tipo_documento);

  return parametros.toString();
}

export const listarRecepciones = (
  filtros: FiltrosRecepciones,
  pagina = 1,
  senal?: AbortSignal,
): Promise<RecepcionesPaginadas> =>
  api.get<RecepcionesPaginadas>(
    `/inventario/recepciones?${consultaRecepciones(filtros, pagina)}`,
    senal,
  );

export const obtenerRecepcion = (id: string): Promise<Recepcion> =>
  api.get<Recepcion>(`/inventario/recepciones/${id}`);

/** Formatos registrados, para el filtro del historial. */
export const obtenerTiposDocumento = (): Promise<TipoDocumento[]> =>
  api.get<TipoDocumento[]>('/inventario/recepciones/tipos-documento');

export const guardarRecepcion = (datos: RecepcionPayload): Promise<Recepcion> =>
  api.post<Recepcion>('/inventario/recepciones', datos);

/**
 * Sube la foto y corre la extracción.
 *
 * El techo del backend son 100 s; aquí se espera un poco más para que sea
 * SIEMPRE el backend quien corte. Si cortara el navegador primero, se perdería
 * la respuesta con `ocr_ok:false` que habilita la captura manual, y el
 * operador vería un error genérico con la foto ya guardada sin saberlo.
 */
export function procesarFotoRecepcion(archivo: File): Promise<ResultadoOcr> {
  const cuerpo = new FormData();
  cuerpo.append('archivo', archivo);
  return enviarFormulario<ResultadoOcr>(
    '/inventario/recepciones/ocr',
    cuerpo,
    AbortSignal.timeout(115_000),
  );
}

/** Corre la extracción sobre la foto que mandó el celular. */
export const procesarFotoDeSesion = (sesionId: string): Promise<ResultadoOcr> =>
  api.post<ResultadoOcr>(
    `/inventario/recepciones/ocr/desde-sesion/${sesionId}`,
    undefined,
    AbortSignal.timeout(115_000),
  );

export const crearSesionQr = (): Promise<SesionQr> =>
  api.post<SesionQr>('/inventario/recepciones/qr-session');

/**
 * Estado de la sesión, para el sondeo de la PC.
 *
 * Es público: no lleva sesión y por eso se llama con `fetch` directo. Un 409
 * significa que la sesión venció o ya se usó, no un fallo de red.
 */
export async function estadoSesionQr(sesionId: string): Promise<EstadoSesionQr> {
  const respuesta = await fetch(`/api/publico/recepcion/${sesionId}`, {
    cache: 'no-store',
  });

  if (!respuesta.ok) {
    throw new ErrorDeApi(respuesta.status, 'La sesión de captura ya no está disponible.');
  }

  const datos = (await respuesta.json()) as { estado: EstadoSesionQr };
  return datos.estado;
}

/**
 * Sube la foto desde el celular. La llama la página pública `/re/[sesion]`.
 *
 * No pasa por `enviarFormulario` porque esa ruta manda la cookie de sesión y
 * aquí no hay ninguna: el celular nunca inició sesión en el panel.
 */
export async function subirFotoSesion(sesionId: string, archivo: File): Promise<void> {
  const cuerpo = new FormData();
  cuerpo.append('archivo', archivo);

  const respuesta = await fetch(`/api/publico/recepcion/${sesionId}/foto`, {
    method: 'POST',
    body: cuerpo,
  });

  if (!respuesta.ok) {
    let mensaje = 'No se pudo enviar la foto.';
    try {
      const datos = (await respuesta.json()) as ErrorApi;
      if (datos.detail) mensaje = datos.detail;
    } catch {
      // Cuerpo no-JSON: se queda el mensaje genérico.
    }
    throw new ErrorDeApi(respuesta.status, mensaje);
  }
}

/** La foto de una recepción. La cookie httpOnly viaja sola. */
export const urlFotoRecepcion = (fotoId: string): string =>
  `/api/inventario/recepciones/foto/${fotoId}`;

// --- Cierre de hallazgos e incidencias -------------------------------------

/** Los hallazgos de una hoja y su cierre, si ya lo tiene. */
export const obtenerCierre = (
  control: string,
  registroId: string,
): Promise<DetalleCierre> =>
  api.get<DetalleCierre>(`/controles/cierres/${control}/${registroId}`);

/**
 * Guarda el cierre de los hallazgos de una hoja.
 *
 * `POST` da de alta y `PUT` actualiza: son rutas distintas porque solo la
 * segunda exige permiso de edición, así que un alta no puede sobrescribir un
 * cierre ajeno. Al actualizar, las fotos solo se mandan si el operador eligió
 * nuevas; si no, el servidor conserva las que ya estaban.
 */
export function guardarCierre(
  control: string,
  registroId: string,
  datos: CierrePayload,
  fotos: File[],
  actualizando: boolean,
): Promise<CierreHallazgo> {
  const cuerpo = new FormData();
  cuerpo.append('datos', JSON.stringify(datos));
  fotos.forEach((foto) => cuerpo.append('fotos', foto));

  return enviarFormulario<CierreHallazgo>(
    `/controles/cierres/${control}/${registroId}`,
    cuerpo,
    undefined,
    actualizando ? 'PUT' : 'POST',
  );
}

function queryIncidencias(filtros: FiltrosIncidencias): string {
  const parametros = new URLSearchParams({
    desde: filtros.desde,
    hasta: filtros.hasta,
  });

  if (filtros.control) {
    parametros.set('control', filtros.control);
  }
  if (filtros.estado) {
    parametros.set('estado', filtros.estado);
  }

  return parametros.toString();
}

/** Todo lo que salió mal en el periodo, de todos los controles juntos. */
export const listarIncidencias = (
  filtros: FiltrosIncidencias,
  senal?: AbortSignal,
): Promise<Incidencia[]> =>
  api.get<Incidencia[]>(`/controles/incidencias?${queryIncidencias(filtros)}`, senal);

/** El Excel de lo que los filtros dejen a la vista. */
export const descargarExcelIncidencias = (
  filtros: FiltrosIncidencias,
): Promise<void> =>
  descargarArchivo(
    `/controles/incidencias/exportar/excel?${queryIncidencias(filtros)}`,
    'incidencias.xlsx',
  );

// ---------------------------------------------------------------------------
// PCI MTTO: mantenimiento del sistema contra incendios
// ---------------------------------------------------------------------------

/**
 * Los registros del año, los años disponibles y los meses sin explicar.
 *
 * Todo en una sola petición: abrir la pestaña necesita las tres cosas a la vez
 * y tres llamadas en cascada se notan en la laptop de planta.
 */
export const listarPciMtto = (anio: number): Promise<ListadoPciMtto> =>
  api.get<ListadoPciMtto>(`/controles/pci-mtto?anio=${anio}`);

/** Los meses sin justificar, para la campana del encabezado. */
export const obtenerAvisosPciMtto = (): Promise<AvisosPciMtto> =>
  api.get<AvisosPciMtto>('/controles/pci-mtto/avisos');

/** Arma el multipart del formulario: los campos, las fotos y el documento. */
function cuerpoPciMtto(datos: CapturaPciMtto): FormData {
  const cuerpo = new FormData();
  cuerpo.append('realizado', String(datos.realizado));
  cuerpo.append('motivo', datos.motivo);

  if (datos.realizado) {
    cuerpo.append('fecha', datos.fecha);
  }

  datos.fotos.forEach((foto) => cuerpo.append('fotos', foto));

  if (datos.reporte !== null) {
    cuerpo.append('reporte', datos.reporte);
  }

  return cuerpo;
}

/** Da de alta el mes. Va por `enviarFormulario` porque lleva archivos. */
export function registrarPciMtto(
  datos: CapturaPciMtto,
): Promise<RegistroPciMtto> {
  const cuerpo = cuerpoPciMtto(datos);
  cuerpo.append('anio', String(datos.anio));
  cuerpo.append('mes', String(datos.mes));
  return enviarFormulario<RegistroPciMtto>('/controles/pci-mtto', cuerpo);
}

/**
 * Corrige un mes ya registrado. Es la única forma de arreglarlo: no hay
 * borrado, porque borrar un cierre automático solo consigue que la vigilancia
 * lo vuelva a levantar con el motivo otra vez en blanco.
 *
 * `conservaReporte` deja el documento que ya estaba cuando la corrección no
 * adjunta uno nuevo: si no, cambiar una fecha obligaría a volver a subir el PDF.
 */
export function corregirPciMtto(
  datos: CapturaPciMtto,
  conservaReporte: boolean,
): Promise<RegistroPciMtto> {
  const cuerpo = cuerpoPciMtto(datos);
  cuerpo.append('conserva_reporte', String(conservaReporte));
  return enviarFormulario<RegistroPciMtto>(
    `/controles/pci-mtto/${datos.anio}/${datos.mes}`,
    cuerpo,
    undefined,
    'PUT',
  );
}

/**
 * Explica un mes que cerró sin mantenimiento.
 *
 * Con `actualizando` va por PUT, que exige permiso de edición porque pisa el
 * texto de otra persona; el POST solo rellena un hueco vacío y lo puede hacer
 * quien opera el control.
 */
export const guardarMotivoPciMtto = (
  anio: number,
  mes: number,
  motivo: string,
  actualizando: boolean,
): Promise<RegistroPciMtto> => {
  const ruta = `/controles/pci-mtto/${anio}/${mes}/motivo`;
  return actualizando
    ? api.put<RegistroPciMtto>(ruta, { motivo })
    : api.post<RegistroPciMtto>(ruta, { motivo });
};

/** URL del reporte adjunto. La cookie de sesión viaja sola. */
export const urlReportePciMtto = (anio: number, mes: number): string =>
  `/api/controles/pci-mtto/${anio}/${mes}/reporte`;

/** Baja el documento con el nombre que tenía al subirse. */
export const descargarReportePciMtto = (
  anio: number,
  mes: number,
): Promise<void> =>
  descargarArchivo(
    `/controles/pci-mtto/${anio}/${mes}/reporte`,
    `reporte_${anio}_${String(mes).padStart(2, '0')}`,
  );

/** El año completo en Excel: la tabla y las evidencias. */
export const descargarExcelPciMtto = (anio: number): Promise<void> =>
  descargarArchivo(
    `/controles/pci-mtto/exportar/excel?anio=${anio}`,
    `pci_mtto_${anio}.xlsx`,
  );
