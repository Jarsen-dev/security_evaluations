"""Plantillas del clasificador de formatos de recepción.

Cada documento confirmado por el usuario es un ejemplo etiquetado gratis. Este
módulo decide cuáles vale la pena guardar y los mantiene acotados:

- **Curados** (``ejemplo``): los captura una persona al registrar un formato
  nuevo. Máximo 2, y **no se borran nunca solos**.
- **Auto**: los aprende el sistema al confirmar un guardado. Máximo 4, con
  rotación FIFO.

El aprendizaje automático es **best-effort**: si falla, la recepción se guarda
igual. Perder un ejemplo es molesto; perder la recepción por no poder aprender
de ella sería absurdo.
"""

import logging
import uuid
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictoDeNegocio, ErrorDeNegocio
from app.models.recepcion import (
    CLASE_AUTO,
    CLASE_CURADO,
    EjemploPlantillaRecepcion,
    PlantillaRecepcion,
)
from app.services import ocr_recepciones as ocr
from app.services.ocr_recepciones import EjemploPlantilla

logger = logging.getLogger(__name__)

SLUG_INVALIDO = (
    "El nombre del formato no puede quedar vacío. Usa letras o números."
)
FORMATO_DUPLICADO = "Ya existe un formato registrado con ese nombre."
DEMASIADOS_CURADOS = (
    "Este formato ya tiene el máximo de ejemplos de referencia. Borra uno "
    "antes de agregar otro."
)


async def corpus(db: AsyncSession) -> list[EjemploPlantilla]:
    """Todos los ejemplos, para clasificar y para el prompt.

    **Curados primero, auto después.** El orden importa: quien arma el prompt
    recorta la lista, y con los auto delante desplazarían a los curados justo
    donde más se quieren los curados.

    Se seleccionan columnas sueltas y no la entidad completa por dos razones:
    la entidad arrastraría la imagen en BYTEA de **cada** ejemplo en cada foto
    que se procesa, y navegar ``fila.plantilla.slug`` dispararía una carga
    perezosa que en una sesión asíncrona revienta con ``MissingGreenlet``.
    """
    filas = await db.execute(
        select(
            PlantillaRecepcion.slug,
            EjemploPlantillaRecepcion.texto_ocr,
            EjemploPlantillaRecepcion.json_esperado,
            EjemploPlantillaRecepcion.clase,
        )
        .join(
            PlantillaRecepcion,
            PlantillaRecepcion.id == EjemploPlantillaRecepcion.plantilla_id,
        )
        .order_by(
            # 'curado' < 'auto' alfabéticamente, así que el orden natural ya
            # los pone delante; se deja explícito para que no dependa de eso.
            (EjemploPlantillaRecepcion.clase == CLASE_AUTO),
            PlantillaRecepcion.slug,
            EjemploPlantillaRecepcion.indice,
        )
    )

    return [
        EjemploPlantilla(
            tipo=slug,
            texto_ocr=texto_ocr,
            json_esperado=json_esperado,
            curado=clase == CLASE_CURADO,
        )
        for slug, texto_ocr, json_esperado, clase in filas.all()
    ]


async def _primer_indice_libre(
    db: AsyncSession, plantilla_id: uuid.UUID, clase: str
) -> int:
    """Índice más chico que no esté ocupado.

    No sirve ``count + 1``: la rotación FIFO deja huecos y ese cálculo
    chocaría contra el índice único.
    """
    usados = set(
        (
            await db.scalars(
                select(EjemploPlantillaRecepcion.indice).where(
                    EjemploPlantillaRecepcion.plantilla_id == plantilla_id,
                    EjemploPlantillaRecepcion.clase == clase,
                )
            )
        ).all()
    )

    indice = 1
    while indice in usados:
        indice += 1
    return indice


async def registrar_formato(
    db: AsyncSession,
    *,
    nombre: str,
    imagen: bytes,
    tipo_mime: str,
    texto_ocr: str,
    json_esperado: dict[str, Any],
    creado_por: str,
) -> PlantillaRecepcion:
    """Da de alta un formato nuevo con su primer ejemplo curado.

    Si el formato ya existe se le agrega el ejemplo, hasta el tope de curados.
    """
    slug = ocr.slugify(nombre)
    if not slug:
        raise ErrorDeNegocio(SLUG_INVALIDO)

    plantilla = await db.scalar(
        select(PlantillaRecepcion).where(PlantillaRecepcion.slug == slug)
    )

    if plantilla is None:
        plantilla = PlantillaRecepcion(
            slug=slug, nombre=nombre.strip()[:150], creado_por=creado_por
        )
        db.add(plantilla)
        try:
            await db.flush()
        except IntegrityError as exc:
            # Otra sesión lo creó entre el SELECT y el INSERT.
            await db.rollback()
            raise ConflictoDeNegocio(FORMATO_DUPLICADO) from exc
    else:
        curados = await db.scalar(
            select(func.count(EjemploPlantillaRecepcion.id)).where(
                EjemploPlantillaRecepcion.plantilla_id == plantilla.id,
                EjemploPlantillaRecepcion.clase == CLASE_CURADO,
            )
        )
        if (curados or 0) >= ocr.MAX_EJEMPLOS_CURADOS:
            raise ConflictoDeNegocio(DEMASIADOS_CURADOS)

    db.add(
        EjemploPlantillaRecepcion(
            plantilla_id=plantilla.id,
            clase=CLASE_CURADO,
            indice=await _primer_indice_libre(db, plantilla.id, CLASE_CURADO),
            imagen=imagen,
            tipo=tipo_mime,
            texto_ocr=texto_ocr,
            json_esperado=json_esperado,
        )
    )
    await db.flush()
    return plantilla


async def aprender(
    db: AsyncSession,
    *,
    slug: str,
    imagen: bytes,
    tipo_mime: str,
    texto_ocr: str,
    json_esperado: dict[str, Any],
) -> None:
    """Suma un ejemplo automático si aporta señal.

    **Best-effort a propósito**: quien llama envuelve esto en un try/except y
    sigue adelante si falla. Un ejemplo perdido no justifica tirar la
    recepción que el usuario acaba de confirmar.
    """
    plantilla = await db.scalar(
        select(PlantillaRecepcion).where(PlantillaRecepcion.slug == slug)
    )
    if plantilla is None:
        return

    existentes = list(
        (
            await db.scalars(
                select(EjemploPlantillaRecepcion.texto_ocr).where(
                    EjemploPlantillaRecepcion.plantilla_id == plantilla.id
                )
            )
        ).all()
    )

    if not ocr.debe_aprender(texto_ocr, existentes):
        logger.info("Ejemplo descartado para %s: no aporta señal", slug)
        return

    # Solo los ids: traer las entidades completas arrastraría la imagen en
    # BYTEA de cada ejemplo para nada más que ordenarlos por antigüedad.
    autos = list(
        (
            await db.scalars(
                select(EjemploPlantillaRecepcion.id)
                .where(
                    EjemploPlantillaRecepcion.plantilla_id == plantilla.id,
                    EjemploPlantillaRecepcion.clase == CLASE_AUTO,
                )
                .order_by(EjemploPlantillaRecepcion.creado_at)
            )
        ).all()
    )

    # Rotación FIFO. Nunca toca los curados: son de otra clase y esta consulta
    # ni siquiera los ve.
    sobrantes = len(autos) - ocr.MAX_EJEMPLOS_AUTO + 1
    if sobrantes > 0:
        await db.execute(
            delete(EjemploPlantillaRecepcion).where(
                EjemploPlantillaRecepcion.id.in_(autos[:sobrantes])
            )
        )
        await db.flush()

    db.add(
        EjemploPlantillaRecepcion(
            plantilla_id=plantilla.id,
            clase=CLASE_AUTO,
            indice=await _primer_indice_libre(db, plantilla.id, CLASE_AUTO),
            imagen=imagen,
            tipo=tipo_mime,
            texto_ocr=texto_ocr,
            json_esperado=json_esperado,
        )
    )
    await db.flush()
    logger.info("Ejemplo automático aprendido para %s", slug)


async def listar_tipos(db: AsyncSession) -> list[dict[str, str]]:
    """Formatos registrados, para el filtro del historial."""
    filas = await db.scalars(
        select(PlantillaRecepcion).order_by(PlantillaRecepcion.nombre)
    )
    return [
        {"slug": fila.slug, "nombre": fila.nombre} for fila in filas.all()
    ]
