"""Catálogo de los controles ESH: puntos de inspección y rangos de operación.

Mismo criterio que ``AREAS`` en ``constants.py``: los textos viven aquí y en
ningún otro lado. El frontend los obtiene por la API
(``/api/controles/sqp/catalogo``, ``/api/controles/checklist/{control}/catalogo``)
para que nunca queden escritos a mano en dos lugares.

Las preguntas se transcriben del formato en papel (hoja "Inspeccion de SQP" del
libro de inspecciones). Se conserva su numeración original **tal cual**, con sus
rarezas incluidas: hay dos puntos numerados ``2.2`` y el ``3.9`` aparece
intercalado antes del ``3.6``. El orden lo fija la posición en esta tupla, no el
código, justo para que esas rarezas no lo alteren.
"""

from decimal import Decimal
from typing import Final, Literal, NamedTuple

# --- Rayser: presión de los manómetros -------------------------------------
#
# La hoja en papel lo dice al pie: "La presión normal de los manómetros es de
# 130 psi". El semáforo abre 5 psi hacia cada lado.
RAYSER_NORMAL: Final[Decimal] = Decimal("130")
RAYSER_MINIMO: Final[Decimal] = Decimal("125")
RAYSER_MAXIMO: Final[Decimal] = Decimal("135")

# Tope de captura. No es el rango bueno, es lo que puede marcar el instrumento:
# un valor de 4 dígitos es un dedazo, no una lectura.
RAYSER_TOPE: Final[Decimal] = Decimal("300")

# Cuántos manómetros tiene el equipo.
RAYSER_MANOMETROS: Final[int] = 4

Semaforo = Literal["verde", "rojo", "naranja"]


def semaforo(valor: Decimal) -> Semaforo:
    """Clasifica la lectura de un manómetro.

    Verde dentro de 125–135 psi, rojo por debajo y naranja por encima. Se
    calcula siempre en el servidor: el cliente lo repite solo para pintar el
    formulario mientras se teclea.
    """
    if valor < RAYSER_MINIMO:
        return "rojo"
    if valor > RAYSER_MAXIMO:
        return "naranja"
    return "verde"


def fuera_de_rango(valores: list[Decimal]) -> bool:
    """``True`` si alguna lectura salió del rango normal.

    Cuando ocurre, el registro exige foto de evidencia y observaciones.
    """
    return any(semaforo(valor) != "verde" for valor in valores)


# --- Inspección de sustancias químicas peligrosas (SQP) --------------------


class PuntoSqp(NamedTuple):
    """Un punto de la inspección de SQP."""

    codigo: str
    seccion: str
    texto: str


SECCIONES_SQP: Final[tuple[str, ...]] = (
    "1. DOCUMENTACIÓN",
    "2. IDENTIFICACIÓN",
    "3. INSTALACIONES",
    "4. ALMACENAMIENTO",
)

PUNTOS_SQP: Final[tuple[PuntoSqp, ...]] = (
    PuntoSqp(
        "1.1",
        SECCIONES_SQP[0],
        "¿Cuenta con Hojas de Datos de Seguridad (MSDS) de las sustancias "
        "químicas en sitio?",
    ),
    PuntoSqp("1.2", SECCIONES_SQP[0], "¿Las MSDS se encuentran en el idioma español?"),
    PuntoSqp(
        "1.3", SECCIONES_SQP[0], "¿Cuentan con matriz de compatibilidad de materiales?"
    ),
    PuntoSqp(
        "1.4",
        SECCIONES_SQP[0],
        "¿Existen procedimientos para el manejo de sustancias químicas?",
    ),
    PuntoSqp("2.1", SECCIONES_SQP[1], "¿Hay señalización de la zona de almacenamiento?"),
    PuntoSqp(
        "2.2",
        SECCIONES_SQP[1],
        "¿Las sustancias químicas se encuentran claramente identificadas y con "
        "su etiqueta de seguridad?",
    ),
    PuntoSqp(
        "2.2",
        SECCIONES_SQP[1],
        "¿El personal que manipula sustancias químicas identifica a través de "
        "pictogramas los riesgos de los productos y el uso adecuado de EPP?",
    ),
    PuntoSqp(
        "3.1",
        SECCIONES_SQP[2],
        "¿Cuentan con zona y/o área exclusiva para almacenamiento de sustancias "
        "químicas?",
    ),
    PuntoSqp(
        "3.2",
        SECCIONES_SQP[2],
        "¿Cuentan con zona exclusiva para almacenamiento de residuos?",
    ),
    PuntoSqp(
        "3.3",
        SECCIONES_SQP[2],
        "¿Las áreas de almacenamiento se encuentran separadas de las zonas de "
        "alimentación e hidratación del personal?",
    ),
    PuntoSqp(
        "3.4", SECCIONES_SQP[2], "¿Las instalaciones de almacenamiento están ventiladas?"
    ),
    PuntoSqp(
        "3.5",
        SECCIONES_SQP[2],
        "¿La zona de almacenamiento cuenta con buena iluminación?",
    ),
    PuntoSqp(
        "3.9",
        SECCIONES_SQP[2],
        "¿Hay protección y correcto aislamiento de las conexiones eléctricas?",
    ),
    PuntoSqp(
        "3.6", SECCIONES_SQP[2], "¿Se cuenta con lava ojos dentro del área o cerca al sitio?"
    ),
    PuntoSqp(
        "3.7",
        SECCIONES_SQP[2],
        "¿Se cuenta con sistemas de respuesta a emergencias cerca al sitio "
        "(extintores, kit de derrames)?",
    ),
    PuntoSqp(
        "4.1", SECCIONES_SQP[3], "¿Los envases de los productos están en buen estado?"
    ),
    PuntoSqp(
        "4.2",
        SECCIONES_SQP[3],
        "¿Los productos químicos están segregados y separados según su "
        "compatibilidad?",
    ),
    PuntoSqp(
        "4.3",
        SECCIONES_SQP[3],
        "¿Todas las etiquetas de los productos químicos son legibles?",
    ),
    PuntoSqp(
        "4.4",
        SECCIONES_SQP[3],
        "¿Los contenedores de las sustancias químicas vacíos o dañados son "
        "desechados adecuadamente?",
    ),
    PuntoSqp(
        "4.5",
        SECCIONES_SQP[3],
        "¿El área de almacenamiento está ordenada y libre de derrames o fugas?",
    ),
    PuntoSqp(
        "4.6",
        SECCIONES_SQP[3],
        "¿Los cilindros que contienen gases inflamables tienen las cadenas de "
        "ajuste recubiertas de plástico o sistema anti chispa?",
    ),
    PuntoSqp(
        "4.7",
        SECCIONES_SQP[3],
        "¿Para el almacenamiento de cilindros hay espacios definidos?",
    ),
    PuntoSqp(
        "4.8",
        SECCIONES_SQP[3],
        "¿Tiene separados e identificados los cilindros llenos de los vacíos?",
    ),
)

TOTAL_PUNTOS_SQP: Final[int] = len(PUNTOS_SQP)

# Renglones numerados de la tabla "Nombre de la SQP" al pie del formato. El
# usuario captura las sustancias en un campo libre, una por renglón; esto es
# cuántos caben en la hoja impresa.
RENGLONES_SUSTANCIAS: Final[int] = 15

VALORES_SQP: Final[frozenset[str]] = frozenset({"si", "no", "na"})

# Cómo se rotula cada respuesta en la hoja de Excel.
ETIQUETAS_VALOR_SQP: Final[dict[str, str]] = {
    "si": "SI",
    "no": "NO",
    "na": "N/A",
}


# --- Controles de lista de verificación (OK / NO OK) -----------------------
#
# Tres hojas del libro de inspecciones tienen exactamente la misma forma: una
# fila por día del mes y una columna por punto, que se palomea o se marca. Solo
# cambian el título y la lista de puntos, así que se describen aquí y el
# formulario, la tabla y el Excel se escriben una sola vez.


class PuntoControl(NamedTuple):
    """Un punto de una lista de verificación."""

    clave: str
    etiqueta: str


class DefinicionChecklist(NamedTuple):
    """Una hoja de lista de verificación completa."""

    clave: str
    titulo: str
    # Nombre de la pestaña dentro del Excel: Excel corta a 31 caracteres y no
    # admite : \\ / ? * [ ], así que se escribe a mano en vez de recortar el
    # título.
    hoja: str
    # Solo la revisión de muros lleva una pregunta bajo el título; en las otras
    # dos hojas el título ya dice todo.
    subtitulo: str | None
    puntos: tuple[PuntoControl, ...]


CONTROLES_CHECKLIST: Final[dict[str, DefinicionChecklist]] = {
    "almacen_rp": DefinicionChecklist(
        clave="almacen_rp",
        titulo="CONTROL DE ALMACEN DE RESIDUOS PELIGROSOS",
        hoja="Almacen de RP",
        subtitulo=None,
        puntos=(
            PuntoControl("derrames", "Derrames de residuos"),
            PuntoControl("extintor", "Extintor en buenas condiciones"),
            PuntoControl("kit_derrames", "Kit de control de derrames"),
            PuntoControl("senalizacion", "Señalización"),
            PuntoControl("charolas", "Charolas"),
            PuntoControl("tierras", "Tierras físicas"),
        ),
    ),
    "recorridos": DefinicionChecklist(
        clave="recorridos",
        titulo="CONTROL DE RECORRIDO",
        hoja="Recorridos",
        subtitulo=None,
        puntos=(
            PuntoControl("frente", "Frente"),
            PuntoControl("oeste", "Lado oeste"),
            PuntoControl("trasera", "Parte trasera"),
            PuntoControl("este", "Lado este"),
        ),
    ),
    "muro": DefinicionChecklist(
        clave="muro",
        titulo="REVISION DE MUROS ALMACEN-EPS",
        hoja="Revision muro",
        subtitulo="¿Muro sin daño o fisura?",
        puntos=(
            PuntoControl("zona_1", "Zona 1"),
            PuntoControl("zona_2", "Zona 2"),
            PuntoControl("zona_3", "Zona 3"),
            PuntoControl("zona_4", "Zona 4"),
        ),
    ),
}

VALORES_CHECKLIST: Final[frozenset[str]] = frozenset({"ok", "no_ok"})

# Cómo se rotula cada valor en la hoja de Excel.
ETIQUETAS_VALOR_CHECKLIST: Final[dict[str, str]] = {
    "ok": "OK",
    "no_ok": "NO OK",
}


def definicion_checklist(clave: str) -> DefinicionChecklist | None:
    """Devuelve la definición de un control, o ``None`` si no existe."""
    return CONTROLES_CHECKLIST.get(clave)


# --- Pláticas diarias de seguridad -----------------------------------------
#
# Las áreas de esta hoja NO son las de ``core/constants.py``: aquellas son las
# del cuestionario y estas son las columnas del formato de pláticas, con la
# abreviatura que usa el personal de piso. Se mantienen separadas a propósito.

AREAS_PLATICAS: Final[tuple[PuntoControl, ...]] = (
    PuntoControl("assy", "ASSY"),
    PuntoControl("eps", "EPS"),
    PuntoControl("almacen", "ALMACEN"),
    PuntoControl("mtto", "MTTO"),
    PuntoControl("embarque", "EMBARQUE"),
    PuntoControl("ventas", "VENTAS"),
)

CLAVES_AREAS_PLATICAS: Final[frozenset[str]] = frozenset(
    area.clave for area in AREAS_PLATICAS
)

TITULO_PLATICAS: Final[str] = "PLATICAS DIARIAS DE SEGURIDAD"

# Cuántas fotos de evidencia admite un punto en NO OK o una plática. El tope
# existe para que una petición con varias fotos no crezca sin control.
MAX_FOTOS: Final[int] = 4
