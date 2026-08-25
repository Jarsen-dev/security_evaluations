import type { Diccionario } from './es';

/**
 * English translation of the panel.
 *
 * Typed against `Diccionario`, so adding a key to `es.ts` breaks the build
 * here until it is translated. Domain data — area names, questionnaire and
 * question text, captured observations — is never translated: it comes from
 * the database as it was written.
 */
export const en: Diccionario = {
  comun: {
    guardar: 'Save',
    guardando: 'Saving…',
    cancelar: 'Cancel',
    cerrar: 'Close',
    eliminar: 'Delete',
    eliminando: 'Deleting…',
    editar: 'Edit',
    duplicar: 'Duplicate',
    descargar: 'Download',
    descargando: 'Downloading…',
    cargando: 'Loading…',
    reintentar: 'Retry',
    buscar: 'Search',
    area: 'Area',
    areaTodas: 'All areas',
    fecha: 'Date',
    desde: 'From',
    hasta: 'To',
    observaciones: 'Notes',
    responsable: 'Recorded by',
    acciones: 'Actions',
    sinDatos: 'There is nothing to show yet.',
    errorGenerico: 'Something went wrong. Please try again.',
    obligatorio: 'This field is required.',
    mes: 'Month',
    descargarExcel: 'Download as Excel',
    si: 'Yes',
    no: 'No',
  },

  encabezado: {
    titulo: 'ESH System',
    secciones: 'Panel sections',
    cuestionarios: 'Questionnaires',
    controles: 'Controls',
    inventario: 'Inventory',
    salir: 'Sign out',
    idioma: 'Language',
    cambiarIdioma: 'Change the panel language',
  },

  login: {
    titulo: 'ESH System',
    subtitulo: 'Administration panel access',
    usuario: 'Username',
    contrasena: 'Password',
    entrar: 'Sign in',
    verificando: 'Checking…',
    faltaUsuario: 'Enter your username.',
    faltaContrasena: 'Enter your password.',
    fallo: 'Could not sign in. Please try again.',
    nota:
      'Employees answering questionnaires do not need an account: they get in ' +
      'through the link or the QR code.',
  },

  controles: {
    titulo: 'Controls',
    descripcion:
      'Safety department inspection forms. Each tab is one control of the ' +
      'daily walkthrough.',
    pestanas: 'Available controls',
    sqp: 'Hazardous chemicals inspection',
    almacenRp: 'Hazardous waste storage',
    rayser: 'Rayser',
    platicas: 'ESH safety talks',
    recorridos: 'Perimeter walkthroughs',
    muro: 'Wall inspection',
    medicamento: 'Medicine log',
    silos: 'EPS silos',
    tableros: 'Electrical panels',
    enConstruccion: 'Under construction',
    enConstruccionDetalle:
      'This control is still filled in on paper. It will be enabled here as ' +
      'soon as its capture rules are defined.',
  },

  rayser: {
    titulo: 'Rayser pressure log',
    descripcion:
      'Daily reading of the four gauges. Normal pressure is {normal} psi.',
    manometro: 'Gauge {numero}',
    placeholderLectura: 'psi',
    terminarRegistro: 'Finish entry',
    registroDelDia: "Today's entry",
    yaRegistrado: 'The reading for {fecha} has already been recorded.',
    eliminarRegistro: 'Delete the entry to record it again',
    guardado: 'Entry saved.',
    eliminado: 'Entry deleted. You can record it again now.',
    rangoNormal: 'Normal: {minimo} to {maximo} psi',
    semaforo: {
      verde: 'Normal',
      rojo: 'Low',
      naranja: 'High',
    },
    evidenciaTitulo: 'Evidence required',
    evidenciaDetalle:
      'One or more readings fell outside the normal range: attach the photo ' +
      'and write down what happened.',
    observacionesPlaceholder: 'What was observed and what was done?',
    faltaObservaciones: 'Write the notes for the out-of-range reading.',
    faltaFoto: 'Attach the evidence photo.',
    faltanLecturas: 'Enter all four readings.',
    historial: 'Entries',
    evidencia: 'Evidence',
    verEvidencia: 'View the evidence',
    historialVacio: 'There are no entries for this period yet.',
    confirmarEliminar: 'Delete the entry for {fecha}?',
    confirmarEliminarDetalle:
      'The reading and its evidence will be deleted. You will be able to ' +
      'record that day again afterwards.',
  },

  sqp: {
    titulo: 'Hazardous chemicals inspection',
    descripcion:
      'Answer all {total} items on the form. An item marked NO needs notes.',
    encargado: 'Person in charge',
    encargadoPlaceholder: 'Who is responsible for the area',
    cargo: 'Job title',
    cargoPlaceholder: 'Title of the person in charge',
    respuestaSi: 'YES',
    respuestaNo: 'NO',
    respuestaNa: 'N/A',
    observacionesPlaceholder: 'What was found?',
    sustancias: 'Chemicals in the area',
    sustanciasAyuda: 'Write one chemical per line.',
    sustanciasContador: '{total} chemicals entered',
    guardarInspeccion: 'Save inspection',
    faltanPuntos: '{total} items still unanswered.',
    faltanObservaciones: '{total} items marked NO have no notes.',
    faltanSustancias: 'Enter at least one chemical for the area.',
    guardada: 'Inspection saved.',
    historial: 'Recorded inspections',
    historialVacio: 'No inspections recorded yet.',
    hallazgos: 'Findings',
    hallazgosDetalle: '{total} marked NO',
    descargarExcel: 'Download as Excel',
    progreso: '{contestados} of {total} answered',
  },

  cuestionarios: {
    pestanas: 'Questionnaire views',
    pestanaCuestionarios: 'Questionnaires',
    pestanaEstadisticas: 'Statistics',
    nombre: 'Name',
    numeroEmpleado: 'Employee number',
    camposFijos: 'Fixed fields — always requested',
    opcionesArea: '{total} options',
    activo: 'Active',
    inactivo: 'Inactive',
    activar: 'Activate',
    desactivar: 'Deactivate',
    preguntas: 'Questions',
    respuestas: 'Responses',
    liga: 'Desktop link',
    ligaAyuda: 'Copy the link to open it from a PC',
    imprimir: 'Print',
    imprimirAyuda: 'Download the PDF to answer it on paper',
    sinPreguntasImprimir: 'This questionnaire has no questions to print',
    masAcciones: 'More actions for {nombre}',
    vacio: 'There are no questionnaires yet.',
    vacioAyuda: 'Create the first one with the “New questionnaire” button.',
    creado: 'Questionnaire created.',
    cambiosGuardados: 'Changes saved.',
    duplicado: 'Questionnaire duplicated. The copy stays inactive.',
    activado: 'Questionnaire activated.',
    desactivado:
      'Questionnaire deactivated. The public link stops accepting responses.',
    eliminado: 'Questionnaire deleted.',
    pdfDescargado: 'PDF downloaded. Open it to choose your printer.',
    falloCarga: 'Could not load the questionnaires.',
    falloDuplicar: 'Could not duplicate it.',
    falloEstado: 'Could not change its status.',
    falloEliminar: 'Could not delete it.',
    falloPdf: 'Could not generate the PDF.',
    confirmarEliminar: 'Delete questionnaire',
    confirmarEliminarDetalle:
      '“{nombre}” will be deleted along with its {preguntas} question(s) and ' +
      '{respuestas} response(s). This cannot be undone.',
  },

  modalCuestionario: {
    nuevo: 'New questionnaire',
    editar: 'Edit questionnaire',
    paso1: 'Step 1 of 2 — General details',
    paso2: 'Step 2 of 2 — Questions',
    continuar: 'Continue',
    atras: 'Back',
    crear: 'Create questionnaire',
    guardarCambios: 'Save changes',
    nombre: 'Questionnaire name',
    nombrePlaceholder: 'E.g. Industrial safety assessment',
    descripcion: 'Description (optional)',
    descripcionPlaceholder: 'Context or instructions for whoever answers',
    multiples: 'Allow several attempts per employee',
    multiplesDetalle:
      'If left off, each employee number can answer only once.',
    avisoRespuestas:
      'This questionnaire already has responses. Editing or deleting ' +
      'questions will affect the historical statistics.',
    faltaTexto: 'Write the question text.',
    minimoOpciones: 'At least {total} options with text are required.',
    faltaCorrecta: 'Mark which option is correct.',
    correctaUnica: 'Only one option can be correct.',
    sinPreguntas: 'Add at least one question before saving.',
    revisaPreguntas: 'Check the questions marked in red.',
    falloCarga: 'Could not load the questionnaire.',
    falloGuardado: 'Could not save the questionnaire.',
  },

  constructor: {
    pregunta: 'Question {numero}',
    textoPregunta: 'Write the question',
    reordenar: 'Reorder question {numero}',
    eliminarPregunta: 'Delete question {numero}',
    opcionesDe: 'Options for question {numero}',
    opcion: 'Option {numero}',
    marcarCorrecta: 'Mark option {numero} as correct',
    eliminarOpcion: 'Delete option {numero}',
    minimoOpciones: 'Every question needs at least two options',
    agregarOpcion: 'Add option',
    agregarPregunta: 'Add question',
    sinPreguntas: 'This questionnaire has no questions yet.',
  },

  importar: {
    boton: 'Import from Excel',
    plantilla: 'Download template',
    nota: 'Imported questions are added to the ones you already have.',
    sinPreguntas: 'No questions were imported.',
    agregadas: '{total} question(s) were added to the builder.',
    fallo: 'Could not import the file.',
    filasConProblemas:
      '{total} row(s) have problems — fix them in your Excel file and import again:',
    fila: 'Row {numero}:',
  },

  qr: {
    titulo: 'QR codes',
    cuestionario: 'Questionnaire',
    escanearContestar: 'Scan to answer',
    red: 'WiFi network',
    escanearConectar: 'Scan to connect',
    descargarPng: 'Download PNG',
    copiarLiga: 'Copy link',
    ligaCopiada: 'Link copied to the clipboard.',
    falloCopia: 'Could not copy. Select the link above instead.',
    advertencia: 'Warning:',
    baseLocal:
      'the link points to {url}. This QR code will not work from a phone. ' +
      'Set NEXT_PUBLIC_BASE_URL to the server IP on the LAN and rebuild the ' +
      'frontend.',
    sinRed: 'No network is configured.',
    sinRedDetalle:
      'Set WIFI_SSID and WIFI_PASSWORD in the server .env file and restart ' +
      'the backend.',
    falloCuestionario: 'Could not generate the questionnaire QR code.',
    falloWifi: 'Could not load the WiFi network settings.',
    falloQrRed: 'Could not generate the network QR code.',
    nota:
      'Print both codes together and post them in the area: the network ' +
      'first, then the questionnaire.',
  },

  estadisticas: {
    cuestionario: 'Questionnaire',
    seleccionaCuestionario: 'Choose a questionnaire',
    seleccionaParaVer: 'Choose a questionnaire to see its data.',
    respuestasContador: '{total} responses',
    configurarMetas: 'Set targets by area',
    descargarExcel: 'Download Excel',
    descargarPowerpoint: 'Download PowerPoint',
    excelDescargado: 'Excel downloaded.',
    powerpointDescargado: 'PowerPoint downloaded.',
    limpiarFiltros: 'Clear filters',
    limpiar: 'Clear',
    limpiarBusqueda: 'Clear the search',
    actualizando: 'Updating charts…',
    falloCarga: 'Could not load the statistics.',
    falloReporte: 'Could not generate the report.',
    kpiRespuestas: 'Responses received',
    kpiParticipacion: 'Participation level',
    kpiPromedio: 'Average score',
    kpiAprobacion: 'Pass rate',
    sinFinalizarContador: '{total} unfinished',
    participacionDetalle: '{recibidas} of {meta} people',
    sinMetas: 'Set the targets by area to calculate it',
    aprobadosDetalle: '{total} passed (threshold {umbral}%)',
    intentos: 'Attempts',
    registros: '{total} record(s)',
    numeroEmpleado: 'Employee no.',
    duracion: 'Duration',
    puntaje: 'Score',
    buscarPlaceholder: 'Name or employee number',
    sinCoincidencias: 'No attempt matches “{busqueda}”.',
    sinIntentos: 'There are no attempts for the selected filters.',
    enProgreso: 'In progress',
    sinFinalizar: 'Unfinished',
    verRespuestas: 'View answers',
    verRespuestasDe: 'View the answers of {nombre}',
    pagina: 'Page {actual} of {total}',
    anterior: 'Previous',
    siguiente: 'Next',
    aprobado: 'Passed',
    noAprobado: 'Not passed',
  },

  respuestas: {
    titulo: 'Attempt answers',
    aciertos: 'Correct',
    resultado: 'Result',
    contestado: 'Answered on {fecha} · pass threshold {umbral}%',
    sinResponder: '{total} question(s) left unanswered',
    correcta: 'Correct',
    incorrecta: 'Incorrect',
    noRespondida: 'Unanswered',
    suRespuesta: 'Their answer',
    falloCarga: 'Could not load the answers.',
  },

  metas: {
    titulo: 'Participation targets by area',
    descripcion:
      'How many people work in each area. It is the denominator of the ' +
      'participation level.',
    guardar: 'Save targets',
    guardadas: 'Targets saved.',
    sinCapturar: 'Not set',
    personas: 'people',
    invalido: 'Headcount must be a whole number of zero or more.',
    falloCarga: 'Could not load the targets.',
    falloGuardado: 'Could not save the targets.',
  },

  graficas: {
    sinDatos: 'No data for the selected filters.',
    participacion: 'Participation by area',
    participacionConMetas: 'Responses received against the headcount target.',
    participacionSinMetas:
      'Set the targets by area to see the participation percentage.',
    meta: 'Target',
    promedioArea: 'Average score by area',
    promedioAreaDetalle:
      'Red bars fell below the pass threshold ({umbral}%).',
    promedio: 'Average',
    promedioPorcentaje: 'Average %',
    distribucion: 'Score distribution',
    distribucionDetalle: 'How many people fell into each range.',
    falladas: 'Questions with the highest error rate',
    falladasDetalle:
      'Shows which topics need retraining or which questions are poorly worded.',
    incorrectas: 'Incorrect answers',
    porDia: 'Responses per day',
    porDiaDetalle: 'Daily volume and the average of each day.',
  },

  fotos: {
    titulo: 'Evidence photos',
    contador: '({total} of {maximo})',
    agregar: 'Take or choose a photo',
    agregarOtra: 'Add another photo',
    quitar: 'Remove photo {numero}',
    numero: 'Evidence {numero}',
    ver: 'View the evidence',
    invalida: 'The file must be an image.',
    pesada: 'The photo is too large, even after being resized.',
    tope: 'You cannot upload more than {total} photos.',
  },

  checklist: {
    registroDelDia: "Today's entry",
    listaVerificacion: 'Checklist',
    descripcionSiNo:
      'Mark every item. An item marked NO needs notes and photo evidence.',
    descripcion:
      'Mark every item. An item marked NO OK needs notes and photo evidence.',
    ok: 'OK',
    noOk: 'NOT OK',
    confirmar: 'Confirm',
    si: 'YES',
    no: 'NO',
    encabezado: 'Inspection details',
    hallazgos: 'Findings',
    hallazgosDetalle: '{total} marked NO',
    faltanEncabezado: '{total} inspection details are missing.',
    faltanMediciones: '{total} readings are missing.',
    faltanSecciones: '{total} fields are missing at the foot of the form.',
    observacionesPlaceholder: 'What was found and what was done?',
    faltaFoto: 'Add at least one evidence photo.',
    faltanPuntos: '{total} items still unmarked.',
    faltanObservaciones: '{total} items marked NOT OK have no notes.',
    faltanFotos: '{total} items marked NOT OK have no photo.',
    guardado: 'Entry saved.',
    eliminado: 'Entry deleted. You can record it again now.',
    yaRegistrado: 'The entry for {fecha} has already been recorded.',
    eliminarRegistro: 'Delete it if you need to record it again.',
    historial: 'Entries',
    historialVacio: 'There are no entries for this period yet.',
    confirmarEliminar: 'Delete the entry for {fecha}?',
    confirmarEliminarDetalle:
      'The recorded items and their evidence will be deleted. You will be able ' +
      'to record that day again afterwards.',
  },

  platicas: {
    registrar: 'Record a safety talk',
    descripcion:
      'Write the topic, mark the areas where it was given and attach the photo ' +
      'evidence.',
    tema: 'Topic',
    temaPlaceholder: 'What was the talk about?',
    areas: 'Areas where it was given',
    primeroTema: 'Write the topic first',
    faltaTema: 'Write the topic of the talk.',
    faltaArea: 'Mark at least one area.',
    faltaFoto: 'Add at least one evidence photo.',
    listo: 'Ready to confirm: {total} area(s).',
    guardada: 'Safety talk recorded.',
    eliminada: 'Safety talk deleted.',
    historial: 'Recorded talks',
    historialVacio: 'No talks recorded for this period yet.',
    confirmarEliminar: 'Delete the talk from {fecha}?',
    confirmarEliminarDetalle:
      'The record and its photos will be deleted. This cannot be undone.',
  },

  inventario: {
    titulo: 'Inventory',
    descripcion: 'Medicine inventory and other safety supplies.',
    enConstruccion: 'Under construction',
    enConstruccionDetalle:
      'The inventory is still kept in the Excel file. It will be enabled here ' +
      'as soon as its capture rules are defined.',
  },
};
