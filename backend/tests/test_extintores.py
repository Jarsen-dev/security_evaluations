"""Pruebas del control de Extintores.

Dos cosas pueden salir mal aquí sin que nada falle de forma visible:

- **Que el semáforo del vencimiento y su filtro digan cosas distintas.** La
  cascada vive en `estado_vencimiento()` y se repite en SQL en
  `expresiones_estado()`; si divergen, el filtro "vence este mes" trae
  extintores que la tabla pinta de otro color y nadie lo nota. Se contrastan
  rama por rama, igual que el semáforo del inventario.
- **Que una hoja a medias pase por evidencia.** Las reglas de los doce puntos
  viven en `_validar_puntos()`.

Mismo estilo que el resto del repo: funciones puras y SQL contra SQLite en
memoria, sin infraestructura async.
"""

from dataclasses import dataclass
from datetime import date

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.core.controles_catalogo import PUNTOS_EXTINTOR, etiqueta_punto_extintor
from app.core.errors import ErrorDeNegocio
from app.core.fechas import dias_del_mes, sumar_meses
from app.models.extintor import (
    ESTADO_CRITICO,
    ESTADO_POR_VENCER,
    ESTADO_VENCIDO,
    ESTADO_VIGENTE,
    ESTADOS_EXTINTOR,
    Extintor,
    estado_vencimiento,
    expresiones_estado,
)
from app.services.extintor_service import _validar_puntos

HOY = date(2026, 9, 4)


# --- Aritmética de meses ----------------------------------------------------


@pytest.mark.parametrize(
    ("dia", "meses", "esperado"),
    [
        # El 31 no existe en febrero: se ajusta al último día equivalente.
        (date(2026, 1, 31), 1, date(2026, 2, 28)),
        (date(2024, 1, 31), 1, date(2024, 2, 29)),
        # Dos meses se cuentan DESDE la fecha original. Encadenar dos llamadas
        # daría el 28 de marzo y movería tres días la frontera del semáforo.
        (date(2026, 1, 31), 2, date(2026, 3, 31)),
        (date(2026, 12, 31), 1, date(2027, 1, 31)),
        (date(2026, 11, 30), 2, date(2027, 1, 30)),
        (date(2026, 9, 4), 0, date(2026, 9, 4)),
    ],
)
def test_sumar_meses(dia: date, meses: int, esperado: date) -> None:
    assert sumar_meses(dia, meses) == esperado


def test_la_deriva_que_se_evita() -> None:
    """Encadenar no es lo mismo que sumar, y por eso `sumar_meses` toma `n`."""
    encadenado = sumar_meses(sumar_meses(date(2026, 1, 31), 1), 1)
    assert encadenado != sumar_meses(date(2026, 1, 31), 2)


@pytest.mark.parametrize(
    ("ano", "mes", "esperado"),
    [(2026, 2, 28), (2024, 2, 29), (2000, 2, 29), (1900, 2, 28), (2026, 4, 30)],
)
def test_dias_del_mes(ano: int, mes: int, esperado: int) -> None:
    assert dias_del_mes(ano, mes) == esperado


# --- El semáforo ------------------------------------------------------------


#: (folio, vencimiento, estado esperado). Las fronteras son lo que importa.
CASOS: list[tuple[str, date, str]] = [
    ("vencido-ayer", date(2026, 9, 3), ESTADO_VENCIDO),
    ("vence-hoy", HOY, ESTADO_CRITICO),
    ("frontera-un-mes", date(2026, 10, 4), ESTADO_CRITICO),
    ("un-dia-despues", date(2026, 10, 5), ESTADO_POR_VENCER),
    ("frontera-dos-meses", date(2026, 11, 4), ESTADO_POR_VENCER),
    ("dos-meses-y-un-dia", date(2026, 11, 5), ESTADO_VIGENTE),
    ("lejano", date(2027, 6, 1), ESTADO_VIGENTE),
    ("muy-vencido", date(2025, 1, 1), ESTADO_VENCIDO),
]


@pytest.mark.parametrize(("folio", "vencimiento", "esperado"), CASOS)
def test_estado_vencimiento(folio: str, vencimiento: date, esperado: str) -> None:
    assert estado_vencimiento(vencimiento, HOY) == esperado


def test_un_extintor_cae_en_un_solo_estado() -> None:
    """La cascada cubre todo el calendario y no se solapa."""
    for _, vencimiento, _ in CASOS:
        estados = [
            estado
            for estado in ESTADOS_EXTINTOR
            if estado_vencimiento(vencimiento, HOY) == estado
        ]
        assert len(estados) == 1


@pytest.fixture()
def sesion() -> Session:
    """Los mismos extintores de `CASOS`, en SQLite.

    La tabla se crea a mano y no con `metadata.create_all`: el modelo declara
    tipos de PostgreSQL que SQLite no sabe construir.
    """
    motor = create_engine("sqlite://")
    with Session(motor) as sesion, sesion.begin():
        sesion.execute(
            text("""
            CREATE TABLE extintores (
                id TEXT PRIMARY KEY, folio TEXT, modelo TEXT, capacidad TEXT,
                tipo TEXT, ubicacion TEXT, vencimiento DATE,
                creado_at TEXT, actualizado_at TEXT
            )
            """)
        )
        for indice, (folio, vencimiento, _) in enumerate(CASOS):
            sesion.execute(
                text("""
                INSERT INTO extintores
                    (id, folio, modelo, capacidad, tipo, ubicacion, vencimiento)
                VALUES (:id, :folio, 'Amerex', '4.5 kg', 'CO2', 'Almacén', :venc)
                """),
                {"id": str(indice), "folio": folio, "venc": vencimiento},
            )
        yield sesion


@pytest.mark.parametrize("estado", ESTADOS_EXTINTOR)
def test_el_filtro_sql_coincide_con_la_funcion(sesion: Session, estado: str) -> None:
    """Rama por rama: lo que el filtro trae es lo que la tabla pinta."""
    traidos = set(
        sesion.scalars(
            select(Extintor.folio).where(expresiones_estado(HOY)[estado])
        ).all()
    )
    esperados = {
        folio
        for folio, vencimiento, _ in CASOS
        if estado_vencimiento(vencimiento, HOY) == estado
    }

    assert traidos == esperados


def test_el_filtro_reparte_todas_las_filas(sesion: Session) -> None:
    """Ningún extintor se queda fuera de los cuatro estados."""
    # Por `folio` y no por `id`: la columna del modelo es UUID y los ids de la
    # tabla de prueba son enteros de texto.
    total = sum(
        len(
            sesion.scalars(
                select(Extintor.folio).where(expresiones_estado(HOY)[e])
            ).all()
        )
        for e in ESTADOS_EXTINTOR
    )
    assert total == len(CASOS)


# --- El catálogo de puntos --------------------------------------------------


def test_el_orden_de_los_puntos_es_el_contrato() -> None:
    """La posición en la tupla ES el `orden` guardado en la base.

    Reordenarla reescribiría el pasado: la revisión de marzo diría que el punto
    3 era otro. Un punto nuevo se añade AL FINAL.
    """
    assert [punto.clave for punto in PUNTOS_EXTINTOR] == [
        "ubicacion",
        "manometro",
        "cilindro",
        "manguera",
        "boquillas",
        "palanca",
        "manija",
        "etiqueta",
        "valvula",
        "presion",
        "seguro",
        "base",
    ]


def test_la_etiqueta_tolera_un_orden_viejo() -> None:
    """Un registro que apunte a un punto retirado no puede tumbar el Excel."""
    assert etiqueta_punto_extintor(0) == PUNTOS_EXTINTOR[0].etiqueta
    assert etiqueta_punto_extintor(99) == "Punto 100"


# --- Las reglas de la revisión ---------------------------------------------


@dataclass
class _Punto:
    orden: int
    valor: str
    observaciones: str | None = None


def _hoja(**cambios: str) -> list[_Punto]:
    """Los doce puntos, todos conformes salvo lo que se indique."""
    puntos = [_Punto(orden=i, valor="ok") for i in range(len(PUNTOS_EXTINTOR))]
    for orden, valor in cambios.items():
        puntos[int(orden.removeprefix("p"))] = _Punto(
            orden=int(orden.removeprefix("p")), valor=valor, observaciones="Suelto"
        )
    return puntos


FOTO = [(b"\xff\xd8\xff", "image/jpeg")]


def test_una_hoja_completa_y_conforme_no_tiene_anomalias() -> None:
    assert _validar_puntos(_hoja(), {}) == 0


def test_se_cuentan_las_anomalias() -> None:
    assert _validar_puntos(_hoja(p1="no_ok", p4="no_ok"), {1: FOTO, 4: FOTO}) == 2


def test_faltan_puntos() -> None:
    """Una hoja a medias no sirve como evidencia."""
    with pytest.raises(ErrorDeNegocio):
        _validar_puntos(_hoja()[:5], {})


def test_un_punto_repetido_se_rechaza() -> None:
    puntos = _hoja()
    puntos.append(_Punto(orden=0, valor="ok"))
    with pytest.raises(ErrorDeNegocio):
        _validar_puntos(puntos, {})


def test_inconforme_sin_foto() -> None:
    with pytest.raises(ErrorDeNegocio):
        _validar_puntos(_hoja(p2="no_ok"), {})


def test_conforme_con_foto() -> None:
    """La evidencia acompaña al hallazgo, no a lo que salió bien."""
    with pytest.raises(ErrorDeNegocio):
        _validar_puntos(_hoja(), {3: FOTO})


def test_tope_de_fotos_por_punto() -> None:
    with pytest.raises(ErrorDeNegocio):
        _validar_puntos(_hoja(p0="no_ok"), {0: FOTO * 5})
