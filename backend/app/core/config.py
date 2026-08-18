"""Configuración de la aplicación, leída una sola vez desde el entorno."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Archivos estáticos servidos por el backend. `config.py` está en
# backend/app/core/, así que se suben tres niveles para llegar a backend/.
DIRECTORIO_ESTATICOS = Path(__file__).resolve().parents[2] / "static"

# Logo de la empresa. Aparece en el panel, en el formulario público y en los
# documentos generados (PDF y PowerPoint). Si el archivo no existe, todo
# sigue funcionando: cada consumidor lo omite en lugar de fallar.
RUTA_LOGO = DIRECTORIO_ESTATICOS / "Logo.png"


def hay_logo() -> bool:
    """Indica si el logo está disponible en disco."""
    return RUTA_LOGO.is_file()


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

    # --- Límite de tasa del login -----------------------------------------
    # Mucho más estricto: el login es la única puerta al panel y quedó
    # expuesto a internet por el túnel. Solo cuentan los intentos fallidos,
    # así que un admin que teclea bien su contraseña nunca lo alcanza.
    RATE_LIMIT_LOGIN_INTENTOS: int = Field(default=5, ge=1)
    RATE_LIMIT_LOGIN_VENTANA_SEGUNDOS: int = Field(default=300, ge=1)

    # --- Red WiFi de planta ------------------------------------------------
    # Se usan para generar un código QR de acceso a la red, junto al QR del
    # cuestionario. Deliberadamente SIN el prefijo NEXT_PUBLIC_: esas
    # variables Next.js las incrusta en el bundle que descarga cualquiera,
    # incluidos los operadores del formulario público. La contraseña solo
    # debe viajar al panel de administración, con sesión iniciada.
    WIFI_SSID: str = ""
    WIFI_PASSWORD: str = ""
    WIFI_SEGURIDAD: Literal["WPA", "WEP", "nopass"] = "WPA"
    WIFI_OCULTA: bool = False

    @property
    def wifi_configurado(self) -> bool:
        """El QR de red solo tiene sentido si al menos hay nombre de red."""
        return bool(self.WIFI_SSID.strip())

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
    def docs_publicas(self) -> bool:
        """Si se sirve la documentación interactiva de la API.

        Fuera de desarrollo va apagada: el sistema está publicado en internet
        por el túnel de Cloudflare y ``/api/docs`` le entregaría a cualquiera
        el mapa completo de los endpoints del panel.
        """
        return self.ENVIRONMENT == "development"

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
