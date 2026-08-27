"""Schemas del catálogo de insumos de seguridad."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.constants import (
    CATEGORIAS_INSUMO,
    CATEGORIAS_VALIDAS,
    UNIDADES_MEDIDA,
    UNIDADES_VALIDAS,
)


def _texto(valor: str) -> str:
    """Recorta espacios y colapsa los interiores."""
    return " ".join(valor.split())


def _texto_opcional(valor: str | None) -> str | None:
    """Igual que ``_texto``, pero deja en ``None`` lo que quede vacío."""
    if valor is None:
        return None
    limpio = _texto(valor)
    return limpio or None


def _validar_categoria(valor: str) -> str:
    """Rechaza categorías fuera del catálogo."""
    limpio = _texto(valor)
    if limpio not in CATEGORIAS_VALIDAS:
        raise ValueError(
            "La categoría no es válida. Usa una de: "
            + ", ".join(CATEGORIAS_INSUMO)
            + "."
        )
    return limpio


def _validar_unidad_medida(valor: str) -> str:
    """Rechaza unidades de medida fuera del catálogo."""
    limpio = _texto(valor)
    if limpio not in UNIDADES_VALIDAS:
        raise ValueError(
            "La unidad de medida no es válida. Usa una de: "
            + ", ".join(UNIDADES_MEDIDA)
            + "."
        )
    return limpio


class _InsumoBase(BaseModel):
    """Campos comunes al alta y a la edición."""

    codigo: str = Field(min_length=1, max_length=150)
    descripcion: str | None = Field(default=None, max_length=2000)
    categoria: str = Field(max_length=30)
    unidad_medida: str = Field(max_length=10)
    proveedor: str | None = Field(default=None, max_length=150)
    ubicacion: str | None = Field(default=None, max_length=150)
    cantidad: int = Field(default=0, ge=0)
    minimo: int = Field(default=0, ge=0)
    maximo: int = Field(default=0, ge=0)

    _limpiar_categoria = field_validator("categoria")(_validar_categoria)
    _limpiar_unidad_medida = field_validator("unidad_medida")(_validar_unidad_medida)
    _limpiar_opcionales = field_validator("descripcion", "proveedor", "ubicacion")(
        _texto_opcional
    )

    @field_validator("codigo")
    @classmethod
    def _limpiar_codigo(cls, valor: str) -> str:
        limpio = _texto(valor)
        if not limpio:
            raise ValueError("El código del insumo es obligatorio.")
        return limpio

    @model_validator(mode="after")
    def _revisar_rango(self) -> "_InsumoBase":
        """Un rango invertido rompería el semáforo en silencio.

        La base tiene el mismo CHECK; aquí se repite para que el usuario vea
        un 422 con el motivo en vez de un 500 de PostgreSQL.
        """
        if self.maximo < self.minimo:
            raise ValueError(
                "El máximo de inventario no puede ser menor que el mínimo."
            )
        return self


class InsumoCrear(_InsumoBase):
    """Alta de un insumo desde el panel."""


class InsumoActualizar(_InsumoBase):
    """Edición de un insumo existente."""


class InsumoOut(BaseModel):
    """Insumo tal como sale de la API.

    ``estado`` lo calcula el servidor (ver ``models/insumo.estado_insumo``);
    el frontend no lo deduce, solo lo pinta.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    codigo: str
    descripcion: str | None = None
    categoria: str
    unidad_medida: str
    proveedor: str | None = None
    ubicacion: str | None = None
    cantidad: int
    minimo: int
    maximo: int
    estado: str
    creado_at: datetime
    actualizado_at: datetime | None = None


class InsumosPaginados(BaseModel):
    """Página del catálogo, con el total para armar el paginador."""

    total: int
    page: int
    size: int
    items: list[InsumoOut]


class ErrorImportacionInsumo(BaseModel):
    """Un problema encontrado en una fila del Excel."""

    fila: int
    mensaje: str


class ResultadoImportacionInsumos(BaseModel):
    """Resumen de una carga masiva.

    Los repetidos se omiten en vez de actualizarse: así un archivo viejo no
    puede pisar existencias que ya se corrigieron en el panel.
    """

    creados: int
    omitidos: int
    errores: list[ErrorImportacionInsumo]


class CatalogoCategorias(BaseModel):
    """Categorías válidas, para el selector del formulario y el filtro."""

    categorias: list[str]


class CatalogoUnidades(BaseModel):
    """Unidades de medida válidas, para el selector del formulario."""

    unidades: list[str]
