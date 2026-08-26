"""Schemas de los estudios y capacitaciones (panel de administración).

Como los de los controles, exigen sesión: nada de aquí se sirve sin
autenticación. Los validadores lanzan su ``ValueError`` con el mensaje ya en
español, que es como el manejador de errores lo conserva tal cual (regla 6).
"""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.estudios_catalogo import (
    APROBACIONES,
    CLAVES_APROBACION,
    CLAVES_ESTATUS,
    CLAVES_PRIORIDAD,
    CLAVES_TIPO,
    CLAVES_VENCIMIENTO,
    CLAVES_VIGENCIA,
    ESTATUS,
    ESTATUS_CON_LINK,
    MAX_LINK,
    PRIORIDADES,
    TIPOS,
    VENCIMIENTOS,
    VENCIMIENTO_CON_FECHA,
    VIGENCIAS,
    OpcionEstudio,
)

# Esquemas que un enlace jamás debe traer. `javascript:` y `data:` ejecutan
# código en el navegador de quien haga clic desde la tabla, y el link lo
# captura un usuario del panel: se rechaza aquí, además de que el frontend
# solo dibuja un ancla para http y https.
ESQUEMAS_PROHIBIDOS: tuple[str, ...] = ("javascript:", "data:", "vbscript:")


def _sin_espacios(valor: str) -> str:
    return valor.strip()


def _texto_opcional(valor: str | None) -> str | None:
    if valor is None:
        return None
    limpio = valor.strip()
    return limpio or None


def _validar_clave(valor: str, validas: frozenset[str], campo: str) -> str:
    """Comprueba una clave contra el catálogo, con mensaje en español."""
    if valor not in validas:
        raise ValueError(f"El valor de {campo} no está en el catálogo.")
    return valor


class OpcionOut(BaseModel):
    """Una opción de un campo de selección, como la sirve el catálogo."""

    clave: str
    etiqueta: str = Field(description="Texto en español; el panel lo traduce.")
    corto: str = Field(description="Cómo se abrevia en la tabla y en el Excel.")
    semaforo: str = Field(description="'verde', 'amarillo', 'rojo', 'gris' o vacío.")
    numero: int | None = Field(description="Solo la prioridad: 1, 2 o 3.")

    @classmethod
    def desde(cls, opcion: OpcionEstudio) -> "OpcionOut":
        return cls(
            clave=opcion.clave,
            etiqueta=opcion.etiqueta,
            corto=opcion.texto_corto,
            semaforo=opcion.semaforo,
            numero=opcion.numero,
        )


class CatalogoEstudios(BaseModel):
    """Todas las opciones válidas, para que el panel no las tenga a mano."""

    vigencias: list[OpcionOut]
    prioridades: list[OpcionOut]
    tipos: list[OpcionOut]
    estatus: list[OpcionOut]
    vencimientos: list[OpcionOut]
    aprobaciones: list[OpcionOut]

    vencimiento_con_fecha: str = Field(
        description="Clave del vencimiento que habilita el campo de fecha."
    )
    estatus_con_link: str = Field(
        description="Clave del estatus que habilita el campo de link."
    )

    @classmethod
    def actual(cls) -> "CatalogoEstudios":
        return cls(
            vigencias=[OpcionOut.desde(o) for o in VIGENCIAS],
            prioridades=[OpcionOut.desde(o) for o in PRIORIDADES],
            tipos=[OpcionOut.desde(o) for o in TIPOS],
            estatus=[OpcionOut.desde(o) for o in ESTATUS],
            vencimientos=[OpcionOut.desde(o) for o in VENCIMIENTOS],
            aprobaciones=[OpcionOut.desde(o) for o in APROBACIONES],
            vencimiento_con_fecha=VENCIMIENTO_CON_FECHA,
            estatus_con_link=ESTATUS_CON_LINK,
        )


class EstudioCrear(BaseModel):
    """Alta o edición de un estudio. El mismo cuerpo sirve para las dos."""

    despacho: str = Field(min_length=1, max_length=150)
    estudio: str = Field(min_length=1, max_length=2000)
    estudio_ko: str | None = Field(default=None, max_length=2000)

    vigencia: str
    prioridad: str
    tipo: str
    estatus: str
    vencimiento: str
    fecha_vencimiento: date | None = None
    aprobado: str
    pagado: str
    link: str | None = Field(default=None, max_length=MAX_LINK)

    _limpiar = field_validator("despacho", "estudio")(_sin_espacios)
    _limpiar_opcional = field_validator("estudio_ko", "link")(_texto_opcional)

    @field_validator("vigencia")
    @classmethod
    def _vigencia_valida(cls, valor: str) -> str:
        return _validar_clave(valor, CLAVES_VIGENCIA, "vigencia")

    @field_validator("prioridad")
    @classmethod
    def _prioridad_valida(cls, valor: str) -> str:
        return _validar_clave(valor, CLAVES_PRIORIDAD, "prioridad")

    @field_validator("tipo")
    @classmethod
    def _tipo_valido(cls, valor: str) -> str:
        return _validar_clave(valor, CLAVES_TIPO, "IN/EX")

    @field_validator("estatus")
    @classmethod
    def _estatus_valido(cls, valor: str) -> str:
        return _validar_clave(valor, CLAVES_ESTATUS, "estatus")

    @field_validator("vencimiento")
    @classmethod
    def _vencimiento_valido(cls, valor: str) -> str:
        return _validar_clave(valor, CLAVES_VENCIMIENTO, "vencimiento")

    @field_validator("aprobado")
    @classmethod
    def _aprobado_valido(cls, valor: str) -> str:
        return _validar_clave(valor, CLAVES_APROBACION, "aprobado")

    @field_validator("pagado")
    @classmethod
    def _pagado_valido(cls, valor: str) -> str:
        return _validar_clave(valor, CLAVES_APROBACION, "pagado")

    @field_validator("link")
    @classmethod
    def _link_seguro(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        if valor.lower().replace(" ", "").startswith(ESQUEMAS_PROHIBIDOS):
            raise ValueError("El link debe apuntar a una ubicación, no a un script.")
        return valor

    @model_validator(mode="after")
    def _coherencia(self) -> "EstudioCrear":
        """Aplica las dos reglas que también sostiene la base.

        Los campos que no corresponden se descartan en vez de rechazarse: el
        formulario los esconde, así que si llegan es porque quedaron de una
        selección anterior, no porque alguien los haya querido guardar.
        """
        if self.vencimiento == VENCIMIENTO_CON_FECHA:
            if self.fecha_vencimiento is None:
                raise ValueError(
                    "Captura la fecha en la que vence el estudio."
                )
        else:
            self.fecha_vencimiento = None

        if self.estatus != ESTATUS_CON_LINK:
            self.link = None

        return self


class EstudioOut(BaseModel):
    """Un estudio tal como lo consume la tabla del panel."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    despacho: str
    estudio: str
    estudio_ko: str | None
    vigencia: str
    prioridad: str
    tipo: str
    estatus: str
    vencimiento: str
    fecha_vencimiento: date | None
    aprobado: str
    pagado: str
    link: str | None
    responsable: str
    creado_at: datetime
    actualizado_at: datetime | None


class AvisoVencimiento(BaseModel):
    """Un estudio que vence pronto o que ya venció."""

    id: uuid.UUID
    estudio: str
    despacho: str
    fecha_vencimiento: date
    dias: int = Field(
        description="Días que faltan; negativo si la fecha ya pasó."
    )
    vencido: bool


class AvisosOut(BaseModel):
    """Lo que dibuja la campana del encabezado."""

    total: int
    vencidos: int
    avisos: list[AvisoVencimiento]
