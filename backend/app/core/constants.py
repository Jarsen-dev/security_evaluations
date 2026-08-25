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
    "catalogo",
    "rondines",
)

# Longitud mínima de las contraseñas del panel. Vive aquí, y no en `cli.py`
# ni en los schemas, para que la CLI y el alta desde la interfaz apliquen
# exactamente la misma regla.
LONGITUD_MINIMA_CONTRASENA: Final[int] = 8


# --- Catálogo de insumos de seguridad --------------------------------------

# Categorías del catálogo. Se definen aquí y en ningún otro lado: el frontend
# las obtiene por ``GET /api/catalogo/categorias``, igual que las áreas, para
# que no queden escritas a mano en dos lugares que se desincronizan.
CATEGORIAS_INSUMO: Final[tuple[str, ...]] = (
    "Medicamento",
    "EPP",
    "Señalización",
    "Extintores",
    "Otros",
)

# Valores aceptados al dar de alta o importar un insumo.
CATEGORIAS_VALIDAS: Final[frozenset[str]] = frozenset(CATEGORIAS_INSUMO)


# --- Rondines de seguridad -------------------------------------------------

# Un turno dura 12 horas y arranca a las 07:30. El día que se elige en el panel
# es el de INICIO del turno, no el del calendario: la noche del 25 al 26 se
# consulta seleccionando el 25.
HORA_INICIO_TURNO: Final[int] = 7
MINUTO_INICIO_TURNO: Final[int] = 30
HORAS_TURNO: Final[int] = 12

#: Rondines por turno. Cada uno cubre un bloque de dos horas.
RONDINES_POR_TURNO: Final[int] = 6

# Silencio a partir del cual se considera que empezó un recorrido nuevo. Un
# recorrido completo de la planta toma bastante menos que esto.
GAP_RECORRIDO_MINUTOS: Final[int] = 30
