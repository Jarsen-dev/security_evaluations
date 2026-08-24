/**
 * Diccionario base del panel. Los otros idiomas se tipan contra este, así que
 * agregar una clave aquí obliga a traducirla en `en.ts` y `ko.ts`.
 *
 * Convención: una sección por módulo de la interfaz. Los textos con datos
 * llevan marcadores `{nombre}` que resuelve `t()`.
 */
export const es = {
  comun: {
    guardar: 'Guardar',
    guardando: 'Guardando…',
    cancelar: 'Cancelar',
    cerrar: 'Cerrar',
    eliminar: 'Eliminar',
    eliminando: 'Eliminando…',
    editar: 'Editar',
    duplicar: 'Duplicar',
    descargar: 'Descargar',
    descargando: 'Descargando…',
    cargando: 'Cargando…',
    reintentar: 'Reintentar',
    buscar: 'Buscar',
    area: 'Área',
    areaTodas: 'Todas las áreas',
    fecha: 'Fecha',
    desde: 'Desde',
    hasta: 'Hasta',
    observaciones: 'Observaciones',
    responsable: 'Responsable',
    acciones: 'Acciones',
    sinDatos: 'Todavía no hay información que mostrar.',
    errorGenerico: 'Ocurrió un error. Intenta de nuevo.',
    obligatorio: 'Este campo es obligatorio.',
    mes: 'Mes',
    descargarExcel: 'Descargar en Excel',
    si: 'Sí',
    no: 'No',
  },

  encabezado: {
    titulo: 'Sistema ESH',
    secciones: 'Secciones del panel',
    cuestionarios: 'Cuestionarios',
    controles: 'Controles',
    inventario: 'Inventario',
    salir: 'Salir',
    idioma: 'Idioma',
    cambiarIdioma: 'Cambiar el idioma del panel',
  },

  login: {
    titulo: 'Sistema ESH',
    subtitulo: 'Acceso al panel de administración',
    usuario: 'Usuario',
    contrasena: 'Contraseña',
    entrar: 'Entrar',
    verificando: 'Verificando…',
    faltaUsuario: 'Escribe tu usuario.',
    faltaContrasena: 'Escribe tu contraseña.',
    fallo: 'No se pudo iniciar sesión. Intenta de nuevo.',
    nota:
      'El personal que contesta cuestionarios no necesita cuenta: accede por la ' +
      'liga o el código QR.',
  },

  controles: {
    titulo: 'Controles',
    descripcion:
      'Formatos de inspección del departamento de seguridad. Cada pestaña ' +
      'corresponde a un control del recorrido diario.',
    pestanas: 'Controles disponibles',
    sqp: 'Inspección de SQP',
    almacenRp: "Almacén de RP's",
    rayser: 'Rayser',
    platicas: 'Pláticas ESH',
    recorridos: 'Recorridos perimetrales',
    muro: 'Revisión de muro',
    medicamento: 'Control de medicamento',
    silos: 'Silos EPS',
    tableros: 'Tableros eléctricos',
    enConstruccion: 'En construcción',
    enConstruccionDetalle:
      'Este control todavía se lleva en papel. Se habilitará aquí en cuanto se ' +
      'definan sus reglas de captura.',
  },

  rayser: {
    titulo: 'Control de presiones de Rayser',
    descripcion:
      'Registro diario de los cuatro manómetros. La presión normal es de ' +
      '{normal} psi.',
    manometro: 'Manómetro {numero}',
    placeholderLectura: 'psi',
    terminarRegistro: 'Terminar registro',
    registroDelDia: 'Registro del día',
    yaRegistrado: 'La lectura del {fecha} ya está registrada.',
    eliminarRegistro: 'Eliminar el registro para capturarlo de nuevo',
    guardado: 'Registro guardado.',
    eliminado: 'Registro eliminado. Ya puedes capturarlo de nuevo.',
    rangoNormal: 'Normal: {minimo} a {maximo} psi',
    semaforo: {
      verde: 'Normal',
      rojo: 'Bajo',
      naranja: 'Alto',
    },
    evidenciaTitulo: 'Evidencia obligatoria',
    evidenciaDetalle:
      'Una o más lecturas salieron del rango normal: agrega la foto y anota qué ' +
      'ocurrió.',
    observacionesPlaceholder: '¿Qué se observó y qué se hizo?',
    faltaObservaciones: 'Anota las observaciones de la lectura fuera de rango.',
    faltaFoto: 'Agrega la foto de evidencia.',
    faltanLecturas: 'Captura las cuatro lecturas.',
    historial: 'Registros',
    evidencia: 'Evidencia',
    verEvidencia: 'Ver la evidencia',
    historialVacio: 'Todavía no hay registros en este periodo.',
    confirmarEliminar: '¿Eliminar el registro del {fecha}?',
    confirmarEliminarDetalle:
      'Se borra la lectura y su evidencia. Después podrás capturar el día otra vez.',
  },

  sqp: {
    titulo: 'Inspección de sustancias químicas peligrosas',
    descripcion:
      'Contesta los {total} puntos del formato. Un punto en NO necesita ' +
      'observaciones.',
    encargado: 'Encargado',
    encargadoPlaceholder: 'Nombre de quien atiende el área',
    cargo: 'Cargo',
    cargoPlaceholder: 'Puesto del encargado',
    respuestaSi: 'SI',
    respuestaNo: 'NO',
    respuestaNa: 'N/A',
    observacionesPlaceholder: '¿Qué se encontró?',
    sustancias: 'SQP del área',
    sustanciasAyuda: 'Escribe una sustancia por renglón.',
    sustanciasContador: '{total} sustancias capturadas',
    guardarInspeccion: 'Guardar inspección',
    faltanPuntos: 'Faltan {total} puntos por contestar.',
    faltanObservaciones: 'Hay {total} puntos en NO sin observaciones.',
    faltanSustancias: 'Captura al menos una sustancia del área.',
    guardada: 'Inspección guardada.',
    historial: 'Inspecciones registradas',
    historialVacio: 'Todavía no hay inspecciones registradas.',
    hallazgos: 'Hallazgos',
    hallazgosDetalle: '{total} en NO',
    descargarExcel: 'Descargar en Excel',
    progreso: '{contestados} de {total} contestados',
  },

  cuestionarios: {
    pestanas: 'Vistas de cuestionarios',
    pestanaCuestionarios: 'Cuestionarios',
    pestanaEstadisticas: 'Estadísticas',
    nombre: 'Nombre',
    numeroEmpleado: 'Número de empleado',
    camposFijos: 'Campos fijos — siempre se solicitan',
    opcionesArea: '{total} opciones',
    activo: 'Activo',
    inactivo: 'Inactivo',
    activar: 'Activar',
    desactivar: 'Desactivar',
    preguntas: 'Preguntas',
    respuestas: 'Respuestas',
    liga: 'Liga escritorio',
    ligaAyuda: 'Copia la liga para abrirla desde una PC',
    imprimir: 'Imprimir',
    imprimirAyuda: 'Descarga el PDF para contestarlo en papel',
    sinPreguntasImprimir: 'El cuestionario no tiene preguntas que imprimir',
    masAcciones: 'Más acciones para {nombre}',
    vacio: 'Todavía no hay cuestionarios.',
    vacioAyuda: 'Crea el primero con el botón “Nuevo cuestionario”.',
    creado: 'Cuestionario creado.',
    cambiosGuardados: 'Cambios guardados.',
    duplicado: 'Cuestionario duplicado. La copia queda inactiva.',
    activado: 'Cuestionario activado.',
    desactivado:
      'Cuestionario desactivado. La liga pública deja de aceptar respuestas.',
    eliminado: 'Cuestionario eliminado.',
    pdfDescargado: 'PDF descargado. Ábrelo para elegir la impresora.',
    falloCarga: 'No se pudieron cargar los cuestionarios.',
    falloDuplicar: 'No se pudo duplicar.',
    falloEstado: 'No se pudo cambiar el estado.',
    falloEliminar: 'No se pudo eliminar.',
    falloPdf: 'No se pudo generar el PDF.',
    confirmarEliminar: 'Eliminar cuestionario',
    confirmarEliminarDetalle:
      'Se eliminará “{nombre}” junto con sus {preguntas} pregunta(s) y ' +
      '{respuestas} respuesta(s). Esta acción no se puede deshacer.',
  },

  modalCuestionario: {
    nuevo: 'Nuevo cuestionario',
    editar: 'Editar cuestionario',
    paso1: 'Paso 1 de 2 — Datos generales',
    paso2: 'Paso 2 de 2 — Preguntas del cuestionario',
    continuar: 'Continuar',
    atras: 'Atrás',
    crear: 'Crear cuestionario',
    guardarCambios: 'Guardar cambios',
    nombre: 'Nombre del cuestionario',
    nombrePlaceholder: 'Ej. Evaluación de seguridad industrial',
    descripcion: 'Descripción (opcional)',
    descripcionPlaceholder: 'Contexto o instrucciones para quien responde',
    multiples: 'Permitir varios intentos por empleado',
    multiplesDetalle:
      'Si se deja apagado, cada número de empleado solo puede responder una vez.',
    avisoRespuestas:
      'Este cuestionario ya tiene respuestas. Editar o eliminar preguntas ' +
      'afectará las estadísticas históricas.',
    faltaTexto: 'Escribe el texto de la pregunta.',
    minimoOpciones: 'Se requieren mínimo {total} opciones con texto.',
    faltaCorrecta: 'Marca cuál es la opción correcta.',
    correctaUnica: 'Solo puede haber una opción correcta.',
    sinPreguntas: 'Agrega al menos una pregunta antes de guardar.',
    revisaPreguntas: 'Revisa las preguntas marcadas en rojo.',
    falloCarga: 'No se pudo cargar el cuestionario.',
    falloGuardado: 'No se pudo guardar el cuestionario.',
  },

  constructor: {
    pregunta: 'Pregunta {numero}',
    textoPregunta: 'Escribe la pregunta',
    reordenar: 'Reordenar pregunta {numero}',
    eliminarPregunta: 'Eliminar pregunta {numero}',
    opcionesDe: 'Opciones de la pregunta {numero}',
    opcion: 'Opción {numero}',
    marcarCorrecta: 'Marcar la opción {numero} como correcta',
    eliminarOpcion: 'Eliminar opción {numero}',
    minimoOpciones: 'Cada pregunta necesita al menos dos opciones',
    agregarOpcion: 'Agregar opción',
    agregarPregunta: 'Agregar pregunta',
    sinPreguntas: 'Este cuestionario todavía no tiene preguntas.',
  },

  importar: {
    boton: 'Importar desde Excel',
    plantilla: 'Descargar plantilla',
    nota: 'Las preguntas importadas se agregan a las que ya tengas.',
    sinPreguntas: 'No se importó ninguna pregunta.',
    agregadas: 'Se agregaron {total} pregunta(s) al constructor.',
    fallo: 'No se pudo importar el archivo.',
    filasConProblemas:
      '{total} fila(s) con problemas — corrígelas en tu Excel y vuelve a importar:',
    fila: 'Fila {numero}:',
  },

  qr: {
    titulo: 'Códigos QR',
    cuestionario: 'Cuestionario',
    escanearContestar: 'Escanear para contestar',
    red: 'Red WiFi',
    escanearConectar: 'Escanear para conectarse',
    descargarPng: 'Descargar PNG',
    copiarLiga: 'Copiar liga',
    ligaCopiada: 'Liga copiada al portapapeles.',
    falloCopia: 'No se pudo copiar. Selecciona la liga de arriba.',
    advertencia: 'Advertencia:',
    baseLocal:
      'la liga apunta a {url}. Este código QR no funcionará desde un celular. ' +
      'Configura NEXT_PUBLIC_BASE_URL con la IP del servidor en la LAN y ' +
      'reconstruye el frontend.',
    sinRed: 'No hay una red configurada.',
    sinRedDetalle:
      'Captura WIFI_SSID y WIFI_PASSWORD en el archivo .env del servidor y ' +
      'reinicia el backend.',
    falloCuestionario: 'No se pudo generar el código QR del cuestionario.',
    falloWifi: 'No se pudo cargar la configuración de la red WiFi.',
    falloQrRed: 'No se pudo generar el código QR de la red.',
    nota:
      'Imprime ambos códigos juntos y pégalos en el área: primero la red, ' +
      'después el cuestionario.',
  },

  estadisticas: {
    cuestionario: 'Cuestionario',
    seleccionaCuestionario: 'Selecciona un cuestionario',
    seleccionaParaVer: 'Selecciona un cuestionario para ver sus datos.',
    respuestasContador: '{total} respuestas',
    configurarMetas: 'Configurar metas por área',
    descargarExcel: 'Descargar Excel',
    descargarPowerpoint: 'Descargar PowerPoint',
    excelDescargado: 'Excel descargado.',
    powerpointDescargado: 'PowerPoint descargado.',
    limpiarFiltros: 'Limpiar filtros',
    limpiar: 'Limpiar',
    limpiarBusqueda: 'Limpiar la búsqueda',
    actualizando: 'Actualizando gráficas…',
    falloCarga: 'No se pudieron cargar las estadísticas.',
    falloReporte: 'No se pudo generar el reporte.',
    kpiRespuestas: 'Respuestas recibidas',
    kpiParticipacion: 'Nivel de participación',
    kpiPromedio: 'Calificación promedio',
    kpiAprobacion: 'Tasa de aprobación',
    sinFinalizarContador: '{total} sin finalizar',
    participacionDetalle: '{recibidas} de {meta} personas',
    sinMetas: 'Captura las metas por área para calcularlo',
    aprobadosDetalle: '{total} aprobados (umbral {umbral}%)',
    intentos: 'Intentos',
    registros: '{total} registro(s)',
    numeroEmpleado: 'Núm. empleado',
    duracion: 'Duración',
    puntaje: 'Puntaje',
    buscarPlaceholder: 'Nombre o número de empleado',
    sinCoincidencias: 'Ningún intento coincide con “{busqueda}”.',
    sinIntentos: 'No hay intentos para los filtros seleccionados.',
    enProgreso: 'En progreso',
    sinFinalizar: 'Sin finalizar',
    verRespuestas: 'Ver respuestas',
    verRespuestasDe: 'Ver las respuestas de {nombre}',
    pagina: 'Página {actual} de {total}',
    anterior: 'Anterior',
    siguiente: 'Siguiente',
    aprobado: 'Aprobado',
    noAprobado: 'No aprobado',
  },

  respuestas: {
    titulo: 'Respuestas del intento',
    aciertos: 'Aciertos',
    resultado: 'Resultado',
    contestado: 'Contestado el {fecha} · umbral de aprobación {umbral}%',
    sinResponder: '{total} pregunta(s) sin responder',
    correcta: 'Correcta',
    incorrecta: 'Incorrecta',
    noRespondida: 'Sin responder',
    suRespuesta: 'Su respuesta',
    falloCarga: 'No se pudieron cargar las respuestas.',
  },

  metas: {
    titulo: 'Metas de participación por área',
    descripcion:
      'Cuántas personas hay en cada área. Es el denominador del nivel de ' +
      'participación.',
    guardar: 'Guardar metas',
    guardadas: 'Metas guardadas.',
    sinCapturar: 'Sin capturar',
    personas: 'personas',
    invalido: 'El headcount debe ser un número entero mayor o igual a cero.',
    falloCarga: 'No se pudieron cargar las metas.',
    falloGuardado: 'No se pudieron guardar las metas.',
  },

  graficas: {
    sinDatos: 'Sin datos para los filtros seleccionados.',
    participacion: 'Participación por área',
    participacionConMetas: 'Respuestas recibidas contra la meta de headcount.',
    participacionSinMetas:
      'Captura las metas por área para ver el porcentaje de participación.',
    meta: 'Meta',
    promedioArea: 'Calificación promedio por área',
    promedioAreaDetalle:
      'Las barras rojas quedaron debajo del umbral de aprobación ({umbral}%).',
    promedio: 'Promedio',
    promedioPorcentaje: 'Promedio %',
    distribucion: 'Distribución de calificaciones',
    distribucionDetalle: 'Cuántas personas cayeron en cada rango.',
    falladas: 'Preguntas con mayor índice de error',
    falladasDetalle:
      'Señala qué temas necesitan recapacitación o qué preguntas están mal ' +
      'redactadas.',
    incorrectas: 'Respuestas incorrectas',
    porDia: 'Respuestas por día',
    porDiaDetalle: 'Volumen diario y promedio de cada jornada.',
  },

  fotos: {
    titulo: 'Fotos de evidencia',
    contador: '({total} de {maximo})',
    agregar: 'Tomar o elegir foto',
    agregarOtra: 'Agregar otra foto',
    quitar: 'Quitar la foto {numero}',
    numero: 'Evidencia {numero}',
    ver: 'Ver la evidencia',
    invalida: 'El archivo debe ser una imagen.',
    pesada: 'La foto pesa demasiado, incluso después de reducirla.',
    tope: 'No se pueden subir más de {total} fotos.',
  },

  checklist: {
    registroDelDia: 'Registro del día',
    descripcion:
      'Marca cada punto. Un punto en NO OK necesita observaciones y evidencia ' +
      'fotográfica.',
    ok: 'OK',
    noOk: 'NO OK',
    confirmar: 'Confirmar',
    observacionesPlaceholder: '¿Qué se encontró y qué se hizo?',
    faltaFoto: 'Agrega al menos una foto de evidencia.',
    faltanPuntos: 'Faltan {total} puntos por marcar.',
    faltanObservaciones: 'Hay {total} puntos en NO OK sin observaciones.',
    faltanFotos: 'Hay {total} puntos en NO OK sin foto.',
    guardado: 'Registro guardado.',
    eliminado: 'Registro eliminado. Ya puedes capturarlo de nuevo.',
    yaRegistrado: 'El registro del {fecha} ya está capturado.',
    eliminarRegistro: 'Elimínalo si necesitas capturarlo de nuevo.',
    historial: 'Registros',
    historialVacio: 'Todavía no hay registros en este periodo.',
    confirmarEliminar: '¿Eliminar el registro del {fecha}?',
    confirmarEliminarDetalle:
      'Se borran los puntos capturados y sus evidencias. Después podrás ' +
      'capturar el día otra vez.',
  },

  platicas: {
    registrar: 'Registrar plática',
    descripcion:
      'Escribe el tema, marca las áreas donde se impartió y agrega la ' +
      'evidencia fotográfica.',
    tema: 'Tema',
    temaPlaceholder: '¿De qué trató la plática?',
    areas: 'Áreas donde se impartió',
    primeroTema: 'Escribe primero el tema',
    faltaTema: 'Escribe el tema de la plática.',
    faltaArea: 'Marca al menos un área.',
    faltaFoto: 'Agrega al menos una foto de evidencia.',
    listo: 'Lista para confirmar: {total} área(s).',
    guardada: 'Plática registrada.',
    eliminada: 'Plática eliminada.',
    historial: 'Pláticas registradas',
    historialVacio: 'Todavía no hay pláticas registradas en este periodo.',
    confirmarEliminar: '¿Eliminar la plática del {fecha}?',
    confirmarEliminarDetalle:
      'Se borra el registro junto con sus fotos. No se puede deshacer.',
  },

  inventario: {
    titulo: 'Inventario',
    descripcion:
      'Inventario de medicamento y demás insumos de seguridad.',
    enConstruccion: 'En construcción',
    enConstruccionDetalle:
      'El inventario todavía se lleva en el archivo de Excel. Se habilitará aquí ' +
      'en cuanto se definan sus reglas de captura.',
  },
};

// Sin `as const` a propósito: los valores tienen que quedar como `string` para
// que `en.ts` y `ko.ts` puedan tipearse contra este diccionario sin verse
// obligados a repetir el texto en español.
export type Diccionario = typeof es;
