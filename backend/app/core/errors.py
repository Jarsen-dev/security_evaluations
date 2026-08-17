"""Excepciones de dominio.

Los servicios lanzan estas excepciones; ``app.main`` las traduce a códigos
HTTP. Así la capa de negocio no depende de FastAPI y puede reutilizarse
desde la CLI o desde los generadores de reportes.
"""


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
