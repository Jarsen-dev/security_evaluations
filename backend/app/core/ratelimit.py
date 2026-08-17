"""Limitador de tasa en memoria para los endpoints públicos.

Sin Redis a propósito: a esta escala (~500 empleados, pico de ~150 en una
hora) un diccionario con ventana deslizante es suficiente y no agrega una
pieza más de infraestructura que mantener.

Limitación conocida: el estado vive en la memoria de cada worker de uvicorn.
Con 4 workers, una IP puede llegar a 4x el límite configurado antes de ser
frenada. Es aceptable aquí porque el objetivo es contener abuso automatizado,
no aplicar una cuota exacta.
"""

import time
from collections import defaultdict, deque

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.core.config import settings

# Cada cuántas peticiones se hace limpieza de IPs inactivas.
INTERVALO_LIMPIEZA = 500


class LimitadorDeTasa:
    """Ventana deslizante por clave."""

    def __init__(
        self,
        max_peticiones: int | None = None,
        ventana: int | None = None,
    ) -> None:
        max_peticiones = max_peticiones or settings.RATE_LIMIT_PETICIONES
        ventana = ventana or settings.RATE_LIMIT_VENTANA_SEGUNDOS
        self.max_peticiones = max_peticiones
        self.ventana = ventana
        self._marcas: defaultdict[str, deque[float]] = defaultdict(deque)
        self._peticiones_desde_limpieza = 0

    def _purgar(self, marcas: deque[float], ahora: float) -> None:
        """Descarta las marcas que ya salieron de la ventana."""
        limite = ahora - self.ventana
        while marcas and marcas[0] <= limite:
            marcas.popleft()

    def _limpiar_inactivas(self, ahora: float) -> None:
        """Elimina las IPs sin actividad reciente.

        Sin esto, el diccionario crece indefinidamente: una IP que entra una
        sola vez ocuparía memoria para siempre.
        """
        limite = ahora - self.ventana
        inactivas = [
            clave
            for clave, marcas in self._marcas.items()
            if not marcas or marcas[-1] <= limite
        ]
        for clave in inactivas:
            del self._marcas[clave]

    def permitir(self, clave: str) -> bool:
        """Registra una petición y dice si está dentro del límite."""
        ahora = time.monotonic()

        self._peticiones_desde_limpieza += 1
        if self._peticiones_desde_limpieza >= INTERVALO_LIMPIEZA:
            self._peticiones_desde_limpieza = 0
            self._limpiar_inactivas(ahora)

        marcas = self._marcas[clave]
        self._purgar(marcas, ahora)

        if len(marcas) >= self.max_peticiones:
            return False

        marcas.append(ahora)
        return True

    def segundos_para_reintentar(self, clave: str) -> int:
        """Cuánto falta para que se libere un espacio en la ventana."""
        marcas = self._marcas.get(clave)
        if not marcas:
            return 0
        restante = self.ventana - (time.monotonic() - marcas[0])
        return max(1, int(restante) + 1)


def obtener_ip_cliente(request: Request) -> str:
    """Determina la IP real del cliente detrás de Nginx.

    Se usa ``X-Real-IP`` porque Nginx la fija en cada petición y es el único
    punto de entrada del sistema. ``X-Forwarded-For`` lo puede falsificar el
    cliente, así que solo se consulta como respaldo tomando la primera
    entrada, y al final se cae a la IP de la conexión.
    """
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()

    reenviada = request.headers.get("x-forwarded-for")
    if reenviada:
        return reenviada.split(",")[0].strip()

    return request.client.host if request.client else "desconocida"


class MiddlewareRateLimit(BaseHTTPMiddleware):
    """Aplica el límite de tasa solo a las rutas públicas.

    El panel de administración queda fuera: ya está protegido por sesión y un
    admin legítimo puede hacer muchas peticiones seguidas al abrir el
    dashboard.
    """

    def __init__(self, app, prefijo: str = "/api/publico") -> None:
        super().__init__(app)
        self.prefijo = prefijo
        self.limitador = LimitadorDeTasa()

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if not request.url.path.startswith(self.prefijo):
            return await call_next(request)

        ip = obtener_ip_cliente(request)

        if not self.limitador.permitir(ip):
            espera = self.limitador.segundos_para_reintentar(ip)
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": (
                        "Estás enviando demasiadas peticiones. "
                        f"Espera {espera} segundos e intenta de nuevo."
                    )
                },
                headers={"Retry-After": str(espera)},
            )

        return await call_next(request)
