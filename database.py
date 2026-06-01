import logging
from config import settings
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import NullPool

logger = logging.getLogger("mediportal.database")

SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL

es_sqlite = SQLALCHEMY_DATABASE_URL.startswith("sqlite")
_es_sqlite = es_sqlite

if es_sqlite:
    logger.warning("ADVERTENCIA: Usando SQLite. Configura DATABASE_URL con Supabase para produccion.")
    connect_args = {"check_same_thread": False}
    engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
else:
    # NullPool para compatibilidad con pgbouncer (Supabase transaction pooler)
    engine = create_engine(SQLALCHEMY_DATABASE_URL, poolclass=NullPool, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
