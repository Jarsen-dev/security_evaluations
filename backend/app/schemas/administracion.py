"""Schemas de la pestaña de Administración: usuarios, bitácora y mantenimiento."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.constants import LONGITUD_MINIMA_CONTRASENA, MODULOS_PERMISO


class PermisoModulo(BaseModel):
    """Lo que puede hacer un usuario dentro de un módulo.

    Estar presente en el diccionario de permisos ya otorga ver y crear;
    ``editar`` agrega modificar y eliminar.
    """

    editar: bool = False


#: Permisos por módulo. Un módulo ausente significa "sin acceso a esa pestaña".
Permisos = dict[str, PermisoModulo]


def _validar_modulos(permisos: Permisos) -> Permisos:
    """Rechaza módulos que no existen.

    Sin esto, una errata como ``cuestionario`` (en singular) se guardaría sin
    protestar y el usuario se quedaría sin la pestaña, con un JSON que a
    simple vista se ve bien.
    """
    desconocidos = sorted(set(permisos) - set(MODULOS_PERMISO))
    if desconocidos:
        raise ValueError(
            "Estos módulos no existen: " + ", ".join(desconocidos) + "."
        )
    return permisos


def _validar_contrasena(valor: str) -> str:
    """Aplica la misma longitud mínima que la CLI."""
    if len(valor) < LONGITUD_MINIMA_CONTRASENA:
        raise ValueError(
            f"La contraseña debe tener al menos {LONGITUD_MINIMA_CONTRASENA} "
            f"caracteres."
        )
    return valor


def _validar_username(valor: str) -> str:
    """Limpia el nombre de usuario.

    Se conservan las mayúsculas tal como se escriben: el login compara el
    valor exacto, y normalizar aquí le cambiaría el usuario a quien ya tiene
    una cuenta creada antes de que existiera esta pantalla.
    """
    limpio = valor.strip()
    if not limpio:
        raise ValueError("El usuario es obligatorio.")
    if " " in limpio:
        raise ValueError("El usuario no puede contener espacios.")
    return limpio


class UsuarioCrear(BaseModel):
    """Alta de un usuario desde el panel."""

    nombre: str = Field(min_length=1, max_length=120)
    username: str = Field(min_length=1, max_length=50)
    email: EmailStr
    password: str = Field(max_length=200)
    permisos: Permisos = Field(default_factory=dict)

    _normalizar_username = field_validator("username")(_validar_username)
    _revisar_password = field_validator("password")(_validar_contrasena)
    _revisar_permisos = field_validator("permisos")(_validar_modulos)

    @field_validator("nombre")
    @classmethod
    def _limpiar_nombre(cls, valor: str) -> str:
        limpio = valor.strip()
        if not limpio:
            raise ValueError("El nombre es obligatorio.")
        return limpio


class UsuarioActualizar(BaseModel):
    """Edición de un usuario existente.

    ``password`` es opcional: si llega vacío o ausente, la contraseña actual
    se conserva. Es lo que se espera al abrir el modal solo para corregir un
    correo o ajustar permisos.
    """

    nombre: str = Field(min_length=1, max_length=120)
    username: str = Field(min_length=1, max_length=50)
    email: EmailStr
    password: str | None = Field(default=None, max_length=200)
    permisos: Permisos = Field(default_factory=dict)

    _normalizar_username = field_validator("username")(_validar_username)
    _revisar_permisos = field_validator("permisos")(_validar_modulos)

    @field_validator("nombre")
    @classmethod
    def _limpiar_nombre(cls, valor: str) -> str:
        limpio = valor.strip()
        if not limpio:
            raise ValueError("El nombre es obligatorio.")
        return limpio

    @field_validator("password")
    @classmethod
    def _revisar_password(cls, valor: str | None) -> str | None:
        if valor is None or valor == "":
            return None
        return _validar_contrasena(valor)


class UsuarioEstado(BaseModel):
    """Activación o desactivación de una cuenta."""

    activo: bool


class UsuarioOut(BaseModel):
    """Usuario tal como sale de la API.

    Nunca declara ``password_hash``: lo que no está en el schema no se puede
    filtrar por descuido (misma lógica que los schemas públicos).
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nombre: str
    username: str
    email: str | None = None
    activo: bool
    es_superadmin: bool
    permisos: dict[str, PermisoModulo]
    created_at: datetime
    last_login_at: datetime | None = None


class BitacoraFila(BaseModel):
    """Un renglón de actividad."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    creado_at: datetime
    usuario_id: uuid.UUID | None = None
    username: str
    accion: str
    modulo: str
    descripcion: str
    metodo: str
    ruta: str
    estado: int
    ip: str | None = None


class BitacoraPaginada(BaseModel):
    """Página de la bitácora, con el total para armar el paginador."""

    total: int
    page: int
    size: int
    items: list[BitacoraFila]


class AccesoPgAdmin(BaseModel):
    """Un botón de la pestaña de Mantenimiento."""

    #: ``local`` o ``produccion``; el panel lo usa como clave de traducción.
    entorno: str
    url: str
    disponible: bool


class MantenimientoOut(BaseModel):
    """Accesos a pgAdmin y las credenciales guardadas en el proyecto.

    La contraseña viaja al navegador del superadministrador a propósito: es
    justo lo que hace útil el botón de "copiar credenciales". Queda anotado
    como riesgo aceptado en SEGURIDAD.md.
    """

    accesos: list[AccesoPgAdmin]
    email: str
    password: str
    configurado: bool
