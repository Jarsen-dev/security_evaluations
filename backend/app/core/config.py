"""Configuración de la aplicación, leída una sola vez desde el entorno."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Variables de entorno del backend.

    Es la única fuente de verdad de configuración: ningún módulo debe leer
    ``os.environ`` por su cuenta.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Aplicación --------------------------------------------------------
    APP_NAME: str = "Sistema de Evaluación de Conocimientos"
    ENVIRONMENT: Literal["development", "production"] = "production"

    # --- Base de datos -----------------------------------------------------
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://evaluaciones:evaluaciones@db:5432/evaluaciones",
        description="URL async de PostgreSQL (driver asyncpg).",
    )

    # --- Seguridad ---------------------------------------------------------
    SECRET_KEY: str = Field(
        default="clave_insegura_de_desarrollo",
        description="Llave para firmar los JWT del administrador.",
    )
    ACCESS_TOKEN_EXPIRE_HOURS: int = 12
    COOKIE_SECURE: bool = False

    # --- Frontend / ligas públicas ----------------------------------------
    NEXT_PUBLIC_BASE_URL: str = "http://localhost:8080"

    # --- Límite de tasa de los endpoints públicos --------------------------
    # El default de la especificación es 30 peticiones por minuto y por IP.
    # Se deja configurable porque el valor correcto depende de la red: si la
    # WiFi de planta hace NAT, todos los celulares comparten una sola IP y
    # el límite hay que subirlo o el sistema los bloquea a media evaluación.
    RATE_LIMIT_PETICIONES: int = Field(default=30, ge=1)
    RATE_LIMIT_VENTANA_SEGUNDOS: int = Field(default=60, ge=1)

    # --- Reglas de negocio -------------------------------------------------
    UMBRAL_APROBACION: int = Field(
        default=70,
        ge=0,
        le=100,
        description="Porcentaje mínimo para considerar aprobado un intento.",
    )

    @field_validator("DATABASE_URL")
    @classmethod
    def _validar_driver_async(cls, valor: str) -> str:
        """Evita que una URL síncrona rompa el engine async con un error críptico."""
        if not valor.startswith("postgresql+asyncpg://"):
            raise ValueError(
                "DATABASE_URL debe usar el driver async: "
                "postgresql+asyncpg://usuario:contrasena@host:puerto/basededatos"
            )
        return valor

    @property
    def base_url_es_local(self) -> bool:
        """``True`` si la URL base apunta a la propia máquina.

        En ese caso el código QR no sirve: al escanearlo, el celular
        intentaría abrir su propio localhost. El frontend muestra una
        advertencia visible cuando esto ocurre.
        """
        url = self.NEXT_PUBLIC_BASE_URL.lower()
        return "localhost" in url or "127.0.0.1" in url

    @property
    def cors_origins(self) -> list[str]:
        """Orígenes permitidos.

        En producción todo pasa por Nginx (mismo origen), así que la lista
        solo cubre el acceso directo al frontend durante el desarrollo.
        """
        origenes = {self.NEXT_PUBLIC_BASE_URL.rstrip("/")}
        if self.ENVIRONMENT == "development":
            origenes.update(
                {
                    "http://localhost:3200",
                    "http://127.0.0.1:3200",
                    "http://localhost:3000",
                }
            )
        return sorted(origenes)


@lru_cache
def get_settings() -> Settings:
    """Devuelve la configuración cacheada (se instancia una sola vez)."""
    return Settings()


settings = get_settings()
