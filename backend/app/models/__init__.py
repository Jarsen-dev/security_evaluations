"""Modelos SQLAlchemy.

Todos los modelos se importan aquí para que ``alembic/env.py`` los registre
en ``Base.metadata`` al autogenerar migraciones.
"""

from app.db.base import Base
from app.models.admin_user import AdminUser
from app.models.bitacora import Bitacora
from app.models.control import (
    AreaPlatica,
    CierreHallazgo,
    FotoControl,
    InspeccionSqp,
    PlaticaEsh,
    PuntoChecklist,
    RegistroChecklist,
    RegistroControlInsumos,
    RegistroPciMtto,
    RegistroRayser,
    RespuestaSqp,
)
from app.models.cuestionario import Cuestionario, Opcion, Pregunta
from app.models.estudio import Estudio
from app.models.extintor import (
    Extintor,
    PuntoRevisionExtintor,
    RevisionExtintor,
)
from app.models.insumo import Insumo
from app.models.intento import Intento, Respuesta
from app.models.meta_area import MetaArea
from app.models.recepcion import (
    EjemploPlantillaRecepcion,
    FotoRecepcion,
    ItemRecepcion,
    PlantillaRecepcion,
    Recepcion,
    SesionQrRecepcion,
)
from app.models.rondin import EnvioReporteRondin, EscaneoRondin, PuntoRondin

__all__ = [
    "AdminUser",
    "AreaPlatica",
    "Base",
    "Bitacora",
    "CierreHallazgo",
    "Cuestionario",
    "EjemploPlantillaRecepcion",
    "Estudio",
    "Extintor",
    "EnvioReporteRondin",
    "EscaneoRondin",
    "FotoControl",
    "FotoRecepcion",
    "InspeccionSqp",
    "Insumo",
    "Intento",
    "ItemRecepcion",
    "MetaArea",
    "Opcion",
    "PlantillaRecepcion",
    "PlaticaEsh",
    "Pregunta",
    "PuntoChecklist",
    "PuntoRevisionExtintor",
    "PuntoRondin",
    "Recepcion",
    "RegistroChecklist",
    "RegistroControlInsumos",
    "RegistroPciMtto",
    "RegistroRayser",
    "RevisionExtintor",
    "Respuesta",
    "RespuestaSqp",
    "SesionQrRecepcion",
]
