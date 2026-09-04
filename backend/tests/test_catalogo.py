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

from io import BytesIO

import pytest
from openpyxl import Workbook
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.schemas.catalogo import InsumoCrear
from app.services import catalogo_excel
from app.services.insumo_service import CAMPOS_ACTUALIZABLES, _aplicar_cambios
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


# --- Reimportar el Excel ----------------------------------------------------
#
# La importación corrige lo que ya existe, y ahí hay dos formas de perder datos
# sin que nada falle: pisar la existencia —que la mueven las recepciones, no el
# archivo— y borrar una columna que el Excel simplemente no traía. Las dos se
# deciden en `_aplicar_cambios()` y en el `columnas` del lector, que no
# necesitan base de datos para probarse.


def _insumo(**cambios: object) -> Insumo:
    """Un insumo ya capturado, sin sesión de por medio."""
    datos: dict[str, object] = {
        "codigo": "GN-100-M",
        "descripcion": "Guantes de nitrilo talla M",
        "categoria": "EPP",
        "unidad_medida": "PZA",
        "proveedor": "Suministros del Norte",
        "ubicacion": "Anaquel A3",
        "piezas_por_empaque": 100,
        "existencia": 1200,
        "minimo": 500,
        "maximo": 2000,
    }
    datos.update(cambios)
    return Insumo(**datos)


def _fila(**cambios: object) -> InsumoCrear:
    """El mismo insumo tal como llega del Excel."""
    datos: dict[str, object] = {
        "codigo": "GN-100-M",
        "descripcion": "Guantes de nitrilo talla M",
        "categoria": "EPP",
        "unidad_medida": "PZA",
        "proveedor": "Suministros del Norte",
        "ubicacion": "Anaquel A3",
        "piezas_por_empaque": 100,
        "existencia": 1200,
        "minimo": 500,
        "maximo": 2000,
    }
    datos.update(cambios)
    return InsumoCrear.model_validate(datos)


def test_la_existencia_nunca_es_actualizable() -> None:
    """La regla que sostiene todo lo demás.

    Es el único número que mueve el propio sistema: confirmar una recepción le
    suma piezas. Si algún día entra a la lista, un Excel exportado la semana
    pasada borra las entradas de almacén de esta.
    """
    assert "existencia" not in CAMPOS_ACTUALIZABLES
    assert "codigo" not in CAMPOS_ACTUALIZABLES
    assert "descripcion" not in CAMPOS_ACTUALIZABLES


def test_una_fila_identica_no_cambia_nada() -> None:
    """Reimportar el mismo archivo dos veces es inocuo la segunda."""
    insumo = _insumo()

    assert _aplicar_cambios(insumo, _fila(), CAMPOS_ACTUALIZABLES) is False
    assert insumo.actualizado_at is None


def test_solo_se_toca_lo_distinto() -> None:
    """El caso real: se añadió la unidad de medida a un producto ya capturado."""
    insumo = _insumo(unidad_medida="PZA")

    assert _aplicar_cambios(insumo, _fila(unidad_medida="GR"), CAMPOS_ACTUALIZABLES)

    assert insumo.unidad_medida == "GR"
    assert insumo.actualizado_at is not None
    # Lo demás se queda como estaba.
    assert insumo.proveedor == "Suministros del Norte"
    assert insumo.minimo == 500


def test_la_existencia_del_archivo_se_ignora() -> None:
    """El Excel trae 0 piezas y la base 1200: manda la base."""
    insumo = _insumo(existencia=1200)

    _aplicar_cambios(insumo, _fila(existencia=0, minimo=600), CAMPOS_ACTUALIZABLES)

    assert insumo.existencia == 1200
    assert insumo.minimo == 600


def test_una_columna_ausente_no_borra_lo_capturado() -> None:
    """Un Excel recortado a las obligatorias no debe vaciar el proveedor.

    El lector entrega todas las claves siempre —la columna que falta toma su
    valor por omisión—, así que sin el filtro de `columnas` la fila diría
    "proveedor: None" y la reimportación lo borraría del catálogo entero.
    """
    insumo = _insumo(proveedor="Suministros del Norte")
    campos = tuple(
        campo for campo in CAMPOS_ACTUALIZABLES if campo in {"categoria", "unidad_medida"}
    )

    _aplicar_cambios(insumo, _fila(proveedor=None, unidad_medida="MTS"), campos)

    assert insumo.proveedor == "Suministros del Norte"
    assert insumo.unidad_medida == "MTS"


def test_el_lector_reporta_las_columnas_que_traia_el_archivo() -> None:
    """`columnas` son las del encabezado, no las de la fila resultante."""
    completa = catalogo_excel.parsear_excel(catalogo_excel.generar_plantilla().read())
    assert {"proveedor", "ubicacion", "minimo", "maximo"} <= completa.columnas

    libro = Workbook()
    hoja = libro.active
    hoja.title = catalogo_excel.NOMBRE_HOJA
    hoja.append(["Código", "Descripción", "Categoría", "Unidad de medida"])
    hoja.append(["GN-100-M", "Guantes de nitrilo talla M", "EPP", "GR"])
    flujo = BytesIO()
    libro.save(flujo)

    recortada = catalogo_excel.parsear_excel(flujo.getvalue())

    assert recortada.columnas == {"codigo", "descripcion", "categoria", "unidad_medida"}
    # La fila sí trae la clave, con su valor por omisión: por eso hace falta
    # `columnas` para no confundirla con un dato capturado.
    assert recortada.filas[0]["proveedor"] is None
