"""Constantes de dominio.

Las áreas se definen aquí y en ningún otro lado: el frontend las obtiene por
``GET /api/areas`` para que nunca queden hardcodeadas en dos lugares.
"""

from typing import Final, NamedTuple


class Area(NamedTuple):
    """Área de la planta.

    ``value`` se guarda en la base de datos sin acentos (evita problemas de
    codificación e índices); ``label`` es lo que ve el usuario.
    """

    value: str
    label: str


AREAS: Final[tuple[Area, ...]] = (
    Area("Ensamble", "Ensamble"),
    Area("EPS", "EPS"),
    Area("Moldes", "Moldes"),
    Area("Mantenimiento", "Mantenimiento"),
    Area("Embarques", "Embarques"),
    Area("Calidad", "Calidad"),
    Area("Almacen", "Almacén"),
    Area("Oficinas", "Oficinas"),
)

# Valores aceptados al crear un intento.
AREAS_VALIDAS: Final[frozenset[str]] = frozenset(area.value for area in AREAS)

# Mapa de despliegue para exportaciones y reportes generados en el backend.
ETIQUETAS_AREA: Final[dict[str, str]] = {area.value: area.label for area in AREAS}


def etiqueta_area(valor: str) -> str:
    """Devuelve la etiqueta con acento de un área.

    Si el valor no está en el catálogo (por ejemplo, un área eliminada del
    catálogo pero aún presente en intentos históricos), regresa el valor tal
    cual en vez de fallar.
    """
    return ETIQUETAS_AREA.get(valor, valor)


# --- Usuarios y permisos ---------------------------------------------------

# Módulos sobre los que se otorgan permisos. Coinciden con las pestañas del
# panel, que es como el administrador razona sobre ellos: "esta persona entra
# a Controles, esta otra no".
#
# Inventario todavía no tiene endpoints propios; se declara desde ahora para
# que el permiso exista el día que los tenga y no haya que migrar los JSON
# de los usuarios ya capturados.
MODULOS_PERMISO: Final[tuple[str, ...]] = (
    "cuestionarios",
    "controles",
    "inventario",
)

# Longitud mínima de las contraseñas del panel. Vive aquí, y no en `cli.py`
# ni en los schemas, para que la CLI y el alta desde la interfaz apliquen
# exactamente la misma regla.
LONGITUD_MINIMA_CONTRASENA: Final[int] = 8
