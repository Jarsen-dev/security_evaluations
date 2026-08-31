"""Pruebas de la lógica pura de los rondines de seguridad.

Ninguna toca la base de datos: `asignar_rondines`, `rango_turno`,
`turno_actual`, `_indice_rondin` y `_turno_que_termina` son funciones
síncronas sobre fechas y listas. Es la lógica más delicada del módulo —el voto
por mayoría decide qué columna del tablero se llena— y hasta ahora no tenía
ningún caso.
"""

from datetime import datetime, time, timedelta
from types import SimpleNamespace

import pytest

from app.core.constants import RONDINES_POR_TURNO
from app.services import rondin_service as rs
from app.services import reporte_automatico as ra

ZONA = rs.zona()


def _momento(dia: int, hora: int, minuto: int = 0) -> datetime:
    """Un instante de agosto de 2026 en la hora de la planta."""
    return datetime(2026, 8, dia, hora, minuto, tzinfo=ZONA)


def _escaneo(
    identificador: int, momento: datetime, punto: int
) -> SimpleNamespace:
    """Lo mínimo que `asignar_rondines` toca de un `EscaneoRondin`."""
    return SimpleNamespace(
        id=identificador,
        escaneado_at=momento,
        punto_id=f"punto-{punto}",
        punto_numero=punto,
    )


def _ronda(
    desde: datetime, puntos: int = 5, cada_minutos: int = 3, primer_id: int = 1
) -> list[SimpleNamespace]:
    """Un recorrido completo: un escaneo por cada punto, uno tras otro.

    Siempre recorre los mismos puntos (1..n), como haría un guardia dando otra
    vuelta a la planta.
    """
    return [
        _escaneo(
            primer_id + indice,
            desde + timedelta(minutes=cada_minutos * indice),
            punto=indice + 1,
        )
        for indice in range(puntos)
    ]


# --- rango_turno -----------------------------------------------------------


def test_rango_turno_dia():
    inicio, fin = rs.rango_turno(_momento(25, 0).date(), rs.TURNO_DIA)

    assert inicio == _momento(25, 7, 30)
    assert fin == _momento(25, 19, 30)


def test_rango_turno_noche_cruza_la_medianoche():
    """La noche del 25 se consulta pidiendo el 25 y termina el 26."""
    inicio, fin = rs.rango_turno(_momento(25, 0).date(), rs.TURNO_NOCHE)

    assert inicio == _momento(25, 19, 30)
    assert fin == _momento(26, 7, 30)


def test_los_dos_turnos_cubren_el_dia_sin_huecos():
    _, fin_dia = rs.rango_turno(_momento(25, 0).date(), rs.TURNO_DIA)
    inicio_noche, _ = rs.rango_turno(_momento(25, 0).date(), rs.TURNO_NOCHE)

    assert fin_dia == inicio_noche


# --- turno_actual ----------------------------------------------------------


@pytest.mark.parametrize(
    ("hora", "minuto", "esperado"),
    [
        (7, 29, rs.TURNO_NOCHE),  # justo antes del cambio
        (7, 30, rs.TURNO_DIA),  # el instante del cambio ya es día
        (12, 0, rs.TURNO_DIA),
        (19, 29, rs.TURNO_DIA),
        (19, 30, rs.TURNO_NOCHE),
        (23, 59, rs.TURNO_NOCHE),
        (0, 30, rs.TURNO_NOCHE),
    ],
)
def test_turno_actual_en_las_fronteras(hora: int, minuto: int, esperado: str):
    assert rs.turno_actual(_momento(25, hora, minuto)) == esperado


def test_turno_actual_convierte_desde_otra_zona():
    """Un instante en UTC se compara contra el reloj de la planta, no el suyo."""
    from datetime import timezone

    # 18:00 UTC son las 12:00 en Monterrey: turno de día, no de noche.
    en_utc = datetime(2026, 8, 25, 18, 0, tzinfo=timezone.utc)

    assert rs.turno_actual(en_utc) == rs.TURNO_DIA


# --- _indice_rondin --------------------------------------------------------


@pytest.mark.parametrize(
    ("hora", "minuto", "esperado"),
    [
        (7, 30, 0),  # arranque del turno
        (9, 29, 0),  # último minuto del primer bloque
        (9, 30, 1),  # frontera exacta
        (17, 30, 5),  # último bloque
        (19, 29, 5),
    ],
)
def test_indice_rondin(hora: int, minuto: int, esperado: int):
    inicio = _momento(25, 7, 30)

    assert rs._indice_rondin(_momento(25, hora, minuto), inicio) == esperado


def test_indice_rondin_se_recorta_a_los_extremos():
    """Un escaneo fuera del turno no puede caer en un bloque inexistente."""
    inicio = _momento(25, 7, 30)

    assert rs._indice_rondin(_momento(25, 3, 0), inicio) == 0
    assert rs._indice_rondin(_momento(26, 6, 0), inicio) == RONDINES_POR_TURNO - 1


# --- asignar_rondines ------------------------------------------------------


def test_sin_escaneos_no_hay_asignacion():
    assert rs.asignar_rondines([], _momento(25, 7, 30)) == {}


def test_una_ronda_completa_cae_en_un_solo_bloque():
    inicio = _momento(25, 7, 30)
    escaneos = _ronda(_momento(25, 8, 0))

    asignacion = rs.asignar_rondines(escaneos, inicio)

    assert set(asignacion.values()) == {0}


def test_una_ronda_que_cruza_la_frontera_no_se_parte():
    """El voto por mayoría mantiene junto un recorrido a caballo del cambio.

    Cuatro de los cinco puntos caen antes de las 09:30; el quinto después. El
    recorrido entero se queda en el bloque 0, que es donde el guardia lo hizo.
    """
    inicio = _momento(25, 7, 30)
    escaneos = _ronda(_momento(25, 9, 18), puntos=5, cada_minutos=3)

    asignacion = rs.asignar_rondines(escaneos, inicio)

    assert set(asignacion.values()) == {0}


def test_dos_rondas_en_bloques_distintos_no_se_funden():
    """La regresión que motivó el corte por frontera de bloque.

    Una ronda al final del bloque 0 y otra al inicio del bloque 1, separadas
    por menos de los 30 minutos de silencio. Antes se fundían en un grupo, el
    voto por mayoría las mandaba a un solo rondín y la segunda visita a cada
    punto se descartaba: el guardia hacía dos rondas y el tablero contaba una.
    """
    inicio = _momento(25, 7, 30)
    primera = _ronda(_momento(25, 9, 10), primer_id=1)
    segunda = _ronda(_momento(25, 9, 40), primer_id=100)

    asignacion = rs.asignar_rondines([*primera, *segunda], inicio)

    assert {asignacion[e.id] for e in primera} == {0}
    assert {asignacion[e.id] for e in segunda} == {1}


def test_dos_vueltas_dentro_del_mismo_bloque_comparten_rondin():
    """Dos vueltas seguidas en el mismo bloque solo pueden llenar una columna.

    El tablero tiene una celda por (punto, rondín), así que la segunda vuelta
    del bloque 0 no gana columna propia: se queda con la primera visita. Eso es
    la regla de negocio, no un defecto.
    """
    inicio = _momento(25, 7, 30)
    primera = _ronda(_momento(25, 7, 35), primer_id=1)
    segunda = _ronda(_momento(25, 8, 40), primer_id=100)

    asignacion = rs.asignar_rondines([*primera, *segunda], inicio)

    assert set(asignacion.values()) == {0}


def test_el_orden_de_entrada_no_altera_el_resultado():
    inicio = _momento(25, 7, 30)
    escaneos = _ronda(_momento(25, 8, 0))

    derecho = rs.asignar_rondines(list(escaneos), inicio)
    revuelto = rs.asignar_rondines(list(reversed(escaneos)), inicio)

    assert derecho == revuelto


# --- _rondines_transcurridos ----------------------------------------------


def test_un_turno_ya_cerrado_cuenta_los_seis_bloques(monkeypatch):
    inicio, fin = rs.rango_turno(_momento(25, 0).date(), rs.TURNO_DIA)
    monkeypatch.setattr(rs, "datetime", _reloj(_momento(26, 12, 0)))

    assert rs._rondines_transcurridos(inicio, fin) == RONDINES_POR_TURNO


def test_un_turno_que_no_empieza_no_cuenta_ninguno(monkeypatch):
    inicio, fin = rs.rango_turno(_momento(25, 0).date(), rs.TURNO_DIA)
    monkeypatch.setattr(rs, "datetime", _reloj(_momento(25, 6, 0)))

    assert rs._rondines_transcurridos(inicio, fin) == 0


def test_a_media_manana_solo_cuentan_los_bloques_vividos(monkeypatch):
    """Lo que impide que el cumplimiento salga clavado por debajo del 17 %."""
    inicio, fin = rs.rango_turno(_momento(25, 0).date(), rs.TURNO_DIA)
    monkeypatch.setattr(rs, "datetime", _reloj(_momento(25, 10, 0)))

    # 10:00 va en el segundo bloque (09:30-11:30): dos transcurridos.
    assert rs._rondines_transcurridos(inicio, fin) == 2


def _reloj(fijo: datetime):
    """Un sustituto de `datetime` cuyo `now()` siempre devuelve `fijo`."""

    class Reloj(datetime):
        @classmethod
        def now(cls, tz=None):  # noqa: ANN001, ANN206
            return fijo.astimezone(tz) if tz else fijo

    return Reloj


# --- reporte automático ----------------------------------------------------


def test_a_las_0730_cierra_la_noche_que_empezo_ayer():
    pendiente = ra._turno_que_termina(_momento(26, 7, 32))

    assert pendiente == (_momento(25, 0).date(), rs.TURNO_NOCHE)


def test_a_las_1930_cierra_el_dia_de_hoy():
    pendiente = ra._turno_que_termina(_momento(25, 19, 31))

    assert pendiente == (_momento(25, 0).date(), rs.TURNO_DIA)


@pytest.mark.parametrize(
    ("hora", "minuto"),
    [
        (7, 29),  # antes de que abra la ventana
        (7, 35),  # justo cuando cierra
        (12, 32),  # hora que no es cambio de turno
        (19, 29),
    ],
)
def test_fuera_de_la_ventana_no_hay_turno_que_cerrar(hora: int, minuto: int):
    assert ra._turno_que_termina(_momento(25, hora, minuto)) is None
