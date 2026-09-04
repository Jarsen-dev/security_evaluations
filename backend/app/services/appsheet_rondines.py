"""Ingesta de los rondines capturados en AppSheet.

Los guardias registran su recorrido en una app de AppSheet con 44 puntos fijos
en planta, y esa app es la fuente de verdad. Aquí solo se consume: un Bot suyo
empuja cada escaneo al webhook y dos comandos de CLI cargan el catálogo y el
histórico desde los CSV exportados. Las tres vías pasan por este módulo para
que el parseo y la deduplicación existan una sola vez.

Casi todo es lógica pura y está probado en `tests/test_rondines.py`. Lo único
que toca la base son `catalogo_de_puntos()`, `registrar_lote()` y
`sincronizar_puntos()`, y ninguna importa FastAPI.
"""

import logging
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Final

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rondin import EscaneoRondin, PuntoRondin
from app.services import rondin_service

logger = logging.getLogger(__name__)

ORIGEN_WEBHOOK: Final[str] = "appsheet"
ORIGEN_HISTORICO: Final[str] = "appsheet_historico"

#: El formato que exporta AppSheet con locale es-ES. **Nunca se agrega
#: `%m/%d/%Y` a la lista.** `05/04/2026` parsea sin error bajo las dos
#: interpretaciones, así que un formato de más no protege de nada: adivina, y
#: adivina en silencio, moviendo escaneos meses de lugar. Medido sobre el
#: histórico completo: el primer campo llega a 31 y el segundo no pasa de 12.
FORMATO_APPSHEET: Final[str] = "%d/%m/%Y %H:%M:%S"

#: Tolerancia de reloj hacia el futuro. No se recorta al presente: un
#: dispositivo con el reloj desviado fabricaría cumplimiento en el rondín en
#: curso, que es justo lo que el tablero está midiendo.
MARGEN_FUTURO: Final[timedelta] = timedelta(minutes=15)

#: Antigüedad máxima por la vía del webhook. El importador histórico pasa
#: `None`: con cualquier tope, un CSV que arranca en febrero se descartaría
#: entero.
ANTIGUEDAD_WEBHOOK_DIAS: Final[int] = 30

#: Longitudes de las columnas de texto, para no reventar el INSERT con un
#: comentario largo. Recortar es mejor que perder el renglón entero.
MAX_COMENTARIO: Final[int] = 300
MAX_EMAIL: Final[int] = 200
MAX_FOTO: Final[int] = 200
MAX_ORIGEN_ID: Final[int] = 64
MAX_NOMBRE_PUNTO: Final[int] = 150

#: Alias de cabecera aceptados, ya normalizados. AppSheet exporta con acentos y
#: espacios, y quien reexporte desde Excel puede cambiarlos.
ALIAS: Final[dict[str, str]] = {
    "id": "origen_id",
    "id_registro": "origen_id",
    "origen_id": "origen_id",
    "fecha_hora": "momento",
    "escaneado_at": "momento",
    "momento": "momento",
    "punto_qr": "numero",
    "id_qr": "numero",
    "numero": "numero",
    "punto": "numero",
    "ubicacion_gps": "gps",
    "gps": "gps",
    "comentarios": "comentario",
    "comentario": "comentario",
    "email_guardia": "email",
    "email": "email",
    "evidencia_foto": "foto",
    "foto": "foto",
    "nombre_del_lugar": "nombre",
    "nombre": "nombre",
    "ubicacion_referencia": "gps",
}


@dataclass(frozen=True)
class FilaEscaneo:
    """Un escaneo ya validado y listo para insertar."""

    origen_id: str
    numero: int
    momento: datetime
    gps: tuple[Decimal, Decimal] | None = None
    comentario: str | None = None
    email: str | None = None
    foto: str | None = None


@dataclass(frozen=True)
class ResultadoIngesta:
    """Qué pasó con un lote. Los motivos van en español, para el operador."""

    recibidos: int = 0
    insertados: int = 0
    duplicados: int = 0
    descartados: int = 0
    problemas: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResultadoSincronia:
    """Qué pasó al importar el catálogo de puntos."""

    creados: int = 0
    actualizados: int = 0
    retirados: int = 0
    descartados: int = 0
    problemas: tuple[str, ...] = ()


def normalizar_clave(cruda: str) -> str:
    """Cabecera a minúsculas, sin acentos ni espacios.

    `Ubicación_GPS` y `Nombre del Lugar` traen acentos y espacios, y Excel los
    cambia al reexportar. Comparar así evita depender de cómo se guardó.
    """
    tabla = str.maketrans("áéíóúüñÁÉÍÓÚÜÑ", "aeiouunAEIOUUN")
    limpia = cruda.strip().lower().translate(tabla)
    return "_".join(limpia.replace("-", " ").replace(".", " ").split()).strip("_")


def renombrar(cruda: dict[str, Any]) -> dict[str, Any]:
    """Traduce las cabeceras del CSV o del webhook a nombres internos."""
    salida: dict[str, Any] = {}
    for llave, valor in cruda.items():
        if llave is None:
            continue
        interna = ALIAS.get(normalizar_clave(str(llave)))
        # El primero gana: si el archivo trae `punto` y `Punto_QR`, quedarse
        # con el segundo dependería del orden de las columnas.
        if interna is not None and interna not in salida:
            salida[interna] = valor
    return salida


def _texto(valor: Any, tope: int) -> str | None:
    """Limpia un texto opcional y lo recorta al ancho de su columna."""
    if valor is None:
        return None
    limpio = " ".join(str(valor).split())
    return limpio[:tope] or None


def parsear_momento(valor: Any) -> datetime | None:
    """Interpreta la marca de tiempo de AppSheet, o devuelve ``None``.

    Dos formatos y ninguno más: ISO 8601 (lo que manda el Bot con una
    plantilla explícita) y `DD/MM/YYYY H:MM:SS` (lo que exporta el CSV).

    Lo que llega sin zona horaria **se interpreta en la hora de la planta, no
    en UTC**. Es la misma trampa que `sin_zona()` con otro disfraz: leerlo como
    UTC correría cada escaneo seis horas y lo tiraría al bloque equivocado del
    tablero. Comprobado sobre el histórico: la hora 6 tiene 3 registros en
    siete meses (el cambio de turno de 07:30) y la 13 está llena; si el sello
    fuera UTC sería al revés.
    """
    if valor is None:
        return None

    texto = str(valor).strip()
    if not texto:
        return None

    momento: datetime | None = None
    try:
        momento = datetime.fromisoformat(texto.replace("Z", "+00:00"))
    except ValueError:
        try:
            momento = datetime.strptime(texto, FORMATO_APPSHEET)
        except ValueError:
            return None

    if momento.tzinfo is None:
        return momento.replace(tzinfo=rondin_service.zona())
    return momento.astimezone(rondin_service.zona())


def momento_razonable(
    momento: datetime, ahora: datetime, *, antiguedad_maxima_dias: int | None
) -> bool:
    """¿La marca de tiempo cae en una ventana creíble?"""
    if momento > ahora + MARGEN_FUTURO:
        return False
    if antiguedad_maxima_dias is None:
        return True
    return momento >= ahora - timedelta(days=antiguedad_maxima_dias)


def parsear_gps(valor: Any) -> tuple[Decimal, Decimal] | None:
    """Convierte ``"25.752827, -100.166298"`` en un par de decimales.

    Es evidencia, no verificación: el dato es `=HERE()`, el GPS del celular, y
    medido contra las coordenadas de referencia tiene 94 m de error mediano
    mientras que los puntos de la planta están más juntos que eso. Un semáforo
    de "el guardia no estuvo ahí" construido con esto acusaría en falso.
    """
    if valor is None:
        return None

    partes = str(valor).replace(";", ",").split(",")
    if len(partes) != 2:
        return None

    try:
        lat = Decimal(partes[0].strip())
        lon = Decimal(partes[1].strip())
    except (InvalidOperation, ValueError):
        return None

    # Fuera de rango no es una coordenada: el histórico trae al menos una
    # lectura basura que caía a 11,000 km de su punto.
    if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
        return None

    return (round(lat, 6), round(lon, 6))


def normalizar_fila(cruda: dict[str, Any]) -> FilaEscaneo | str:
    """Valida un renglón. Devuelve la fila lista o el motivo del descarte.

    Nunca lanza: el 2.6 % del histórico viene sucio (sin punto, sin fecha o
    sin ID) y un lote se descarta renglón a renglón, jamás entero.
    """
    datos = renombrar(cruda)

    origen_id = _texto(datos.get("origen_id"), MAX_ORIGEN_ID)
    if not origen_id:
        return "sin ID_Registro"

    crudo_numero = str(datos.get("numero") or "").strip()
    if not crudo_numero:
        return f"{origen_id}: sin Punto_QR"
    try:
        # AppSheet exporta los números como texto y a veces con decimal.
        numero = int(float(crudo_numero))
    except ValueError:
        return f"{origen_id}: Punto_QR ilegible ({crudo_numero!r})"
    if numero < 1:
        return f"{origen_id}: Punto_QR fuera de rango ({numero})"

    momento = parsear_momento(datos.get("momento"))
    if momento is None:
        return f"{origen_id}: fecha ilegible ({str(datos.get('momento'))!r})"

    return FilaEscaneo(
        origen_id=origen_id,
        numero=numero,
        momento=momento,
        gps=parsear_gps(datos.get("gps")),
        comentario=_texto(datos.get("comentario"), MAX_COMENTARIO),
        email=_texto(datos.get("email"), MAX_EMAIL),
        foto=_texto(datos.get("foto"), MAX_FOTO),
    )


def deduplicar(filas: Sequence[FilaEscaneo]) -> tuple[list[FilaEscaneo], int]:
    """Colapsa los repetidos DENTRO del lote, quedándose con el primero.

    Cinturón sobre los tirantes del `ON CONFLICT`: hace el conteo determinista
    y evita depender de cómo se comporta la inserción especulativa cuando dos
    `VALUES` del mismo comando comparten llave.
    """
    vistos: set[str] = set()
    unicas: list[FilaEscaneo] = []
    for fila in filas:
        if fila.origen_id in vistos:
            continue
        vistos.add(fila.origen_id)
        unicas.append(fila)
    return unicas, len(filas) - len(unicas)


def preparar(
    crudas: Iterable[dict[str, Any]],
    *,
    ahora: datetime,
    antiguedad_maxima_dias: int | None,
) -> tuple[list[FilaEscaneo], int, list[str]]:
    """Normaliza, valida la ventana temporal y deduplica un lote entero."""
    validas: list[FilaEscaneo] = []
    problemas: list[str] = []

    for cruda in crudas:
        resultado = normalizar_fila(cruda)
        if isinstance(resultado, str):
            problemas.append(resultado)
            continue
        if not momento_razonable(
            resultado.momento, ahora, antiguedad_maxima_dias=antiguedad_maxima_dias
        ):
            problemas.append(
                f"{resultado.origen_id}: fecha fuera de la ventana "
                f"({resultado.momento:%d/%m/%Y %H:%M})"
            )
            continue
        validas.append(resultado)

    unicas, repetidas = deduplicar(validas)
    return unicas, repetidas, problemas


async def catalogo_de_puntos(db: AsyncSession) -> dict[int, uuid.UUID]:
    """Número de punto → id, en UNA consulta.

    Resolver punto por punto haría una consulta por renglón y el importador
    histórico son 48 mil (regla 4: las agregaciones y las búsquedas masivas van
    en SQL, no en Python).
    """
    filas = await db.execute(select(PuntoRondin.numero, PuntoRondin.id))
    return {numero: punto_id for numero, punto_id in filas.all()}


async def registrar_lote(
    db: AsyncSession,
    crudas: Sequence[dict[str, Any]],
    *,
    origen: str = ORIGEN_WEBHOOK,
    ip: str | None = None,
    antiguedad_maxima_dias: int | None = ANTIGUEDAD_WEBHOOK_DIAS,
    catalogo: dict[int, uuid.UUID] | None = None,
) -> ResultadoIngesta:
    """Inserta un lote de escaneos, saltando los que ya estaban.

    Un escaneo de un punto que no está en el catálogo **se descarta y se
    reporta**, no se guarda huérfano: `construir_tablero()` ignora las filas
    con `punto_id` en NULL, así que un huérfano sería invisible y solo
    escondería el problema real, que es que el catálogo quedó viejo. Se
    recupera corriendo `importar-puntos` y volviendo a importar el día.
    """
    if catalogo is None:
        catalogo = await catalogo_de_puntos(db)

    ahora = rondin_service.ahora_local()
    filas, repetidas, problemas = preparar(
        crudas, ahora=ahora, antiguedad_maxima_dias=antiguedad_maxima_dias
    )

    valores: list[dict[str, Any]] = []
    for fila in filas:
        punto_id = catalogo.get(fila.numero)
        if punto_id is None:
            problemas.append(f"{fila.origen_id}: el punto {fila.numero} no existe")
            continue
        valores.append(
            {
                "punto_id": punto_id,
                "punto_numero": fila.numero,
                "escaneado_at": fila.momento,
                "ip": ip,
                "origen": origen,
                "origen_id": fila.origen_id,
                "gps_lat": fila.gps[0] if fila.gps else None,
                "gps_lon": fila.gps[1] if fila.gps else None,
                "comentario": fila.comentario,
                "email_guardia": fila.email,
                "foto_ruta": fila.foto,
            }
        )

    insertados = 0
    if valores:
        # El upsert va en SQL y sin leer antes: con cuatro workers y un lote
        # reintentado, leer-y-luego-escribir se pisa. `RETURNING` bajo
        # `DO NOTHING` devuelve solo lo que de verdad entró, así que de ahí
        # salen "insertados" y "duplicados" sin un SELECT previo.
        sentencia = (
            pg_insert(EscaneoRondin)
            .values(valores)
            .on_conflict_do_nothing(constraint="uq_escaneos_rondin_origen_id")
            .returning(EscaneoRondin.origen_id)
        )
        insertados = len((await db.scalars(sentencia)).all())
        await db.commit()

    descartados = len(problemas)
    if problemas:
        logger.warning(
            "Ingesta de rondines: %d renglón(es) descartado(s). Primeros: %s",
            descartados,
            "; ".join(problemas[:5]),
        )

    return ResultadoIngesta(
        recibidos=len(crudas),
        insertados=insertados,
        duplicados=len(valores) - insertados + repetidas,
        descartados=descartados,
        problemas=tuple(problemas),
    )


def normalizar_punto(cruda: dict[str, Any]) -> tuple[int, str, tuple | None] | str:
    """Valida un renglón de `Puntos_Referencia`, o devuelve el motivo."""
    datos = renombrar(cruda)

    crudo = str(datos.get("numero") or "").strip()
    if not crudo:
        return "sin ID_QR"
    try:
        numero = int(float(crudo))
    except ValueError:
        return f"ID_QR ilegible ({crudo!r})"
    # El export de AppSheet trae una fila basura al final con ID_QR = 0 y todo
    # lo demás vacío. Y el schema exige `numero >= 1`.
    if numero < 1:
        return f"ID_QR fuera de rango ({numero})"

    nombre = _texto(datos.get("nombre"), MAX_NOMBRE_PUNTO)
    if not nombre:
        return f"punto {numero}: sin nombre"

    return (numero, nombre, parsear_gps(datos.get("gps")))


async def sincronizar_puntos(
    db: AsyncSession,
    crudas: Sequence[dict[str, Any]],
    *,
    desactivar_ausentes: bool = False,
) -> ResultadoSincronia:
    """Refresca el catálogo desde el export de `Puntos_Referencia`.

    Nunca borra: un punto que desaparece del archivo se marca `activo = False`
    con `--desactivar-ausentes`, porque los escaneos históricos siguen
    apuntando aquí y el cumplimiento de los turnos ya cerrados no debe cambiar.

    Va todo en UNA transacción: `puntos_rondin.numero` es único, así que un
    archivo que renumere puede violar el constraint a media pasada, y un
    catálogo importado a medias es peor que uno rechazado.
    """
    validos: list[tuple[int, str, tuple | None]] = []
    problemas: list[str] = []

    for cruda in crudas:
        resultado = normalizar_punto(cruda)
        if isinstance(resultado, str):
            problemas.append(resultado)
        else:
            validos.append(resultado)

    creados = actualizados = retirados = 0
    if validos:
        valores = [
            {
                "numero": numero,
                "nombre": nombre,
                # AppSheet no tiene una ubicación legible: `Ubicación_Referencia`
                # son coordenadas y el nombre YA es el lugar ("CASETA", "SILOS").
                "ubicacion": None,
                "ref_lat": gps[0] if gps else None,
                "ref_lon": gps[1] if gps else None,
                "activo": True,
            }
            for numero, nombre, gps in validos
        ]
        base = pg_insert(PuntoRondin).values(valores)
        sentencia = base.on_conflict_do_update(
            index_elements=[PuntoRondin.numero],
            set_={
                "nombre": base.excluded.nombre,
                "ref_lat": base.excluded.ref_lat,
                "ref_lon": base.excluded.ref_lon,
                "activo": True,
                "actualizado_at": func.now(),
            },
        # `xmax = 0` distingue el INSERT del UPDATE dentro del mismo upsert,
        # sin tener que leer la tabla antes para saber qué había.
        ).returning(PuntoRondin.numero, text("(xmax = 0) AS insertado"))

        filas = (await db.execute(sentencia)).all()
        creados = sum(1 for _, insertado in filas if insertado)
        actualizados = len(filas) - creados

        if desactivar_ausentes:
            presentes = [numero for numero, _, _ in validos]
            bajas = await db.execute(
                PuntoRondin.__table__.update()
                .where(
                    PuntoRondin.numero.notin_(presentes),
                    PuntoRondin.activo.is_(True),
                )
                .values(activo=False, actualizado_at=func.now())
            )
            retirados = bajas.rowcount or 0

        await db.commit()

    return ResultadoSincronia(
        creados=creados,
        actualizados=actualizados,
        retirados=retirados,
        descartados=len(problemas),
        problemas=tuple(problemas),
    )
