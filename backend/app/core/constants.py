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
    "estudios",
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
    "Enfermería",
    "EPP",
    "Señalización",
    "Extintores",
    # "Otros" va al final a propósito: es el cajón de sastre y en el selector
    # se lee como la última opción, no como una más.
    "Otros",
)

# Valores aceptados al dar de alta o importar un insumo.
CATEGORIAS_VALIDAS: Final[frozenset[str]] = frozenset(CATEGORIAS_INSUMO)

# Unidades de medida del catálogo. Mismo patrón que las categorías: catálogo
# fijo aquí, servido por ``GET /api/catalogo/unidades`` para que el frontend
# nunca las tenga escritas a mano.
UNIDADES_MEDIDA: Final[tuple[str, ...]] = ("TAB", "ML", "PZA", "GR", "MTS")
UNIDADES_VALIDAS: Final[frozenset[str]] = frozenset(UNIDADES_MEDIDA)

# Unidades que se consumen a granel. Lo que el inventario cuenta son PIEZAS —el
# tubo, el frasco, el rollo—, así que usar 20 GR de un tubo de 60 no baja
# ninguna pieza: la baja se produce cuando el tubo se acaba. Por eso el control
# de insumos pregunta si el producto se terminó antes de tocar la existencia.
#
# Va aquí y se sirve por la API, igual que las áreas y las categorías: el panel
# necesita saber cuándo preguntar, y con la lista escrita a mano allá, agregar
# una unidad nueva dejaría de preguntar sin que nada fallara.
UNIDADES_PARCIALES: Final[frozenset[str]] = frozenset({"GR", "ML", "MTS"})

# Topes de los números del inventario. No son una regla de negocio: son la
# defensa contra el desbordamiento del INTEGER de PostgreSQL. La entrada de una
# recepción es `cajas x piezas_por_empaque`, y sin acotar los dos factores el
# producto puede pasarse de int4; entonces la base responde "integer out of
# range" y el operador ve un 500 en crudo en lugar del mensaje en español.
# Acotados así, la partida más grande posible (10 000 cajas de 100 000 piezas)
# sigue cabiendo con holgura.
# Tope de la descripción del insumo. No es una regla de dominio: es lo que la
# hace indexable. La descripción entra al índice único junto con el código, y
# una entrada de btree no pasa de ~2704 bytes; con 2000 caracteres, un alta
# fallaría con "index row size exceeds maximum", que no es un IntegrityError y
# saldría como 500 en vez del 409 en español.
LONGITUD_DESCRIPCION: Final[int] = 300

TOPE_PIEZAS: Final[int] = 100_000
TOPE_EXISTENCIA: Final[int] = 100_000_000
TOPE_CAJAS_RECEPCION: Final[int] = 10_000


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
