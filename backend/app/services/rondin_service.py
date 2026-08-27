"""Rondines de seguridad: turnos, recorridos y tablero.

La asignación de escaneos a rondines es una traducción directa del panel de
Streamlit que este módulo sustituye (`asignar_rondines_por_puntos` en su
`main.py`), con los mismos números: turnos de 12 h desde las 07:30, seis
bloques de 2 h, y recorridos separados por 30 minutos de silencio.
"""

import secrets
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.constants import (
    GAP_RECORRIDO_MINUTOS,
    HORA_INICIO_TURNO,
    HORAS_TURNO,
    MINUTO_INICIO_TURNO,
    RONDINES_POR_TURNO,
)
from app.core.errors import ConflictoDeNegocio, RecursoNoEncontrado
from app.models.rondin import EscaneoRondin, PuntoRondin

TURNO_DIA = "dia"
TURNO_NOCHE = "noche"
TURNOS_VALIDOS = frozenset({TURNO_DIA, TURNO_NOCHE})

#: Duración de cada rondín, en horas.
HORAS_POR_RONDIN = HORAS_TURNO // RONDINES_POR_TURNO

# Mensaje único para token inexistente, punto inactivo o borrado. Distinguirlos
# permitiría sondear tokens desde fuera (misma decisión que
# `intento_service.CUESTIONARIO_NO_DISPONIBLE`).
PUNTO_NO_DISPONIBLE = "Este punto no está registrado. Avisa a tu supervisor."

NUMERO_DUPLICADO = "Ya existe un punto de control con ese número."
NO_EXISTE = "El punto de control no existe."

#: Reintentos ante colisión de token. Con 24 bytes aleatorios es improbable,
#: pero una colisión silenciosa dejaría dos puntos con el mismo QR.
MAX_INTENTOS_TOKEN = 5


def zona() -> ZoneInfo:
    """Zona horaria de la planta, donde el turno empieza a las 07:30."""
    return ZoneInfo(settings.ZONA_HORARIA)


def ahora_local() -> datetime:
    """La hora actual en la zona de la planta, con zona horaria puesta."""
    return datetime.now(tz=zona())


#: Fin del turno de día, derivado de las mismas constantes que ``rango_turno``
#: (7:30 + 12 h = 19:30). Escrito literal y no con una suma de horas: sumar
#: podría desbordar el día si algún valor cambiara.
_FIN_TURNO_DIA = time(19, 30)


def turno_actual(momento: datetime | None = None) -> str:
    """``TURNO_DIA`` o ``TURNO_NOCHE`` para el instante dado (u ahora).

    Mismo límite que usan los rondines: día de 07:30 a 19:30, noche el resto.
    Un ``momento`` con otra zona horaria se convierte a la de la planta antes
    de comparar la hora.
    """
    local = (momento or datetime.now(tz=zona())).astimezone(zona())
    inicio_dia = time(HORA_INICIO_TURNO, MINUTO_INICIO_TURNO)
    return TURNO_DIA if inicio_dia <= local.time() < _FIN_TURNO_DIA else TURNO_NOCHE


def rango_turno(fecha: date, turno: str) -> tuple[datetime, datetime]:
    """Devuelve el inicio y el fin de un turno, con zona horaria.

    La fecha es la de INICIO del turno, no la del calendario: el turno de
    noche del 25 termina a las 07:30 del 26, y se consulta pidiendo el 25.
    """
    inicio_dia = datetime.combine(
        fecha, time(HORA_INICIO_TURNO, MINUTO_INICIO_TURNO), tzinfo=zona()
    )

    if turno == TURNO_DIA:
        inicio = inicio_dia
    else:
        inicio = inicio_dia + timedelta(hours=HORAS_TURNO)

    return inicio, inicio + timedelta(hours=HORAS_TURNO)


def _indice_rondin(momento: datetime, inicio_turno: datetime) -> int:
    """Bloque de dos horas al que pertenece un instante, de 0 a 5."""
    transcurrido = (momento - inicio_turno).total_seconds() / 3600
    indice = int(transcurrido // HORAS_POR_RONDIN)
    return max(0, min(RONDINES_POR_TURNO - 1, indice))


def asignar_rondines(
    escaneos: list[EscaneoRondin], inicio_turno: datetime
) -> dict[int, int]:
    """Asigna cada escaneo a un rondín, en tres pasos.

    Devuelve ``{id_del_escaneo: índice de rondín}``.

    1. **Agrupación por silencio**: más de 30 minutos sin escanear significa
       que empezó un recorrido nuevo.
    2. **Voto por mayoría**: el recorrido completo se asigna al bloque donde
       cayó la mayoría de sus puntos. Sin esto, un recorrido que cruza las
       09:30 se partiría en dos columnas del tablero y ninguna de las dos
       reflejaría lo que hizo el guardia.
    3. Todos los escaneos del grupo heredan ese rondín.

    Esto se hace en Python y no en SQL a propósito, y es una excepción
    justificada a la regla 4: son pasos secuenciales que dependen del escaneo
    anterior, no una agregación. Además el conjunto es pequeño — un turno son
    como mucho `puntos activos × 6` filas, no las decenas de miles que
    motivaron esa regla.
    """
    if not escaneos:
        return {}

    ordenados = sorted(escaneos, key=lambda e: e.escaneado_at)

    # Paso 1: cortar en recorridos.
    grupos: list[list[EscaneoRondin]] = [[ordenados[0]]]
    for anterior, actual in zip(ordenados, ordenados[1:], strict=False):
        minutos = (actual.escaneado_at - anterior.escaneado_at).total_seconds() / 60
        if minutos > GAP_RECORRIDO_MINUTOS:
            grupos.append([])
        grupos[-1].append(actual)

    # Pasos 2 y 3: voto por mayoría y herencia.
    asignacion: dict[int, int] = {}
    for grupo in grupos:
        votos = Counter(
            _indice_rondin(escaneo.escaneado_at, inicio_turno) for escaneo in grupo
        )
        # `most_common` desempata por orden de aparición, que es el más
        # temprano: el recorrido se queda en el bloque donde arrancó.
        ganador = votos.most_common(1)[0][0]
        for escaneo in grupo:
            asignacion[escaneo.id] = ganador

    return asignacion


# --- Puntos de control -----------------------------------------------------


async def _token_libre(db: AsyncSession) -> str:
    """Genera un token opaco que no choque con otro punto."""
    for _ in range(MAX_INTENTOS_TOKEN):
        token = secrets.token_urlsafe(24)
        existe = await db.scalar(
            select(PuntoRondin.id).where(PuntoRondin.token_publico == token)
        )
        if existe is None:
            return token

    raise ConflictoDeNegocio(
        "No se pudo generar un código único para el punto. Intenta de nuevo."
    )


async def listar_puntos(
    db: AsyncSession, *, solo_activos: bool = False
) -> list[PuntoRondin]:
    """Puntos de control ordenados por número."""
    consulta = select(PuntoRondin).order_by(PuntoRondin.numero)
    if solo_activos:
        consulta = consulta.where(PuntoRondin.activo.is_(True))

    return list((await db.scalars(consulta)).all())


async def obtener_punto(db: AsyncSession, punto_id: uuid.UUID) -> PuntoRondin:
    """Busca un punto o lanza 404."""
    punto = await db.scalar(select(PuntoRondin).where(PuntoRondin.id == punto_id))
    if punto is None:
        raise RecursoNoEncontrado(NO_EXISTE)
    return punto


async def crear_punto(
    db: AsyncSession, *, numero: int, nombre: str, ubicacion: str | None
) -> PuntoRondin:
    """Da de alta un punto y le genera su código QR."""
    punto = PuntoRondin(
        numero=numero,
        nombre=nombre,
        ubicacion=ubicacion,
        token_publico=await _token_libre(db),
    )
    db.add(punto)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictoDeNegocio(NUMERO_DUPLICADO) from exc

    await db.refresh(punto)
    return punto


async def actualizar_punto(
    db: AsyncSession,
    punto_id: uuid.UUID,
    *,
    numero: int,
    nombre: str,
    ubicacion: str | None,
    activo: bool,
) -> PuntoRondin:
    """Actualiza un punto sin tocar su token: el QR impreso sigue sirviendo."""
    punto = await obtener_punto(db, punto_id)

    punto.numero = numero
    punto.nombre = nombre
    punto.ubicacion = ubicacion
    punto.activo = activo
    punto.actualizado_at = datetime.now(tz=zona())

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictoDeNegocio(NUMERO_DUPLICADO) from exc

    await db.refresh(punto)
    return punto


async def eliminar_punto(db: AsyncSession, punto_id: uuid.UUID) -> str:
    """Borra un punto y devuelve su nombre para la bitácora.

    Los escaneos históricos se conservan: el FK queda en NULL y cada uno
    guarda su `punto_numero`. Aun así, desactivar suele ser mejor que borrar.
    """
    punto = await obtener_punto(db, punto_id)
    etiqueta = f"{punto.numero} — {punto.nombre}"
    await db.delete(punto)
    await db.commit()
    return etiqueta


# --- Escaneo público -------------------------------------------------------


async def registrar_escaneo(
    db: AsyncSession, token: str, *, ip: str | None
) -> PuntoRondin:
    """Registra la visita a un punto y devuelve el punto escaneado.

    La hora la pone el servidor, no el celular: el reloj de un teléfono
    cualquiera decidiría a qué rondín pertenece la visita.
    """
    punto = await db.scalar(
        select(PuntoRondin).where(
            PuntoRondin.token_publico == token, PuntoRondin.activo.is_(True)
        )
    )
    if punto is None:
        raise RecursoNoEncontrado(PUNTO_NO_DISPONIBLE)

    db.add(EscaneoRondin(punto_id=punto.id, punto_numero=punto.numero, ip=ip))
    await db.commit()
    return punto


# --- Tablero ---------------------------------------------------------------


@dataclass(frozen=True)
class FilaTablero:
    """Un punto de control con sus seis celdas."""

    numero: int
    nombre: str
    ubicacion: str | None
    #: Hora del escaneo por rondín, o ``None`` si no se visitó.
    rondines: list[datetime | None]

    @property
    def visitados(self) -> int:
        return sum(1 for celda in self.rondines if celda is not None)


async def construir_tablero(
    db: AsyncSession, fecha: date, turno: str
) -> dict[str, Any]:
    """Arma la matriz de puntos × rondines de un turno, con sus indicadores.

    Devuelve todo resuelto para que el frontend solo pinte: la matriz, el
    porcentaje por rondín, el cumplimiento general, el rondín en curso y su
    avance.
    """
    inicio, fin = rango_turno(fecha, turno)

    puntos = await listar_puntos(db, solo_activos=True)

    # El filtro por rango sí va en SQL, sobre el índice de `escaneado_at`.
    escaneos = list(
        (
            await db.scalars(
                select(EscaneoRondin)
                .where(
                    EscaneoRondin.escaneado_at >= inicio,
                    EscaneoRondin.escaneado_at < fin,
                )
                .order_by(EscaneoRondin.escaneado_at)
            )
        ).all()
    )

    asignacion = asignar_rondines(escaneos, inicio)

    # Primer escaneo de cada (punto, rondín): si alguien pasa dos veces por el
    # mismo punto en el mismo rondín, vale la primera visita.
    celdas: dict[tuple[int, int], datetime] = {}
    for escaneo in escaneos:
        clave = (escaneo.punto_numero, asignacion[escaneo.id])
        if clave not in celdas:
            celdas[clave] = escaneo.escaneado_at

    filas = [
        FilaTablero(
            numero=punto.numero,
            nombre=punto.nombre,
            ubicacion=punto.ubicacion,
            rondines=[
                celdas.get((punto.numero, indice))
                for indice in range(RONDINES_POR_TURNO)
            ],
        )
        for punto in puntos
    ]

    total_celdas = len(puntos) * RONDINES_POR_TURNO
    visitados = sum(fila.visitados for fila in filas)

    por_rondin = [
        sum(1 for fila in filas if fila.rondines[indice] is not None)
        for indice in range(RONDINES_POR_TURNO)
    ]

    rondin_actual = _rondin_en_curso(inicio, fin)

    return {
        "fecha": fecha,
        "turno": turno,
        "inicio": inicio,
        "fin": fin,
        "puntos_activos": len(puntos),
        "rondines": RONDINES_POR_TURNO,
        "filas": filas,
        "visitados": visitados,
        "total": total_celdas,
        "cumplimiento": (visitados / total_celdas * 100) if total_celdas else 0.0,
        "por_rondin": por_rondin,
        "rondin_actual": rondin_actual,
        "avance_actual": (
            por_rondin[rondin_actual] if rondin_actual is not None else None
        ),
    }


def _rondin_en_curso(inicio: datetime, fin: datetime) -> int | None:
    """Índice del rondín que corre ahora, o ``None`` si el turno no está vivo.

    Se calcula con el reloj, no con el último escaneo: si el guardia lleva una
    hora sin escanear nada, el tablero debe seguir diciendo en qué rondín va,
    que es justo cuando interesa mirarlo.
    """
    ahora = datetime.now(tz=zona())
    if not inicio <= ahora < fin:
        return None
    return _indice_rondin(ahora, inicio)


async def contar_escaneos(db: AsyncSession, fecha: date, turno: str) -> int:
    """Escaneos de un turno. Se usa para no mandar reportes vacíos."""
    inicio, fin = rango_turno(fecha, turno)
    total = await db.scalar(
        select(func.count(EscaneoRondin.id)).where(
            EscaneoRondin.escaneado_at >= inicio, EscaneoRondin.escaneado_at < fin
        )
    )
    return total or 0
