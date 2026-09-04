"""Schemas de los controles ESH (panel de administración).

Estos endpoints exigen sesión: nada de aquí se sirve sin autenticación. Los
schemas del formulario público siguen viviendo aparte, en
``app.schemas.publico`` (ver regla 1 del CLAUDE.md).
"""

import uuid
from datetime import date, datetime, time
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.constants import AREAS_VALIDAS, TOPE_EXISTENCIA
from app.core.controles_catalogo import (
    CLAVES_AREAS_PLATICAS,
    MAX_EXTINTORES,
    TIPOS_EXTINTOR,
    TIPOS_EXTINTOR_VALIDOS,
    VALORES_CHECKLIST,
    VALORES_SQP,
)
from app.schemas.sistema import AreaOut


def _sin_espacios(valor: str) -> str:
    """Recorta espacios al inicio y al final."""
    return valor.strip()


def _texto_opcional(valor: str | None) -> str | None:
    """Recorta espacios y convierte el texto vacío en ``None``."""
    if valor is None:
        return None
    limpio = valor.strip()
    return limpio or None


# --- Rayser ----------------------------------------------------------------


class LecturaManometro(BaseModel):
    """Una lectura ya clasificada por el servidor."""

    valor: Decimal = Field(description="Presión en psi.")
    semaforo: str = Field(description="'verde', 'rojo' o 'naranja'.")


class RegistroRayserOut(BaseModel):
    """Registro diario tal como lo consume la tabla del panel.

    No incluye las imágenes: una lista de 31 días con las fotos embebidas
    pesaría varios megabytes. Solo viajan sus identificadores y cada una se
    pide aparte por ``GET /api/controles/fotos/{foto_id}``.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    fecha: date
    manometros: list[LecturaManometro]
    observaciones: str | None
    fotos: list[uuid.UUID]
    fuera_de_rango: bool
    responsable: str
    creado_at: datetime


class RangoRayser(BaseModel):
    """Rango de operación que el frontend usa para pintar el semáforo en vivo."""

    minimo: Decimal
    maximo: Decimal
    normal: Decimal
    manometros: int


# El registro de Rayser llega como multipart (trae las fotos), así que sus
# campos se declaran con `Form(...)` en la ruta y no hay schema de entrada:
# Pydantic no valida cuerpos multipart campo por campo.


# --- Inspección de SQP -----------------------------------------------------


class PuntoSqpOut(BaseModel):
    """Punto del formato de inspección, servido desde el catálogo del backend."""

    orden: int
    codigo: str
    seccion: str
    texto: str


class CatalogoSqp(BaseModel):
    """Respuesta de ``GET /api/controles/sqp/catalogo``."""

    secciones: list[str]
    puntos: list[PuntoSqpOut]
    renglones_sustancias: int = Field(
        description="Cuántas sustancias caben en la tabla de la hoja impresa."
    )


class RespuestaSqpIn(BaseModel):
    """Respuesta a un punto de la inspección."""

    orden: int = Field(ge=0)
    valor: str = Field(description="'si', 'no' o 'na'.")
    observaciones: str | None = Field(default=None, max_length=2000)

    _limpiar_observaciones = field_validator("observaciones")(_texto_opcional)

    @field_validator("valor")
    @classmethod
    def _validar_valor(cls, valor: str) -> str:
        normalizado = valor.strip().lower()
        if normalizado not in VALORES_SQP:
            raise ValueError("La respuesta debe ser SI, NO o N/A.")
        return normalizado

    @model_validator(mode="after")
    def _exigir_observaciones_en_no(self) -> "RespuestaSqpIn":
        """Un "NO" sin explicación no le sirve a nadie que lea el reporte."""
        if self.valor == "no" and not self.observaciones:
            raise ValueError(
                "Cada punto contestado con NO necesita observaciones."
            )
        return self


class InspeccionSqpCrear(BaseModel):
    """Cuerpo de ``POST /api/controles/sqp``."""

    fecha: date
    area: str = Field(max_length=30)
    encargado: str = Field(min_length=1, max_length=150)
    cargo: str | None = Field(default=None, max_length=100)
    sustancias: str | None = Field(default=None, max_length=4000)
    respuestas: list[RespuestaSqpIn]

    _limpiar_encargado = field_validator("encargado")(_sin_espacios)
    _limpiar_cargo = field_validator("cargo")(_texto_opcional)
    _limpiar_sustancias = field_validator("sustancias")(_texto_opcional)

    @field_validator("area")
    @classmethod
    def _validar_area(cls, valor: str) -> str:
        limpio = valor.strip()
        if limpio not in AREAS_VALIDAS:
            raise ValueError("El área seleccionada no existe en el catálogo.")
        return limpio


class RespuestaSqpOut(BaseModel):
    """Respuesta guardada, con el texto del punto ya resuelto."""

    orden: int
    codigo: str
    seccion: str
    texto: str
    valor: str
    observaciones: str | None
    fotos: list[uuid.UUID] = Field(default_factory=list)


class InspeccionSqpResumen(BaseModel):
    """Fila del historial de inspecciones."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    fecha: date
    area: str
    area_label: str
    encargado: str
    responsable: str
    total_no: int = Field(description="Cuántos puntos salieron como NO.")
    creado_at: datetime


class InspeccionSqpDetalle(InspeccionSqpResumen):
    """Inspección completa, con sus respuestas y el listado de sustancias."""

    cargo: str | None
    sustancias: list[str]
    respuestas: list[RespuestaSqpOut]


# --- Listas de verificación (OK / NO OK) -----------------------------------


class PuntoControlOut(BaseModel):
    """Punto de una lista de verificación, servido desde el catálogo."""

    orden: int
    clave: str
    etiqueta: str
    etiqueta_ko: str | None = None
    categoria: str | None = None
    medicion: str | None = Field(
        default=None, description="Unidad de la lectura que pide el punto."
    )


class CampoFormatoOut(BaseModel):
    """Campo del encabezado o de una sección del formato."""

    clave: str
    etiqueta: str
    etiqueta_ko: str | None
    tipo: str
    opciones: list[str]
    unidad: str | None
    obligatorio: bool
    automatico: str | None = Field(
        default=None,
        description="'turno' u 'hora' si el servicio lo calcula solo; None si lo captura el operador.",
    )


class SeccionFormatoOut(BaseModel):
    """Bloque que va después de la lista de puntos."""

    clave: str
    titulo: str
    titulo_ko: str | None
    campos: list[CampoFormatoOut]


class CatalogoChecklist(BaseModel):
    """Respuesta de ``GET /api/controles/checklist/{control}/catalogo``."""

    clave: str
    titulo: str
    titulo_ko: str | None = None
    subtitulo: str | None
    puntos: list[PuntoControlOut]
    max_fotos: int = Field(description="Cuántas fotos admite un punto en NO OK.")
    encabezado: list[CampoFormatoOut] = Field(default_factory=list)
    secciones: list[SeccionFormatoOut] = Field(default_factory=list)
    por_inspeccion: bool = Field(
        description=(
            "True cuando el control es un formato por inspección: lleva "
            "encabezado y admite varios registros el mismo día."
        )
    )


class PuntoChecklistIn(BaseModel):
    """Cómo salió un punto. Viaja dentro del campo JSON del multipart."""

    orden: int = Field(ge=0)
    valor: str = Field(description="'ok' o 'no_ok'.")
    observaciones: str | None = Field(default=None, max_length=2000)
    medicion: str | None = Field(default=None, max_length=40)

    _limpiar_observaciones = field_validator("observaciones")(_texto_opcional)
    _limpiar_medicion = field_validator("medicion")(_texto_opcional)

    @field_validator("valor")
    @classmethod
    def _validar_valor(cls, valor: str) -> str:
        normalizado = valor.strip().lower()
        if normalizado not in VALORES_CHECKLIST:
            raise ValueError("La respuesta debe ser OK o NO OK.")
        return normalizado

    @model_validator(mode="after")
    def _exigir_observaciones(self) -> "PuntoChecklistIn":
        """Un NO OK sin explicación no le sirve a quien da seguimiento."""
        if self.valor == "no_ok" and not self.observaciones:
            raise ValueError("Cada punto marcado como NO OK necesita observaciones.")
        return self


class ChecklistCrear(BaseModel):
    """Parte estructurada de ``POST /api/controles/checklist/{control}``."""

    fecha: date
    puntos: list[PuntoChecklistIn]
    # Solo los formatos por inspección los usan; el servicio los valida contra
    # el catálogo, que es quien define qué campos existen.
    encabezado: dict[str, str] = Field(default_factory=dict)
    secciones: dict[str, dict[str, str]] = Field(default_factory=dict)


class PuntoChecklistOut(BaseModel):
    """Punto guardado, con el texto del catálogo ya resuelto."""

    orden: int
    clave: str
    etiqueta: str
    etiqueta_ko: str | None = None
    categoria: str | None = None
    valor: str
    observaciones: str | None
    medicion: str | None = None
    fotos: list[uuid.UUID]


class RegistroChecklistOut(BaseModel):
    """Fila del historial de un control."""

    id: uuid.UUID
    fecha: date
    puntos: list[PuntoChecklistOut]
    hay_hallazgos: bool = Field(description="Si algún punto salió como NO OK.")
    encabezado: dict[str, str] = Field(default_factory=dict)
    secciones: dict[str, dict[str, str]] = Field(default_factory=dict)
    responsable: str
    creado_at: datetime


# --- Pláticas diarias de seguridad -----------------------------------------


class AreaPlaticaOut(BaseModel):
    """Área del formato de pláticas."""

    clave: str
    etiqueta: str


class PlaticaCrear(BaseModel):
    """Parte estructurada de ``POST /api/controles/platicas``."""

    fecha: date
    tema: str = Field(min_length=1, max_length=300)
    areas: list[str] = Field(min_length=1)

    _limpiar_tema = field_validator("tema")(_sin_espacios)

    @field_validator("areas")
    @classmethod
    def _validar_areas(cls, areas: list[str]) -> list[str]:
        limpias = [area.strip().lower() for area in areas]

        for area in limpias:
            if area not in CLAVES_AREAS_PLATICAS:
                raise ValueError("Un área seleccionada no existe en el catálogo.")

        # Sin repetidas: la restricción de la base rechazaría el registro
        # entero con un error críptico.
        return list(dict.fromkeys(limpias))


class PlaticaOut(BaseModel):
    """Fila del historial de pláticas."""

    id: uuid.UUID
    fecha: date
    tema: str
    areas: list[AreaPlaticaOut]
    fotos: list[uuid.UUID]
    responsable: str
    creado_at: datetime


# --- Cierre de hallazgos e incidencias -------------------------------------


def _hora_valida(valor: str) -> str:
    """Comprueba el formato ``HH:MM`` que manda el input `type="time"`."""
    limpio = valor.strip()

    try:
        time.fromisoformat(limpio)
    except ValueError as exc:
        raise ValueError("La hora debe tener el formato HH:MM.") from exc

    return limpio[:5]


class CierreCrear(BaseModel):
    """Parte estructurada de ``POST``/``PUT`` de un cierre de hallazgo.

    Viaja como JSON dentro del multipart, igual que ``puntos`` en el registro
    de una lista de verificación: el cuerpo trae también las evidencias.
    """

    hora_hallazgo: str
    ubicacion: str = Field(min_length=1, max_length=200)
    accion_inmediata: str = Field(min_length=1, max_length=2000)
    responsable_accion: str = Field(min_length=1, max_length=150)
    hora_cierre: str
    # Lo único opcional: solo se llena si algo quedó sin resolver.
    accion_pendiente: str | None = Field(default=None, max_length=2000)

    _limpiar_ubicacion = field_validator("ubicacion")(_sin_espacios)
    _limpiar_accion = field_validator("accion_inmediata")(_sin_espacios)
    _limpiar_responsable = field_validator("responsable_accion")(_sin_espacios)
    _limpiar_pendiente = field_validator("accion_pendiente")(_texto_opcional)

    _validar_hallazgo = field_validator("hora_hallazgo")(_hora_valida)
    _validar_cierre = field_validator("hora_cierre")(_hora_valida)


class HallazgoOut(BaseModel):
    """Un problema de la hoja, ya normalizado entre los tres controles."""

    orden: int | None = Field(
        description="Punto dentro de la hoja; None en Rayser, que no los tiene."
    )
    etiqueta: str
    observaciones: str | None
    fotos: list[uuid.UUID]


class CierreOut(BaseModel):
    """Un cierre guardado."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    hora_hallazgo: str
    ubicacion: str
    accion_inmediata: str
    responsable_accion: str
    hora_cierre: str
    accion_pendiente: str | None
    responsable: str
    creado_at: datetime
    actualizado_at: datetime | None
    fotos: list[uuid.UUID] = Field(
        default_factory=list, description="Evidencias de la verificación."
    )


class DetalleCierre(BaseModel):
    """Lo que necesita el modal: los problemas y el cierre, si ya lo tiene."""

    control: str
    registro_id: uuid.UUID
    fecha: date
    hallazgos: list[HallazgoOut]
    cierre: CierreOut | None


class IncidenciaOut(BaseModel):
    """Un renglón de la pestaña de Incidencias."""

    control: str
    registro_id: uuid.UUID
    fecha: date
    identificacion: str = Field(
        description="Lo que distingue la hoja: el área, el tablero, el turno."
    )
    total_hallazgos: int
    responsable: str
    estado: str = Field(description="'pendiente' o 'cerrado'.")
    cierre: CierreOut | None


# --- PCI MTTO: mantenimiento del sistema contra incendios -------------------


class RegistroPciMttoOut(BaseModel):
    """Un renglón de la tabla del control.

    No lleva el documento adjunto, solo su nombre y su tamaño: son hasta 10 MB
    por registro y el listado de un año trae doce.
    """

    id: uuid.UUID
    anio: int
    mes: int
    #: Fecha del mantenimiento. Nula cuando el mes lo cerró el sistema.
    fecha: date | None
    realizado: bool
    motivo: str | None
    #: La levantó la vigilancia automática y nadie la ha explicado todavía si
    #: además ``motivo`` viene nulo.
    automatico: bool
    tiene_reporte: bool
    reporte_nombre: str | None
    reporte_tamano: int | None
    responsable: str
    fotos: list[uuid.UUID] = Field(default_factory=list)
    creado_at: datetime
    actualizado_at: datetime | None


class MesPendientePci(BaseModel):
    """Un mes que el sistema cerró y sigue sin explicación."""

    anio: int
    mes: int


class ListadoPciMtto(BaseModel):
    """Todo lo que la pestaña necesita para dibujarse, en una sola petición.

    Los registros del año, los años que existen para el filtro y los meses sin
    explicar. Van juntos porque abrir la pestaña necesita las tres cosas a la
    vez y tres peticiones en cascada se notan en la laptop de planta.
    """

    anio: int
    registros: list[RegistroPciMttoOut]
    anios: list[int]
    pendientes: list[MesPendientePci]
    #: Desde cuándo vigila el control. Viaja para que el panel no tenga que
    #: repetir la constante del catálogo y pueda decir "todavía no arranca"
    #: en lugar de ofrecer un mes que el servidor va a rechazar.
    primer_mes: MesPendientePci


class AvisoPciMtto(BaseModel):
    """Un mes sin explicar, para la campana del encabezado."""

    id: str = Field(description="'AAAA-MM', estable entre peticiones.")
    anio: int
    mes: int
    meses_de_retraso: int


class AvisosPciMtto(BaseModel):
    """Lo que la campana dibuja del control PCI MTTO.

    Sin textos: el backend no traduce interfaz (regla 6 del CLAUDE.md). El
    panel arma la frase con `t()` y el nombre del mes con `Intl`.
    """

    total: int
    avisos: list[AvisoPciMtto]


class MotivoPciMtto(BaseModel):
    """El motivo por el que un mes no tuvo mantenimiento."""

    motivo: str = Field(min_length=1, max_length=2000)

    @field_validator("motivo")
    @classmethod
    def _con_contenido(cls, valor: str) -> str:
        limpio = valor.strip()
        if not limpio:
            raise ValueError("Captura el motivo por el que no se realizó.")
        return limpio


# --- Control de insumos ----------------------------------------------------


class InsumoParaControl(BaseModel):
    """Un insumo tal como lo ve el desplegable de captura.

    **Deliberadamente más pobre que `InsumoOut`.** Este endpoint es un puente
    entre módulos: le sirve datos del catálogo a quien solo tiene el permiso
    `controles` y que por su vía normal recibiría 403. Devolver el schema del
    catálogo le entregaría de propina proveedor, ubicación, mínimo, máximo y el
    semáforo, que no le tocan. Aquí van los cinco campos que la captura
    necesita, y la existencia es uno de ellos: quien entrega tiene que ver
    cuánto hay antes de teclear.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    codigo: str
    descripcion: str
    unidad_medida: str
    existencia: int


class CatalogoControlInsumos(BaseModel):
    """Lo que la pestaña necesita para dibujar sus selectores.

    Las unidades parciales viajan desde el servidor porque son las que deciden
    si aparece la pregunta de "¿se terminó?": con la lista escrita a mano en el
    panel, agregar una unidad nueva dejaría de preguntar sin que nada fallara.
    """

    areas: list[AreaOut]
    unidades_parciales: list[str]


class ControlInsumoCrear(BaseModel):
    """Una salida de almacén tal como la captura el panel.

    Solo viaja el `insumo_id`, nunca el código: el desplegable obliga a elegir
    una fila concreta, así que aquí no existe la ambigüedad código↔descripción
    que la captura de recepciones tiene que desactivar a mano.
    """

    insumo_id: uuid.UUID
    entregado_a: str = Field(min_length=1, max_length=150)
    area: str = Field(max_length=50)
    #: El tope no es una regla de negocio: es la defensa contra el
    #: desbordamiento del INTEGER de PostgreSQL, igual que en el catálogo.
    consumo: int = Field(ge=1, le=TOPE_EXISTENCIA)
    #: `None` cuando la unidad no lo pregunta. Nunca por omisión: un "no se
    #: terminó" implícito descontaría 0 en silencio, y eso no se nota hasta el
    #: conteo físico.
    termino: bool | None = None

    @field_validator("entregado_a")
    @classmethod
    def _con_nombre(cls, valor: str) -> str:
        limpio = valor.strip()
        if not limpio:
            raise ValueError("Escribe a quién se le entrega el insumo.")
        return limpio

    @field_validator("area")
    @classmethod
    def _validar_area(cls, valor: str) -> str:
        limpio = valor.strip()
        if limpio not in AREAS_VALIDAS:
            raise ValueError("El área no es válida.")
        return limpio


class RegistroControlInsumoOut(BaseModel):
    """Un renglón del historial.

    `area_etiqueta` la resuelve el servidor: en la base el área va sin acentos
    y el panel pinta, no deduce.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    fecha: date
    codigo: str
    descripcion: str
    unidad_medida: str
    entregado_a: str
    area: str
    area_etiqueta: str
    consumo: int
    descontado: int
    termino: bool | None
    responsable: str
    creado_at: datetime


# --- Extintores ------------------------------------------------------------


class ExtintorBase(BaseModel):
    """Los cinco campos de la ficha, más el folio que la identifica."""

    folio: str = Field(min_length=1, max_length=20)
    modelo: str = Field(min_length=1, max_length=100)
    capacidad: str = Field(min_length=1, max_length=50)
    tipo: str = Field(max_length=10)
    ubicacion: str = Field(min_length=1, max_length=150)
    vencimiento: date

    _limpiar = field_validator(
        "folio", "modelo", "capacidad", "ubicacion", mode="after"
    )(_sin_espacios)

    @field_validator("folio")
    @classmethod
    def _con_folio(cls, valor: str) -> str:
        limpio = valor.strip()
        if not limpio:
            raise ValueError(
                "El folio es obligatorio: es lo que distingue a dos extintores "
                "del mismo modelo en la misma área."
            )
        return limpio

    @field_validator("tipo")
    @classmethod
    def _validar_tipo(cls, valor: str) -> str:
        limpio = valor.strip()
        if limpio not in TIPOS_EXTINTOR_VALIDOS:
            raise ValueError(
                "El tipo de extintor no es válido. Usa uno de: "
                + ", ".join(TIPOS_EXTINTOR)
                + "."
            )
        return limpio


class ExtintorCrear(ExtintorBase):
    """Alta de una ficha."""


class ExtintorActualizar(ExtintorBase):
    """Edición de una ficha existente."""


class ExtintorOut(BaseModel):
    """Un extintor tal como sale de la API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    folio: str
    modelo: str
    capacidad: str
    tipo: str
    ubicacion: str
    vencimiento: date


class FilaExtintor(BaseModel):
    """Un renglón de la tabla, con lo que decide qué botones se pintan.

    `estado`, `revisado_hoy`, `anomalias_hoy` y `cierre_hecho` los calcula el
    servidor en la misma consulta del listado: el panel pinta, no deduce, y
    pedirlos por renglón serían cincuenta peticiones por página.
    """

    extintor: ExtintorOut
    estado: str
    revisado_hoy: bool
    anomalias_hoy: int | None = None
    revision_id: uuid.UUID | None = None
    cierre_hecho: bool = False


class ExtintoresPaginados(BaseModel):
    """Página del registro, con lo que necesita el paginador y la cabecera."""

    total: int
    page: int
    size: int
    items: list[FilaExtintor]
    #: «Revisados hoy: N de M». Sale de un conteo en SQL sobre TODO el
    #: inventario, no sobre la página que se está viendo.
    revisados_hoy: int
    registrados: int


class PuntoRevisionIn(BaseModel):
    """Un punto contestado de la revisión diaria."""

    orden: int = Field(ge=0)
    valor: str
    observaciones: str | None = None

    _limpiar_observaciones = field_validator("observaciones")(_texto_opcional)

    @field_validator("valor")
    @classmethod
    def _validar_valor(cls, valor: str) -> str:
        normalizado = valor.strip().lower()
        if normalizado not in VALORES_CHECKLIST:
            raise ValueError("La respuesta debe ser CONFORME o INCONFORME.")
        return normalizado

    @model_validator(mode="after")
    def _exigir_observaciones(self) -> "PuntoRevisionIn":
        if self.valor == "no_ok" and not self.observaciones:
            raise ValueError(
                "Cada punto marcado como INCONFORME necesita observaciones."
            )
        return self


class PuntoRevisionOut(BaseModel):
    """Un punto ya guardado, con su etiqueta resuelta y sus fotos."""

    orden: int
    clave: str
    etiqueta: str
    valor: str
    observaciones: str | None = None
    fotos: list[uuid.UUID] = Field(default_factory=list)


class RevisionExtintorOut(BaseModel):
    """La revisión de un día."""

    id: uuid.UUID
    extintor_id: uuid.UUID | None
    folio: str
    modelo: str
    tipo: str
    ubicacion: str
    fecha: date
    anomalias: int
    responsable: str
    creado_at: datetime
    puntos: list[PuntoRevisionOut]


class CatalogoExtintores(BaseModel):
    """Lo que la pestaña necesita para dibujar el formulario de revisión.

    Los doce puntos y los tipos salen del backend: el panel nunca los tiene
    escritos a mano, así que agregar uno no puede dejar la pantalla a medias.
    """

    puntos: list[PuntoControlOut]
    tipos: list[str]
    max_fotos: int
    #: Cuántas fichas admite el registro, para que la pantalla lo diga antes de
    #: que el alta falle.
    maximo: int


class AvisoExtintor(BaseModel):
    """Un extintor por vencer, para la campana del encabezado."""

    id: uuid.UUID
    folio: str
    ubicacion: str
    fecha_vencimiento: date
    dias: int = Field(description="Días que faltan; negativo si la fecha ya pasó.")
    vencido: bool


class AvisosExtintores(BaseModel):
    """Resumen para la campana.

    Sin textos: el backend no traduce interfaz (regla 6). El panel arma la
    frase con `t()` y la fecha con `Intl`.
    """

    total: int
    vencidos: int
    avisos: list[AvisoExtintor]


class EtiquetasExtintores(BaseModel):
    """Los extintores cuya etiqueta QR se va a imprimir.

    Viaja en el cuerpo y no en la query porque la cola puede llevar los 160
    identificadores y la URL se pasaría del búfer de cabeceras de Nginx.
    """

    ids: list[uuid.UUID] = Field(min_length=1, max_length=MAX_EXTINTORES)
