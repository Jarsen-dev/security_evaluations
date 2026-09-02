"""Pruebas del semáforo de existencias del catálogo.

El semáforo se decide en dos sitios que tienen que coincidir siempre:
`estado_insumo()` clasifica la fila que se pinta en la tabla, y
`EXPRESIONES_ESTADO` traduce esa misma cascada a SQL para que el filtro por
estado se resuelva en la base sin romper el conteo ni la paginación. Si los dos
divergen, el filtro "bajo" devuelve renglones que la tabla pinta de otro color
y nadie se entera hasta que alguien resurte lo que no hacía falta.

Por eso la comparación no se hace a ojo: los mismos casos pasan por la función
y por una consulta de verdad contra SQLite en memoria.
"""

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.models.insumo import (
    ESTADO_BAJO,
    ESTADO_EXCEDIDO,
    ESTADO_MEDIO,
    ESTADO_NORMAL,
    ESTADO_SIN_TOPES,
    ESTADOS_INSUMO,
    EXPRESIONES_ESTADO,
    Insumo,
    estado_insumo,
)

#: (código, existencia, mínimo, máximo, estado esperado).
#:
#: Las fronteras son lo que importa: el 35 % y el 75 % son inclusivos hacia
#: abajo, y el mínimo capturado gana aunque el porcentaje diga otra cosa.
CASOS: list[tuple[str, int, int, int, str]] = [
    ("sin-max", 50, 10, 0, ESTADO_SIN_TOPES),
    ("vacio-sin-topes", 0, 0, 0, ESTADO_SIN_TOPES),
    ("excedido", 101, 0, 100, ESTADO_EXCEDIDO),
    ("justo-en-el-max", 100, 0, 100, ESTADO_NORMAL),
    ("verde-apenas", 76, 0, 100, ESTADO_NORMAL),
    ("frontera-75", 75, 0, 100, ESTADO_MEDIO),
    ("amarillo-apenas", 36, 0, 100, ESTADO_MEDIO),
    ("frontera-35", 35, 0, 100, ESTADO_BAJO),
    ("vacio", 0, 0, 100, ESTADO_BAJO),
    # 60 % del máximo pintaría amarillo, pero está por debajo del mínimo:
    # el mínimo es el punto en el que hay que resurtir y manda.
    ("bajo-el-minimo", 60, 80, 100, ESTADO_BAJO),
    # Frontera exacta del 35 %: es la que se iría al color equivocado si la
    # comparación se hiciera con 0.35 en coma flotante.
    ("frontera-exacta", 7, 0, 20, ESTADO_BAJO),
    ("min-igual-max", 10, 10, 10, ESTADO_NORMAL),
    ("min-igual-max-corto", 5, 10, 10, ESTADO_BAJO),
]


@pytest.mark.parametrize(("codigo", "existencia", "minimo", "maximo", "esperado"), CASOS)
def test_estado_insumo(
    codigo: str, existencia: int, minimo: int, maximo: int, esperado: str
) -> None:
    assert estado_insumo(existencia, minimo, maximo) == esperado


def test_un_insumo_cae_en_un_solo_estado() -> None:
    """La cascada cubre todo y no se solapa: cada fila tiene UN color."""
    for _, existencia, minimo, maximo, _ in CASOS:
        assert estado_insumo(existencia, minimo, maximo) in ESTADOS_INSUMO


@pytest.fixture
def sesion() -> Session:
    """Una base de juguete con los casos ya cargados.

    SQLite y no PostgreSQL porque lo que se prueba es la cascada de
    condiciones, que es aritmética entera y booleanos: no hay nada específico
    del motor. La tabla se crea a mano —y no con `metadata.create_all`— porque
    el modelo declara tipos de PostgreSQL (UUID, `gen_random_uuid()`) que
    SQLite no sabe construir; aquí solo hacen falta las cuatro columnas que la
    condición mira.
    """
    motor = create_engine("sqlite://")

    with Session(motor) as sesion:
        sesion.execute(
            text("""
            CREATE TABLE insumos (
                id                 TEXT PRIMARY KEY,
                codigo             TEXT NOT NULL,
                descripcion        TEXT,
                categoria          TEXT,
                unidad_medida      TEXT,
                proveedor          TEXT,
                ubicacion          TEXT,
                piezas_por_empaque INTEGER NOT NULL,
                existencia         INTEGER NOT NULL,
                minimo             INTEGER NOT NULL,
                maximo             INTEGER NOT NULL,
                creado_at          TEXT,
                actualizado_at     TEXT
            )
            """)
        )

        for indice, (codigo, existencia, minimo, maximo, _) in enumerate(CASOS):
            sesion.execute(
                text("""
                INSERT INTO insumos (
                    id, codigo, categoria, unidad_medida,
                    piezas_por_empaque, existencia, minimo, maximo
                ) VALUES (
                    :id, :codigo, 'Otros', 'PZA', 1, :existencia, :minimo, :maximo
                )
                """),
                {
                    "id": str(indice),
                    "codigo": codigo,
                    "existencia": existencia,
                    "minimo": minimo,
                    "maximo": maximo,
                },
            )

        yield sesion


@pytest.mark.parametrize("estado", ESTADOS_INSUMO)
def test_el_filtro_sql_coincide_con_la_funcion(sesion: Session, estado: str) -> None:
    """Rama por rama: lo que el filtro trae es lo que la tabla pinta."""
    traidos = set(
        sesion.scalars(select(Insumo.codigo).where(EXPRESIONES_ESTADO[estado])).all()
    )
    esperados = {
        codigo
        for codigo, existencia, minimo, maximo, _ in CASOS
        if estado_insumo(existencia, minimo, maximo) == estado
    }

    assert traidos == esperados
