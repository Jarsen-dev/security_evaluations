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
    sinAcceso: 'No tienes acceso a esta sección. Pídeselo al administrador del sistema.',
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
    catalogo: 'Catálogo',
    rondines: 'Rondines',
    administracion: 'Administración',
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
    listaVerificacion: 'Lista de verificación',
    descripcionSiNo:
      'Marca cada punto. Un punto en NO necesita observaciones y evidencia ' +
      'fotográfica.',
    descripcion:
      'Marca cada punto. Un punto en NO OK necesita observaciones y evidencia ' +
      'fotográfica.',
    ok: 'OK',
    noOk: 'NO OK',
    confirmar: 'Confirmar',
    si: 'SÍ',
    no: 'NO',
    encabezado: 'Datos de la inspección',
    hallazgos: 'Hallazgos',
    hallazgosDetalle: '{total} en NO',
    faltanEncabezado: 'Faltan {total} datos de la inspección.',
    faltanMediciones: 'Faltan {total} mediciones.',
    faltanSecciones: 'Faltan {total} datos por capturar al pie del formato.',
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

  administracion: {
    titulo: 'Administración',
    descripcion: 'Usuarios, actividad del sistema y mantenimiento de la base.',
    usuarios: 'Usuarios',
    logs: 'Logs',
    mantenimiento: 'Mantenimiento',
    secciones: 'Secciones de administración',
    soloSuperadmin: 'Esta sección es solo para el superadministrador.',
  },

  usuarios: {
    titulo: 'Usuarios del sistema',
    descripcion: 'Quién entra al panel y qué puede hacer dentro de cada pestaña.',
    nuevo: 'Nuevo usuario',
    nombre: 'Nombre',
    usuario: 'Usuario',
    email: 'Correo electrónico',
    contrasena: 'Contraseña',
    contrasenaNueva: 'Nueva contraseña',
    contrasenaAyuda: 'Mínimo 8 caracteres.',
    contrasenaOpcional: 'Déjala vacía para conservar la actual.',
    rol: 'Rol',
    superadmin: 'Superadministrador',
    normal: 'Usuario',
    estado: 'Estado',
    activo: 'Activo',
    inactivo: 'Desactivado',
    ultimoAcceso: 'Último acceso',
    nunca: 'Nunca',
    tu: 'Tú',
    sinPermisos: 'Sin acceso a ninguna pestaña',
    crear: 'Crear usuario',
    editar: 'Editar usuario',
    activar: 'Activar',
    desactivar: 'Desactivar',
    vacio: 'Todavía no hay más usuarios.',
    vacioAyuda: 'Da de alta al personal que va a usar el panel.',
    falloCarga: 'No se pudieron cargar los usuarios.',
    creado: 'Usuario creado.',
    actualizado: 'Usuario actualizado.',
    activado: 'Usuario activado.',
    desactivado: 'Usuario desactivado. Sus sesiones abiertas se cerraron.',
    eliminado: 'Usuario eliminado.',
    falloGuardar: 'No se pudo guardar el usuario.',
    falloEstado: 'No se pudo cambiar el estado del usuario.',
    falloEliminar: 'No se pudo eliminar el usuario.',
    confirmarEliminar: 'Eliminar usuario',
    confirmarEliminarDetalle:
      '{nombre} perderá el acceso de inmediato y su cuenta se borrará. Lo que ' +
      'haya capturado se conserva. Esta acción no se puede deshacer.',
    faltaNombre: 'Escribe el nombre completo.',
    faltaUsuario: 'Escribe el nombre de usuario.',
    usuarioConEspacios: 'El usuario no puede contener espacios.',
    faltaEmail: 'Escribe un correo electrónico válido.',
    faltaContrasena: 'La contraseña debe tener al menos 8 caracteres.',
  },

  permisos: {
    titulo: 'Permisos',
    ayuda:
      'Con el acceso se puede ver y crear. Marcar "Editar" agrega modificar y ' +
      'eliminar dentro de esa pestaña.',
    modulo: 'Pestaña',
    acceso: 'Acceso',
    editar: 'Editar',
    cuestionarios: 'Cuestionarios',
    controles: 'Controles',
    inventario: 'Inventario',
    catalogo: 'Catálogo',
    rondines: 'Rondines',
    accesoA: 'Dar acceso a {modulo}',
    editarEn: 'Permitir editar y eliminar en {modulo}',
    superadminTodo: 'El superadministrador tiene acceso completo a todo el panel.',
  },

  logs: {
    titulo: 'Actividad del sistema',
    descripcion:
      'Todo lo que se crea, edita o elimina, más los inicios de sesión. Las ' +
      'consultas de lectura no se registran.',
    fecha: 'Fecha',
    horaDesde: 'Hora desde',
    horaHasta: 'Hora hasta',
    usuario: 'Usuario',
    todosLosUsuarios: 'Todos los usuarios',
    limpiar: 'Limpiar filtros',
    hora: 'Hora',
    accion: 'Acción',
    detalle: 'Detalle',
    origen: 'Origen',
    registros: '{total} registros',
    pagina: 'Página {pagina} de {total}',
    anterior: 'Anterior',
    siguiente: 'Siguiente',
    vacio: 'Todavía no hay actividad registrada.',
    sinCoincidencias: 'Ningún registro coincide con los filtros.',
    falloCarga: 'No se pudo cargar la actividad.',
  },

  mantenimiento: {
    titulo: 'Mantenimiento',
    descripcion: 'Acceso directo a pgAdmin para revisar la base de datos.',
    local: 'pgAdmin — Local',
    localDetalle: 'La base de esta máquina, la de desarrollo.',
    produccion: 'pgAdmin — Producción',
    produccionDetalle:
      'La base del servidor de planta. Solo se alcanza desde la red interna.',
    abrir: 'Abrir y copiar credenciales',
    noConfigurado: 'No configurado',
    noConfiguradoDetalle:
      'Falta capturar su URL en el archivo .env del proyecto.',
    credenciales: 'Credenciales',
    copiado: 'Credenciales copiadas. Pégalas en pgAdmin.',
    falloCopiar: 'No se pudieron copiar. Cópialas a mano: {credenciales}',
    falloCarga: 'No se pudieron cargar los accesos.',
    aviso:
      'pgAdmin no permite iniciar sesión desde una liga externa, así que el ' +
      'botón abre la pestaña con las credenciales ya en el portapapeles.',
  },

  catalogo: {
    titulo: 'Catálogo de insumos',
    descripcion:
      'Los insumos de seguridad de la planta: medicamento, EPP, señalización y ' +
      'extintores, con su existencia y sus topes de inventario.',
    nuevo: 'Nuevo insumo',
    nombre: 'Nombre',
    nombreAyuda: 'Identifica al insumo. No puede repetirse.',
    descripcionCampo: 'Descripción',
    categoria: 'Categoría',
    proveedor: 'Proveedor',
    ubicacion: 'Ubicación',
    cantidad: 'Cantidad',
    minimo: 'Mín. inventario',
    maximo: 'Máx. inventario',
    rango: 'Mín. / Máx.',
    estado: 'Estado',
    crear: 'Nuevo insumo',
    editar: 'Editar insumo',
    registros: '{total} insumo(s)',
    pagina: 'Página {pagina} de {total}',
    anterior: 'Anterior',
    siguiente: 'Siguiente',
    todasLasCategorias: 'Todas las categorías',
    todosLosEstados: 'Todos los estados',
    limpiar: 'Limpiar filtros',
    buscarAyuda: 'Buscar por nombre, descripción, proveedor o ubicación…',
    vacio: 'Todavía no hay insumos en el catálogo.',
    vacioAyuda: 'Da de alta el primero, o carga varios desde un Excel.',
    sinCoincidencias: 'Ningún insumo coincide con los filtros.',
    falloCarga: 'No se pudo cargar el catálogo.',
    creado: 'Insumo dado de alta.',
    actualizado: 'Insumo actualizado.',
    eliminado: 'Insumo eliminado.',
    falloGuardar: 'No se pudo guardar el insumo.',
    falloEliminar: 'No se pudo eliminar el insumo.',
    confirmarEliminar: 'Eliminar insumo',
    confirmarEliminarDetalle:
      '«{nombre}» se borrará del catálogo. Esta acción no se puede deshacer.',
    faltaNombre: 'Escribe el nombre del insumo.',
    faltaCategoria: 'Elige una categoría.',
    numeroInvalido: 'Escribe un número entero de 0 o más.',
    rangoInvertido: 'El máximo no puede ser menor que el mínimo.',
  },

  semaforoInsumo: {
    bajo: 'Bajo mínimo',
    normal: 'Normal',
    excedido: 'Excedido',
    ayuda:
      'Bajo mínimo cuando la existencia no alcanza el mínimo; excedido cuando ' +
      'pasa del máximo.',
  },

  importarCatalogo: {
    boton: 'Importar desde Excel',
    importando: 'Importando…',
    plantilla: 'Descargar plantilla',
    nota:
      'Los insumos nuevos se dan de alta y los que ya existen se omiten, así que ' +
      'volver a subir un archivo no pisa lo capturado.',
    resultado: '{creados} insumo(s) nuevo(s); {omitidos} ya existían.',
    fallo: 'No se pudo importar el archivo.',
    filasConProblemas:
      '{total} fila(s) con problemas — corrígelas en tu Excel y vuelve a importar:',
    fila: 'Fila {numero}:',
  },

  rondines: {
    titulo: 'Rondines de seguridad',
    descripcion:
      'Seguimiento de los recorridos por turno: qué punto se visitó, en qué ' +
      'rondín y a qué hora.',
    tablero: 'Tablero',
    puntos: 'Puntos de control',
    secciones: 'Secciones de rondines',
    turno: 'Turno',
    turnoDia: 'Día',
    turnoNoche: 'Noche',
    dia: 'Día de inicio',
    rango: '{inicio} → {fin}',
    ayudaTurno:
      'El día que eliges es el de INICIO del turno. Para la noche del 25 al 26, ' +
      'elige el 25 con turno Noche.',
    cumplimiento: 'Cumplimiento general',
    visitas: 'Visitas del turno',
    rondinEnCurso: 'Rondín en curso',
    fueraDeTurno: 'Turno cerrado',
    avance: 'Avance del rondín',
    rondin: 'Rondín {numero}',
    punto: 'Punto',
    porRondin: 'Cumplimiento por rondín',
    visitados: 'Visitados',
    sinVisita: 'Sin visita',
    descargar: 'Descargar Excel',
    enviarCorreo: 'Enviar por correo',
    correoDestino: 'Correo del destinatario',
    correoEnviado: 'Reporte enviado correctamente.',
    falloCorreo: 'No se pudo enviar el reporte.',
    sinPuntos: 'Todavía no hay puntos de control.',
    sinPuntosAyuda: 'Da de alta los puntos para que el tablero tenga qué mostrar.',
    falloCarga: 'No se pudo cargar el tablero.',
    actualizado: 'Actualizado a las {hora}',
  },

  puntosRondin: {
    titulo: 'Puntos de control',
    descripcion:
      'Cada punto tiene su código QR. Imprímelos, recórtalos y pégalos en su ' +
      'lugar de la planta.',
    nuevo: 'Nuevo punto',
    imprimir: 'Imprimir códigos QR',
    numero: 'Número',
    numeroAyuda: 'Es lo que se imprime en la etiqueta. No puede repetirse.',
    nombre: 'Nombre',
    ubicacion: 'Ubicación',
    estado: 'Estado',
    activo: 'Activo',
    inactivo: 'Retirado',
    codigo: 'Código QR',
    verCodigo: 'Ver código',
    crear: 'Nuevo punto de control',
    editar: 'Editar punto de control',
    vacio: 'Todavía no hay puntos de control.',
    vacioAyuda: 'Da de alta el primero para empezar a registrar recorridos.',
    falloCarga: 'No se pudieron cargar los puntos.',
    creado: 'Punto dado de alta.',
    actualizadoOk: 'Punto actualizado.',
    eliminado: 'Punto eliminado.',
    falloGuardar: 'No se pudo guardar el punto.',
    falloEliminar: 'No se pudo eliminar el punto.',
    confirmarEliminar: 'Eliminar punto de control',
    confirmarEliminarDetalle:
      'El punto {nombre} se borrará y su código QR dejará de servir. Los ' +
      'recorridos anteriores conservan el número, pero dejarán de contarse. ' +
      'Casi siempre conviene retirarlo en vez de borrarlo.',
    faltaNumero: 'Escribe el número del punto.',
    faltaNombre: 'Escribe el nombre del punto.',
    descargarQr: 'Descargar PNG',
    ligaCopiada: 'Liga copiada.',
    falloCopiar: 'No se pudo copiar. Cópiala a mano: {liga}',
  },
};

// Sin `as const` a propósito: los valores tienen que quedar como `string` para
// que `en.ts` y `ko.ts` puedan tipearse contra este diccionario sin verse
// obligados a repetir el texto en español.
export type Diccionario = typeof es;
