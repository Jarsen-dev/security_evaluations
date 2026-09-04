"""Pruebas del Control de Insumos: las salidas del almacén.

Dos cosas pueden salir mal aquí sin que nada falle de forma visible, y las dos
se prueban:

- **Que se descuente lo que no debía, o no se descuente lo que sí.** La regla
  vive en `piezas_a_descontar()` y la repite el CHECK
  `ck_control_insumos_descontado`. Si las dos versiones divergen, el registro y
  el stock dejan de cuadrar y nadie se entera hasta el conteo físico. Se
  contrastan una contra otra, igual que el semáforo del catálogo contrasta
  `estado_insumo()` contra `EXPRESIONES_ESTADO`.
- **Que la resta deje la existencia en negativo.** La guarda va dentro del
  `UPDATE`; aquí se comprueba que con la guarda la fila queda intacta.

Mismo estilo que el resto del repo: funciones puras y SQL contra SQLite en
memoria. Lo que necesita HTTP —el 422 y el 403— se verifica a mano contra el
contenedor.
"""

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.constants import (
    AREAS_VALIDAS,
    UNIDADES_MEDIDA,
    UNIDADES_PARCIALES,
    etiqueta_area,
)
from app.core.errors import ErrorDeNegocio
from app.schemas.control import ControlInsumoCrear
from app.services.control_insumos_service import es_parcial, piezas_a_descontar

ID_INSUMO = "3f1a5a9e-0000-4000-8000-000000000001"


# --- La regla ---------------------------------------------------------------


#: (unidad, consumo, termino, descontado esperado).
CASOS: list[tuple[str, int, bool | None, int]] = [
    # Lo que se cuenta por piezas baja siempre.
    ("PZA", 3, None, 3),
    ("TAB", 20, None, 20),
    ("PZA", 1, None, 1),
    # Lo que se mide a granel solo baja cuando el envase se acaba.
    ("GR", 2, True, 2),
    ("GR", 2, False, 0),
    ("ML", 5, True, 5),
    ("ML", 5, False, 0),
    ("MTS", 1, True, 1),
    ("MTS", 1, False, 0),
]


@pytest.mark.parametrize(("unidad", "consumo", "termino", "esperado"), CASOS)
def test_piezas_a_descontar(
    unidad: str, consumo: int, termino: bool | None, esperado: int
) -> None:
    assert piezas_a_descontar(unidad, consumo, termino) == esperado


def test_la_unidad_a_granel_exige_contestar() -> None:
    """Sin respuesta no se adivina: un "no" implícito descontaría 0 callado."""
    for unidad in sorted(UNIDADES_PARCIALES):
        with pytest.raises(ErrorDeNegocio):
            piezas_a_descontar(unidad, 5, None)


def test_un_termino_que_sobra_se_rechaza() -> None:
    """El panel solo lo manda para unidades a granel.

    Que llegue en una PZA significa que el insumo cambió de unidad entre la
    búsqueda y el guardado. Corregirlo en silencio descontaría lo que el
    operador creía que no se descontaba.
    """
    for unidad in ("PZA", "TAB"):
        with pytest.raises(ErrorDeNegocio):
            piezas_a_descontar(unidad, 5, True)
        with pytest.raises(ErrorDeNegocio):
            piezas_a_descontar(unidad, 5, False)


def test_las_unidades_del_catalogo_estan_todas_cubiertas() -> None:
    """Ninguna unidad se queda sin regla.

    Si mañana se agrega una a `UNIDADES_MEDIDA`, esta prueba obliga a decidir
    si se mide a granel en vez de dejar que caiga en la rama por omisión.
    """
    for unidad in UNIDADES_MEDIDA:
        termino = True if es_parcial(unidad) else None
        assert piezas_a_descontar(unidad, 7, termino) == 7


def test_el_descuento_es_todo_o_nada() -> None:
    """El invariante: nunca un descuento a medias.

    Es la única forma de que el registro y el stock dejen de cuadrar, y es lo
    mismo que dice `ck_control_insumos_descontado`.
    """
    for unidad in UNIDADES_MEDIDA:
        for consumo in (1, 2, 7, 999):
            for termino in ((True, False) if es_parcial(unidad) else (None,)):
                assert piezas_a_descontar(unidad, consumo, termino) in (0, consumo)


# --- La regla, contrastada contra el CHECK de la base ------------------------


#: El mismo CHECK de la migración, escrito para SQLite: `termino = 0` se
#: comporta igual que el `termino IS FALSE` de PostgreSQL (con NULL las dos dan
#: la rama del ELSE) y aquí sí es sintaxis válida.
TABLA_REGISTROS = """
CREATE TABLE registros_control_insumos (
    id            TEXT PRIMARY KEY,
    consumo       INTEGER NOT NULL,
    descontado    INTEGER NOT NULL,
    termino       BOOLEAN NULL,
    entregado_a   TEXT NOT NULL,
    CHECK (consumo > 0),
    CHECK (descontado = CASE WHEN termino = 0 THEN 0 ELSE consumo END),
    CHECK (length(trim(entregado_a)) > 0)
)
"""


@pytest.fixture()
def sesion() -> Session:
    motor = create_engine("sqlite://")
    with Session(motor) as sesion, sesion.begin():
        sesion.execute(text(TABLA_REGISTROS))
        yield sesion


def _insertar(
    sesion: Session, *, consumo: int, descontado: int, termino: bool | None
) -> None:
    sesion.execute(
        text(
            "INSERT INTO registros_control_insumos "
            "(id, consumo, descontado, termino, entregado_a) VALUES "
            "(:id, :consumo, :descontado, :termino, 'J. Ramírez')"
        ),
        {
            "id": f"{consumo}-{descontado}-{termino}",
            "consumo": consumo,
            "descontado": descontado,
            "termino": termino,
        },
    )


@pytest.mark.parametrize(("unidad", "consumo", "termino", "esperado"), CASOS)
def test_lo_que_calcula_el_servicio_lo_acepta_la_base(
    sesion: Session, unidad: str, consumo: int, termino: bool | None, esperado: int
) -> None:
    """Rama por rama: la función y el CHECK dicen lo mismo."""
    _insertar(
        sesion,
        consumo=consumo,
        descontado=piezas_a_descontar(unidad, consumo, termino),
        termino=termino,
    )


def test_la_base_rechaza_un_descuento_a_medias(sesion: Session) -> None:
    with pytest.raises(IntegrityError):
        _insertar(sesion, consumo=10, descontado=4, termino=None)


def test_la_base_rechaza_no_descontar_lo_que_si_se_termino(sesion: Session) -> None:
    """El caso que la versión ingenua del CHECK dejaba pasar.

    Con `descontado IN (0, consumo)`, un bug del servicio que guardara 0 en una
    entrega que sí debía descontar habría entrado sin protestar.
    """
    with pytest.raises(IntegrityError):
        _insertar(sesion, consumo=10, descontado=0, termino=True)
    with pytest.raises(IntegrityError):
        _insertar(sesion, consumo=10, descontado=0, termino=None)


def test_la_base_rechaza_a_quien_no_tiene_nombre(sesion: Session) -> None:
    with pytest.raises(IntegrityError):
        sesion.execute(
            text(
                "INSERT INTO registros_control_insumos "
                "(id, consumo, descontado, termino, entregado_a) VALUES "
                "('x', 1, 1, NULL, '   ')"
            )
        )


# --- La guarda de la resta --------------------------------------------------


TABLA_INSUMOS = """
CREATE TABLE insumos (
    id          TEXT PRIMARY KEY,
    existencia  INTEGER NOT NULL,
    CHECK (existencia >= 0)
)
"""

RESTA_CON_GUARDA = (
    "UPDATE insumos SET existencia = existencia - :n "
    "WHERE id = :id AND existencia >= :n"
)


@pytest.fixture()
def catalogo() -> Session:
    motor = create_engine("sqlite://")
    with Session(motor) as sesion, sesion.begin():
        sesion.execute(text(TABLA_INSUMOS))
        sesion.execute(
            text("INSERT INTO insumos (id, existencia) VALUES (:id, 3)"),
            {"id": ID_INSUMO},
        )
        yield sesion


def test_la_resta_baja_lo_que_hay(catalogo: Session) -> None:
    resultado = catalogo.execute(text(RESTA_CON_GUARDA), {"id": ID_INSUMO, "n": 2})

    assert resultado.rowcount == 1
    assert catalogo.scalar(text("SELECT existencia FROM insumos")) == 1


def test_la_guarda_impide_el_negativo_sin_tocar_la_fila(catalogo: Session) -> None:
    """Pedir más de lo que hay no descuenta nada y se nota en el `rowcount`.

    Sin la guarda, el `UPDATE` chocaría contra el CHECK de la existencia y
    saldría como 500 crudo en vez del 422 en español; y comprobar con un SELECT
    previo sería una carrera entre workers.
    """
    resultado = catalogo.execute(text(RESTA_CON_GUARDA), {"id": ID_INSUMO, "n": 5})

    assert resultado.rowcount == 0
    assert catalogo.scalar(text("SELECT existencia FROM insumos")) == 3


def test_dejar_la_existencia_en_cero_si_esta_permitido(catalogo: Session) -> None:
    resultado = catalogo.execute(text(RESTA_CON_GUARDA), {"id": ID_INSUMO, "n": 3})

    assert resultado.rowcount == 1
    assert catalogo.scalar(text("SELECT existencia FROM insumos")) == 0


# --- Lo que valida el schema ------------------------------------------------


def _datos(**cambios: object) -> dict[str, object]:
    base: dict[str, object] = {
        "insumo_id": ID_INSUMO,
        "entregado_a": "J. Ramírez",
        "area": "Ensamble",
        "consumo": 2,
    }
    base.update(cambios)
    return base


def test_el_area_se_guarda_sin_acento() -> None:
    """El acento es de la etiqueta, no del valor almacenado."""
    assert "Almacen" in AREAS_VALIDAS
    assert "Almacén" not in AREAS_VALIDAS
    assert etiqueta_area("Almacen") == "Almacén"

    assert ControlInsumoCrear.model_validate(_datos(area="Almacen")).area == "Almacen"
    with pytest.raises(ValidationError):
        ControlInsumoCrear.model_validate(_datos(area="Almacén"))


def test_un_area_inventada_se_rechaza() -> None:
    with pytest.raises(ValidationError):
        ControlInsumoCrear.model_validate(_datos(area="Taller"))


@pytest.mark.parametrize("consumo", [0, -1])
def test_el_consumo_tiene_que_ser_positivo(consumo: int) -> None:
    with pytest.raises(ValidationError):
        ControlInsumoCrear.model_validate(_datos(consumo=consumo))


def test_hace_falta_decir_a_quien_se_entrega() -> None:
    with pytest.raises(ValidationError):
        ControlInsumoCrear.model_validate(_datos(entregado_a="   "))
