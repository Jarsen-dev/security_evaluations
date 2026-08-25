"""Schemas de los controles ESH (panel de administración).

Estos endpoints exigen sesión: nada de aquí se sirve sin autenticación. Los
schemas del formulario público siguen viviendo aparte, en
``app.schemas.publico`` (ver regla 1 del CLAUDE.md).
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.constants import AREAS_VALIDAS
from app.core.controles_catalogo import (
    CLAVES_AREAS_PLATICAS,
    VALORES_CHECKLIST,
    VALORES_SQP,
)


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


class SeccionFormatoOut(BaseModel):
    """Bloque que va después de la lista de puntos."""

    clave: str
    titulo: str
    titulo_ko: str | None
    campos: list[CampoFormatoOut]
    solo_con_hallazgos: bool


class CatalogoChecklist(BaseModel):
    """Respuesta de ``GET /api/controles/checklist/{control}/catalogo``."""

    clave: str
    titulo: str
    titulo_ko: str | None = None
    subtitulo: str | None
    puntos: list[PuntoControlOut]
    max_fotos: int = Field(description="Cuántas fotos admite un punto en NO OK.")
    estilo_valores: str = Field(description="'ok_no_ok' o 'si_no'.")
    encabezado: list[CampoFormatoOut] = Field(default_factory=list)
    secciones: list[SeccionFormatoOut] = Field(default_factory=list)
    nota: str | None = None
    nota_ko: str | None = None
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
