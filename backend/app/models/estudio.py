"""Estudios normativos y capacitaciones con vigencia.

La hoja DETALLE del archivo de estudios, que el departamento llevaba en Excel:
qué estudio es, qué despacho lo hace, cada cuánto se renueva, en qué estatus
va y cuándo vence. A diferencia de los controles ESH —que son un histórico de
inspecciones y no se tocan— cada renglón de aquí es un documento vivo que
cambia de estatus varias veces al año, así que se edita en su lugar.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Estudio(Base):
    """Un estudio o capacitación del programa anual."""

    __tablename__ = "estudios"
    __table_args__ = (
        # Las dos son verdades del dato, no del formulario, así que las
        # sostiene la base además del servicio: la fecha existe exactamente
        # cuando el vencimiento está "en curso", y el link solo acompaña a un
        # estudio ya terminado.
        CheckConstraint(
            "(vencimiento = 'en_curso') = (fecha_vencimiento IS NOT NULL)",
            name="ck_estudio_fecha_de_vencimiento",
        ),
        CheckConstraint(
            "link IS NULL OR estatus = 'ok'",
            name="ck_estudio_link_solo_con_ok",
        ),
        Index("ix_estudios_vencimiento", "fecha_vencimiento"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    despacho: Mapped[str] = mapped_column(String(150), nullable=False)
    estudio: Mapped[str] = mapped_column(Text, nullable=False)
    # Nombre en coreano, la columna 한국어 de la hoja. Opcional: si no se
    # captura, la celda sale vacía y el formato se conserva igual.
    estudio_ko: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Todas estas guardan la CLAVE del catálogo, no la etiqueta: el texto que
    # ve el usuario cambia con el idioma del panel, el dato no.
    vigencia: Mapped[str] = mapped_column(String(20), nullable=False)
    prioridad: Mapped[str] = mapped_column(String(10), nullable=False)
    tipo: Mapped[str] = mapped_column(String(10), nullable=False)
    estatus: Mapped[str] = mapped_column(String(10), nullable=False)
    vencimiento: Mapped[str] = mapped_column(String(10), nullable=False)
    fecha_vencimiento: Mapped[date | None] = mapped_column(Date, nullable=True)
    aprobado: Mapped[str] = mapped_column(String(10), nullable=False)
    pagado: Mapped[str] = mapped_column(String(10), nullable=False)

    # Acceso directo a la ubicación del estudio ya hecho.
    link: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Desnormalizado a propósito, igual que en los controles y en la bitácora:
    # borrar un usuario pone el FK en NULL y el histórico quedaría anónimo.
    responsable: Mapped[str] = mapped_column(String(150), nullable=False)
    admin_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="SET NULL"),
        nullable=True,
    )

    creado_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    actualizado_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<Estudio {self.estudio[:40]}>"
