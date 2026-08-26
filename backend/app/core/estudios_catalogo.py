"""Catálogo de los estudios y capacitaciones normativos.

Las opciones válidas de cada campo viven aquí y se sirven por la API, igual
que las áreas y que los puntos de los controles: el frontend nunca las tiene
escritas a mano, así que agregar una vigencia o un estatus se hace en un solo
lugar.

Lo que **no** vive aquí son los rótulos que ve el usuario en el panel: esos
son interfaz y se traducen a los tres idiomas desde ``lib/i18n`` (regla 6).
``etiqueta`` es el texto en español que imprime el Excel y que aparece en los
mensajes de error de la API.
"""

from datetime import date
from typing import Final, NamedTuple

# Colores del semáforo. Son los mismos nombres que usan los controles ESH,
# para que el panel y las exportaciones los traduzcan una sola vez.
VERDE: Final[str] = "verde"
AMARILLO: Final[str] = "amarillo"
ROJO: Final[str] = "rojo"
GRIS: Final[str] = "gris"


class OpcionEstudio(NamedTuple):
    """Una opción de un campo de selección del formulario."""

    clave: str
    #: Texto en español. Lo imprime el Excel; el panel lo traduce.
    etiqueta: str
    #: Cómo se abrevia en la tabla y en la hoja ("IN" en lugar de "Interno").
    #: Vacío significa que se usa la etiqueta completa.
    corto: str = ""
    #: 'verde', 'amarillo', 'rojo', 'gris' o vacío si el campo no se semaforiza.
    semaforo: str = ""
    #: La hoja DETALLE imprime la prioridad como número, no como texto.
    numero: int | None = None

    @property
    def texto_corto(self) -> str:
        """Lo que se pinta en la celda o en la tabla."""
        return self.corto or self.etiqueta


VIGENCIAS: Final[tuple[OpcionEstudio, ...]] = (
    OpcionEstudio("una_vez", "Una sola vez"),
    OpcionEstudio("1_ano", "1 año"),
    OpcionEstudio("2_anos", "2 años"),
    OpcionEstudio("3_anos", "3 años"),
    OpcionEstudio("4_anos", "4 años"),
    OpcionEstudio("5_anos", "5 años"),
)

# La hoja original numera la prioridad al revés de como se lee: 1 es la más
# alta. El número es lo que va en la celda; el color lo pinta el semáforo.
PRIORIDADES: Final[tuple[OpcionEstudio, ...]] = (
    OpcionEstudio("alta", "Alta", semaforo=ROJO, numero=1),
    OpcionEstudio("media", "Media", semaforo=AMARILLO, numero=2),
    OpcionEstudio("baja", "Baja", semaforo=VERDE, numero=3),
)

TIPOS: Final[tuple[OpcionEstudio, ...]] = (
    OpcionEstudio("interno", "Interno", corto="IN"),
    OpcionEstudio("externo", "Externo", corto="EX"),
)

ESTATUS: Final[tuple[OpcionEstudio, ...]] = (
    OpcionEstudio("pendiente", "Pendiente", semaforo=ROJO),
    OpcionEstudio("proceso", "Proceso", semaforo=AMARILLO),
    OpcionEstudio("ok", "OK", semaforo=VERDE),
)

# El campo "Vencido" de la hoja: o se sabe la fecha, o se sabe que ya venció,
# o todavía no se tiene el estudio. Solo `en_curso` lleva fecha.
VENCIMIENTOS: Final[tuple[OpcionEstudio, ...]] = (
    OpcionEstudio("en_curso", "En curso"),
    OpcionEstudio("vencido", "Vencido"),
    OpcionEstudio("pendiente", "Pendiente"),
)

#: Clave del vencimiento que exige una fecha capturada.
VENCIMIENTO_CON_FECHA: Final[str] = "en_curso"

# Aprobado y Pagado comparten lista: en la hoja son las columnas APRO y PAGAR
# y toman exactamente los mismos valores.
APROBACIONES: Final[tuple[OpcionEstudio, ...]] = (
    OpcionEstudio("ok", "OK", semaforo=VERDE),
    OpcionEstudio("pendiente", "Pendiente", semaforo=ROJO),
    OpcionEstudio("proceso", "Proceso", semaforo=AMARILLO),
    OpcionEstudio("na", "N/A", semaforo=GRIS),
)

#: El link al estudio solo tiene sentido cuando ya está hecho.
ESTATUS_CON_LINK: Final[str] = "ok"

#: Cuántos caracteres se aceptan en el link. Una ruta de red larga cabe de
#: sobra; el tope solo evita que alguien pegue un documento entero.
MAX_LINK: Final[int] = 500


def _claves(opciones: tuple[OpcionEstudio, ...]) -> frozenset[str]:
    return frozenset(opcion.clave for opcion in opciones)


CLAVES_VIGENCIA: Final[frozenset[str]] = _claves(VIGENCIAS)
CLAVES_PRIORIDAD: Final[frozenset[str]] = _claves(PRIORIDADES)
CLAVES_TIPO: Final[frozenset[str]] = _claves(TIPOS)
CLAVES_ESTATUS: Final[frozenset[str]] = _claves(ESTATUS)
CLAVES_VENCIMIENTO: Final[frozenset[str]] = _claves(VENCIMIENTOS)
CLAVES_APROBACION: Final[frozenset[str]] = _claves(APROBACIONES)


def opcion(opciones: tuple[OpcionEstudio, ...], clave: str) -> OpcionEstudio | None:
    """Busca una opción por su clave; ``None`` si el catálogo cambió."""
    for candidata in opciones:
        if candidata.clave == clave:
            return candidata
    return None


def etiqueta(opciones: tuple[OpcionEstudio, ...], clave: str) -> str:
    """Texto en español de una clave, o la clave misma si ya no existe.

    No falla ante un valor histórico que se haya retirado del catálogo: el
    Excel de un estudio viejo debe seguir generándose.
    """
    encontrada = opcion(opciones, clave)
    return encontrada.texto_corto if encontrada is not None else clave


def semaforo(opciones: tuple[OpcionEstudio, ...], clave: str) -> str:
    """Color de una clave, o vacío si no se semaforiza."""
    encontrada = opcion(opciones, clave)
    return encontrada.semaforo if encontrada is not None else ""


def sumar_un_mes(dia: date) -> date:
    """El mismo día del mes siguiente, ajustando el fin de mes.

    Es la ventana del aviso de vencimiento: "un mes antes" son treinta y tantos
    días según el mes, no treinta fijos. El 31 de enero avisa desde el 28 (o el
    29) de febrero, que es el último día equivalente que existe.
    """
    mes = dia.month + 1
    ano = dia.year + (mes > 12)
    mes = mes - 12 if mes > 12 else mes

    ultimo = _dias_del_mes(ano, mes)
    return date(ano, mes, min(dia.day, ultimo))


def _dias_del_mes(ano: int, mes: int) -> int:
    """Cuántos días tiene un mes, sin importar `calendar`."""
    if mes == 2:
        bisiesto = ano % 4 == 0 and (ano % 100 != 0 or ano % 400 == 0)
        return 29 if bisiesto else 28
    return 30 if mes in (4, 6, 9, 11) else 31
