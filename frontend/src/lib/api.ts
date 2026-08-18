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
  ConfigWifi,
  Credenciales,
  Cuestionario,
  CuestionarioActualizarPayload,
  CuestionarioCrearPayload,
  CuestionarioResumen,
  CuestionarioPublico,
  DetalleIntento,
  ErrorApi,
  EstadisticaArea,
  EstadisticaPregunta,
  EstadoIntento,
  EstadoSalud,
  FiltrosEstadisticas,
  IdentidadRespondiente,
  IntentoIniciado,
  IntentosPaginados,
  Mensaje,
  MetaArea,
  PuntoLineaTiempo,
  RangoDistribucion,
  Resumen,
  PreguntaPayload,
  ResultadoImportacion,
  ResultadoIntento,
} from './types';

const EN_SERVIDOR = typeof window === 'undefined';

function baseUrl(): string {
  if (EN_SERVIDOR) {
    return `${process.env.API_INTERNAL_URL ?? 'http://backend:8000'}/api`;
  }
  return '/api';
}

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
  } catch {
    // fetch solo lanza por fallo de red, no por códigos 4xx/5xx.
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
  get: <T>(ruta: string): Promise<T> => solicitar<T>(ruta, { method: 'GET' }),

  post: <T>(ruta: string, cuerpo?: unknown): Promise<T> =>
    solicitar<T>(ruta, {
      method: 'POST',
      body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
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
