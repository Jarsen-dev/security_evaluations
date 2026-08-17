"""Engine async y fábrica de sesiones de SQLAlchemy."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

# pool_size 10 por worker x 4 workers = 40 conexiones máximas contra Postgres,
# cómodo dentro del límite default de 100 y suficiente para el pico de ~150
# operadores contestando en la misma ventana.
engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_size=10,
    max_overflow=5,
    pool_pre_ping=True,  # descarta conexiones muertas tras un corte de red
    pool_recycle=1800,
)

SessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # permite leer los objetos después del commit
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependencia de FastAPI: una sesión por request, siempre cerrada.

    El rollback ante excepción evita que una transacción a medias contamine
    la siguiente request que reutilice la conexión del pool.
    """
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
