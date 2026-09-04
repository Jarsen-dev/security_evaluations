"""Control de Insumos: las salidas del almacén.

Registrar una entrega hace dos cosas a la vez: deja constancia de quién se
llevó qué y para qué área, y **baja la existencia del catálogo**. Es el primer
control que mueve datos de otro módulo; hasta ahora ese número solo lo subían
las recepciones y lo corregía a mano el catálogo.

Toda la aritmética del control cabe en `piezas_a_descontar()`, que es pura y
está probada. Lo demás es traer el insumo, restar con cuidado y guardar el
documento histórico.
"""

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import UNIDADES_PARCIALES
from app.core.errors import ConflictoDeNegocio, ErrorDeNegocio, RecursoNoEncontrado
from app.models.admin_user import AdminUser
from app.models.control import RegistroControlInsumos
from app.models.insumo import Insumo
from app.schemas.control import ControlInsumoCrear
from app.services import insumo_service
from app.services.rondin_service import ahora_local

NO_EXISTE = "El insumo ya no está en el catálogo. Vuelve a elegirlo."

FALTA_TERMINO = (
    "Este insumo se mide a granel: indica si el producto se terminó o no."
)

CAMBIO_DE_UNIDAD = (
    "El insumo cambió de unidad de medida mientras lo capturabas. Vuelve a "
    "elegirlo para que el descuento sea el correcto."
)


def es_parcial(unidad: str) -> bool:
    """¿Esta unidad obliga a preguntar si el producto se terminó?"""
    return unidad.strip().upper() in UNIDADES_PARCIALES


def piezas_a_descontar(unidad: str, consumo: int, termino: bool | None) -> int:
    """Cuánto baja del inventario. Es toda la regla del control.

    El inventario cuenta **piezas** —el frasco, el tubo, el rollo—, y `consumo`
    viene en esa misma unidad. Para lo que se mide a granel eso no basta: usar
    parte de un tubo no agota ningún envase, así que la captura pregunta si el
    producto se terminó y solo entonces se descuenta.

    El resultado es siempre `0` o `consumo`, nunca algo intermedio: un
    descuento a medias es la única forma de que el registro y el stock dejen de
    cuadrar. `ck_control_insumos_descontado` repite esa misma regla en la base,
    y `tests/test_control_insumos.py` contrasta las dos.

    Las combinaciones incoherentes se **rechazan**, no se corrigen en silencio:
    un `termino` que sobra significa que el panel creía otra unidad —alguien
    editó el insumo entre la búsqueda y el guardado—, y darlo por bueno
    descontaría lo que el operador creía que no se descontaba.
    """
    if es_parcial(unidad):
        if termino is None:
            raise ErrorDeNegocio(FALTA_TERMINO)
        return consumo if termino else 0

    if termino is not None:
        raise ErrorDeNegocio(CAMBIO_DE_UNIDAD)
    return consumo


async def _obtener_insumo(db: AsyncSession, insumo_id: uuid.UUID) -> Insumo:
    insumo = await db.scalar(select(Insumo).where(Insumo.id == insumo_id))
    if insumo is None:
        raise RecursoNoEncontrado(NO_EXISTE)
    return insumo


async def registrar(
    db: AsyncSession, datos: ControlInsumoCrear, *, admin: AdminUser
) -> RegistroControlInsumos:
    """Da salida a un insumo y deja el registro.

    El descuento y el registro van en **una sola transacción**, con un único
    `commit()` al final: si el INSERT falla, la existencia vuelve sola. Meter un
    `commit()` entre los dos pasos —para "refrescar" algo— rompería justo eso.
    """
    insumo = await _obtener_insumo(db, datos.insumo_id)

    # La unidad se lee de la fila, nunca del payload: es lo que decide cuánto
    # se descuenta, y entre que el desplegable la mostró y el operador guarda
    # cabe una edición del catálogo.
    descontado = piezas_a_descontar(insumo.unidad_medida, datos.consumo, datos.termino)

    if descontado > 0:
        # La comprobación y la escritura son la MISMA sentencia. Un SELECT para
        # validar y luego un UPDATE sería una carrera: con cuatro workers de
        # uvicorn, dos entregas simultáneas del último frasco pasarían las dos
        # la prueba. Y sin la guarda, pasarse de cero no da cero: choca contra
        # `ck_insumos_rango` y sale como 500 crudo en vez del 422 en español.
        resultado = await db.execute(
            update(Insumo)
            .where(Insumo.id == insumo.id, Insumo.existencia >= descontado)
            .values(
                existencia=Insumo.existencia - descontado,
                actualizado_at=datetime.now(UTC),
            )
        )

        if resultado.rowcount == 0:
            # Releer es solo para el mensaje: quien decidió fue la guarda.
            disponible = await db.scalar(
                select(Insumo.existencia).where(Insumo.id == insumo.id)
            )
            # El mensaje se arma ANTES del rollback. Deshacer expira el objeto
            # de SQLAlchemy, y leerle un atributo después dispara una recarga
            # perezosa que en una sesión asíncrona revienta como
            # `MissingGreenlet`: el operador vería un 500 en vez del aviso de
            # que no alcanza la existencia. Es la misma trampa que tumbó el
            # aprendizaje de formatos en Recepciones.
            aviso = (
                f"Solo hay {disponible} pieza(s) de "
                f"{insumo_service.etiquetar(insumo)}. Corrige la existencia en "
                f"Catálogo o ajusta el consumo."
            )
            await db.rollback()
            raise ErrorDeNegocio(aviso)

    registro = RegistroControlInsumos(
        # Día de planta. `date.today()` sería el del contenedor, que corre en
        # UTC: a las 19:00 de la nave ya sería mañana.
        fecha=ahora_local().date(),
        insumo_id=insumo.id,
        # Snapshot de la fila resuelta, nunca de lo que mandó el cliente.
        codigo=insumo.codigo,
        descripcion=insumo.descripcion,
        unidad_medida=insumo.unidad_medida,
        entregado_a=datos.entregado_a,
        area=datos.area,
        consumo=datos.consumo,
        descontado=descontado,
        termino=datos.termino,
        responsable=admin.username,
        admin_id=admin.id,
    )
    db.add(registro)

    try:
        await db.commit()
    except IntegrityError as exc:
        # Inalcanzable desde `ck_insumos_rango` gracias a la guarda; queda como
        # red para los CHECK de la fila nueva, que si no saldrían como 500.
        await db.rollback()
        raise ConflictoDeNegocio(
            "No se pudo guardar el registro. Vuelve a intentarlo."
        ) from exc

    await db.refresh(registro)
    return registro


async def listar(
    db: AsyncSession, desde: date, hasta: date
) -> list[RegistroControlInsumos]:
    """Los registros del periodo, del más reciente al más viejo."""
    filas = await db.scalars(
        select(RegistroControlInsumos)
        .where(RegistroControlInsumos.fecha.between(desde, hasta))
        .order_by(
            RegistroControlInsumos.fecha.desc(),
            RegistroControlInsumos.creado_at.desc(),
        )
    )
    return list(filas.all())
