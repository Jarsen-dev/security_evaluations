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


# Espejo en disco de los formatos que el clasificador aprende: una carpeta por
# formato con la foto, el JSON y el texto del OCR, para poder revisarlos como
# archivos. **Fuera de `static/` a propósito**: aquel se sirve en /api/static
# SIN sesión —el formulario público necesita el logo— y el túnel lo publica,
# así que ahí dentro las remisiones quedarían al alcance de cualquiera.
#
# Es una copia, no la fuente: el clasificador sigue leyendo de la base. Y
# necesita el volumen declarado en docker-compose.yml, o se vacía en cada
# `--build` sin que nada falle de forma visible.
DIRECTORIO_FORMATOS = Path(__file__).resolve().parents[2] / "ocr_formatos"


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
    APP_NAME: str = "Sistema ESH"
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

    # --- Límite de tasa del escaneo de rondines ---------------------------
    # Más holgado que el del formulario: un recorrido son decenas de escaneos
    # en pocos minutos, y todos los guardias comparten la IP del NAT de la
    # WiFi de planta.
    RATE_LIMIT_RONDIN_ESCANEOS: int = Field(default=120, ge=1)
    RATE_LIMIT_RONDIN_VENTANA_SEGUNDOS: int = Field(default=60, ge=1)

    # La PC sondea el estado de la sesión de captura cada dos segundos: unas
    # 30 peticiones por minuto de un solo operador, y varios pueden estar
    # capturando a la vez detrás del mismo NAT de planta.
    RATE_LIMIT_RECEPCION_PETICIONES: int = Field(default=120, ge=1)
    RATE_LIMIT_RECEPCION_VENTANA_SEGUNDOS: int = Field(default=60, ge=1)

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

    # --- pgAdmin (pestaña de Mantenimiento) --------------------------------
    # Los dos botones de acceso rápido del panel. Deliberadamente SIN el
    # prefijo NEXT_PUBLIC_: la contraseña se sirve por un endpoint que exige
    # sesión de superadministrador, no se incrusta en el bundle de Next.
    #
    # pgAdmin escucha solo en la LAN; el túnel de Cloudflare apunta a
    # nginx:80 y no lo publica. Por eso la URL de "producción" es la IP del
    # servidor dentro de la planta, no el dominio.
    PGADMIN_URL_LOCAL: str = ""
    PGADMIN_URL_PRODUCCION: str = ""
    PGADMIN_EMAIL: str = ""
    PGADMIN_PASSWORD: str = ""

    @property
    def pgadmin_configurado(self) -> bool:
        """Si hay al menos una instancia de pgAdmin a la que apuntar.

        Sin esto la pantalla de Mantenimiento mostraría botones que no
        llevan a ningún lado; con esto muestra un aviso de qué falta
        capturar en el `.env`.
        """
        return bool(
            self.PGADMIN_URL_LOCAL.strip() or self.PGADMIN_URL_PRODUCCION.strip()
        )

    # --- Zona horaria ------------------------------------------------------
    # La bitácora se guarda en TIMESTAMPTZ (UTC), pero se consulta con
    # filtros de "hora desde" y "hora hasta" que la gente teclea pensando en
    # el reloj de la planta. La conversión se hace en SQL con esta zona.
    ZONA_HORARIA: str = "America/Monterrey"

    # --- Correo saliente ---------------------------------------------------
    # Se usa para los reportes de rondines. La contraseña NO lleva el prefijo
    # NEXT_PUBLIC_ por la misma razón que la del WiFi: Next incrustaría esa
    # variable en el bundle que descarga cualquiera.
    SMTP_HOST: str = ""
    SMTP_PUERTO: int = Field(default=465, ge=1, le=65535)
    SMTP_USUARIO: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_DESDE: str = ""
    #: True para SMTPS directo (puerto 465); False para STARTTLS (587).
    SMTP_SSL: bool = True

    @property
    def correo_configurado(self) -> bool:
        """Si hay servidor y remitente para poder enviar."""
        return bool(self.SMTP_HOST.strip() and self.remitente)

    @property
    def remitente(self) -> str:
        """Dirección del remitente; cae al usuario si no se capturó aparte."""
        return (self.SMTP_DESDE or self.SMTP_USUARIO).strip()

    # --- Reporte automático de rondines ------------------------------------
    RONDINES_REPORTE_AUTOMATICO: bool = False
    #: Correos separados por comas.
    RONDINES_DESTINATARIOS: str = ""

    @property
    def rondines_destinatarios(self) -> list[str]:
        """Lista de destinatarios del reporte automático."""
        return [
            correo.strip()
            for correo in self.RONDINES_DESTINATARIOS.split(",")
            if correo.strip()
        ]

    # --- Ingesta de rondines desde AppSheet --------------------------------
    # La captura de rondines la hace una app de AppSheet; un Bot suyo empuja
    # cada escaneo a /api/publico/rondin/escaneos. El secreto que viaja en la
    # cabecera es la ÚNICA credencial de ese endpoint, así que va sin prefijo
    # NEXT_PUBLIC_ (Next lo incrustaría en el bundle) y sin valor por omisión:
    # vacío significa "apagado", nunca "abierto". Ver SEGURIDAD.md.
    RONDINES_WEBHOOK_SECRETO: str = ""
    #: El peor día medido del histórico son 476 escaneos; 500 cubre uno entero.
    RONDINES_WEBHOOK_MAX_LOTE: int = Field(default=500, ge=1)

    @property
    def ingesta_rondines_activa(self) -> bool:
        """Sin secreto capturado el webhook responde 503, no acepta a ciegas."""
        return bool(self.RONDINES_WEBHOOK_SECRETO.strip())

    # --- Cierre automático de PCI MTTO -------------------------------------
    #: Encendido por omisión, al revés que el reporte de rondines: aquel
    #: necesita un servidor de correo configurado y este no depende de nada
    #: externo. Apagarlo deja de levantar el registro de los meses sin
    #: respuesta, así que el histórico de cumplimiento se queda con huecos.
    PCI_CIERRE_AUTOMATICO: bool = True

    # --- Recepciones por foto (OCR + IA) -----------------------------------
    # El paso (3) del pipeline lo resuelve un LLM de TEXTO en un Ollama de la
    # red: nunca ve la imagen, solo acomoda el texto que Tesseract ya leyó.
    # Un modelo de visión inventaría números de parte y cantidades que no
    # están en el papel; así el peor caso es un campo en null.
    OLLAMA_HOST: str = "http://192.168.1.56:11434"
    OLLAMA_TEXT_MODEL: str = "llama3.2:latest"

    # Piso absoluto del clasificador TF-IDF: por debajo de esto un documento no
    # se parece a nada conocido. **Quien decide de verdad es el cociente**
    # contra el mejor de otro formato (`FACTOR_DISTINCION` en
    # `ocr_recepciones.py`), porque todas las facturas CFDI comparten la
    # plantilla del SAT y el parecido absoluto sube por igual para todos los
    # formatos. Medido con documentos reales de la planta: las facturas que sí
    # son del formato puntúan 0.227, 0.312 y 0.632 —el absoluto no las
    # distingue de una ajena, que daba 0.314— pero le ganan al segundo formato
    # por 1.30, 1.80 y 2.47 veces, mientras que una ajena empata con todos.
    #
    # Estuvo en 0.40 unas horas, con el cociente sin implementar: rechazaba las
    # facturas legítimas del mismo proveedor a partir de la segunda.
    OCR_UMBRAL_SIMILITUD: float = Field(default=0.20, ge=0.0, le=1.0)

    # Presupuesto de tiempo en capas. La regla que no se puede romper: el
    # techo total debe ser MENOR que el `proxy_read_timeout` de Nginx (120 s).
    # Si el proxy corta primero, el navegador recibe un 500 opaco en vez del
    # 200 con `ocr_ok:false` que habilita la captura manual.
    OCR_TIMEOUT_PS: int = Field(default=5, ge=1)
    OCR_TIMEOUT_FRIO: int = Field(default=90, ge=1)
    OCR_TIMEOUT_CALIENTE: int = Field(default=30, ge=1)
    OCR_PRESUPUESTO_TOTAL: int = Field(default=100, ge=1)

    #: Tope por foto de recepción. Nginx corta antes en 25 MB (client_max_body_size).
    RECEPCIONES_MAX_BYTES_FOTO: int = Field(default=15 * 1024 * 1024, ge=1)

    #: Minutos que vive una sesión de captura por QR antes de expirar.
    RECEPCIONES_MINUTOS_SESION_QR: int = Field(default=10, ge=1)

    @property
    def ocr_configurado(self) -> bool:
        """Si hay a dónde mandar el texto para estructurarlo.

        No comprueba que el host responda: eso se descubre al llamarlo, y la
        extracción degrada sola a captura manual si no contesta.
        """
        return bool(self.OLLAMA_HOST.strip() and self.OLLAMA_TEXT_MODEL.strip())

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
