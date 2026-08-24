"""Excepciones de dominio y traducción de los errores de validación.

Los servicios lanzan estas excepciones; ``app.main`` las traduce a códigos
HTTP. Así la capa de negocio no depende de FastAPI y puede reutilizarse
desde la CLI o desde los generadores de reportes.
"""

from typing import Any, Final

# Pydantic redacta sus mensajes en inglés. Se traducen por tipo de error para
# que ninguna respuesta de la API mezcle idiomas. Viven aquí, y no en
# ``app.main``, porque las rutas que validan un cuerpo multipart a mano
# también los necesitan.
MENSAJES_VALIDACION: Final[dict[str, str]] = {
    "missing": "Este campo es obligatorio.",
    "string_too_short": "El texto es demasiado corto.",
    "string_too_long": "El texto es demasiado largo.",
    "string_type": "Se esperaba un texto.",
    "uuid_parsing": "El identificador no tiene un formato válido.",
    "int_parsing": "Se esperaba un número entero.",
    "int_type": "Se esperaba un número entero.",
    "float_parsing": "Se esperaba un número.",
    "bool_parsing": "Se esperaba un valor verdadero o falso.",
    "datetime_parsing": "La fecha no tiene un formato válido.",
    "date_parsing": "La fecha no tiene un formato válido.",
    "date_from_datetime_inexact": "La fecha no tiene un formato válido.",
    "greater_than_equal": "El valor es menor que el mínimo permitido.",
    "less_than_equal": "El valor es mayor que el máximo permitido.",
    "too_short": "Faltan elementos en la lista.",
    "too_long": "La lista tiene demasiados elementos.",
    "list_type": "Se esperaba una lista.",
    "json_invalid": "El cuerpo de la petición no es JSON válido.",
    "value_error": "El valor no es válido.",
}


def mensaje_de_validacion(error: dict[str, Any]) -> str:
    """Elige el texto en español para un error de validación de Pydantic.

    Los validadores propios ya lanzan su mensaje en español dentro de un
    ``ValueError``; ese texto es más específico que cualquier traducción
    genérica, así que se conserva. Pydantic lo entrega con el prefijo
    "Value error, ", que se recorta.
    """
    if error["type"] == "value_error":
        return str(error["msg"]).removeprefix("Value error, ")

    return MENSAJES_VALIDACION.get(error["type"], "El valor no es válido.")


class ErrorDeNegocio(Exception):
    """Los datos violan una regla de negocio. Se traduce a HTTP 422.

    ``errores`` permite devolver varios problemas a la vez (por ejemplo, una
    lista con todo lo que está mal en cada pregunta) en lugar de obligar al
    usuario a corregir de uno en uno.
    """

    def __init__(self, mensaje: str, errores: list[str] | None = None) -> None:
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.errores = errores or []


class RecursoNoEncontrado(Exception):
    """El recurso solicitado no existe. Se traduce a HTTP 404."""

    def __init__(self, mensaje: str = "El recurso solicitado no existe.") -> None:
        super().__init__(mensaje)
        self.mensaje = mensaje


class ConflictoDeNegocio(Exception):
    """La operación choca con el estado actual de los datos. HTTP 409."""

    def __init__(self, mensaje: str) -> None:
        super().__init__(mensaje)
        self.mensaje = mensaje
