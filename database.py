import logging
import os
from config import settings
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import NullPool

logger = logging.getLogger("mediportal.database")

SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL

es_sqlite = SQLALCHEMY_DATABASE_URL.startswith("sqlite")
_es_sqlite = es_sqlite

# Transaction pooler (puerto 6543): una conexión por request. Session pooler (5432): pool reutilizable.
_usar_null_pool = (
    os.getenv("DB_NULL_POOL", "").lower() in ("1", "true", "yes")
    or ":6543/" in SQLALCHEMY_DATABASE_URL
)

if es_sqlite:
    logger.warning("ADVERTENCIA: Usando SQLite. Configura DATABASE_URL con Supabase para produccion.")
    connect_args = {"check_same_thread": False}
    engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
elif _usar_null_pool:
    logger.info("DB: NullPool (transaction pooler / DB_NULL_POOL)")
    engine = create_engine(SQLALCHEMY_DATABASE_URL, poolclass=NullPool, pool_pre_ping=True)
else:
    logger.info("DB: QueuePool (recomendado con session pooler puerto 5432)")
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        pool_pre_ping=True,
        pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
        max_overflow=int(os.getenv("DB_POOL_OVERFLOW", "5")),
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
