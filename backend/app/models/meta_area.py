"""Metas de participación por área."""

from sqlalchemy import CheckConstraint, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MetaArea(Base):
    """Headcount esperado por área.

    Es el denominador del KPI "nivel de participación". Si un área no tiene
    meta capturada, el dashboard muestra el conteo absoluto y oculta el
    porcentaje en vez de inventar un denominador.

    La tabla se crea desde la migración inicial para no fragmentar el
    esquema; su pantalla de captura llega en la Fase 6.
    """

    __tablename__ = "metas_area"
    __table_args__ = (
        CheckConstraint("headcount >= 0", name="ck_metas_area_headcount_no_negativo"),
    )

    area: Mapped[str] = mapped_column(String(30), primary_key=True)
    headcount: Mapped[int] = mapped_column(Integer, nullable=False)

    def __repr__(self) -> str:
        return f"<MetaArea {self.area}={self.headcount}>"
