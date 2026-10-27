import logging
import os
import re
from config import settings
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker, with_loader_criteria
from sqlalchemy import event
from sqlalchemy.pool import NullPool
from fastapi import Request

logger = logging.getLogger("mediportal.database")


def _paleta_acento(color_hex):
    """Convierte el color de marca en tonos Tailwind expresados como canales RGB."""
    valor = color_hex or "#2563eb"
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", valor):
        valor = "#2563eb"
    rgb = tuple(int(valor[i:i + 2], 16) for i in (1, 3, 5))

    def mezclar(destino, proporcion):
        return tuple(round(origen * (1 - proporcion) + fin * proporcion) for origen, fin in zip(rgb, destino))

    tonos = {
        50: mezclar((255, 255, 255), .95),
        100: mezclar((255, 255, 255), .88),
        200: mezclar((255, 255, 255), .72),
        300: mezclar((255, 255, 255), .52),
        400: mezclar((255, 255, 255), .28),
        500: mezclar((255, 255, 255), .12),
        600: rgb,
        700: mezclar((0, 0, 0), .18),
        800: mezclar((0, 0, 0), .34),
        900: mezclar((0, 0, 0), .50),
    }
    return ";".join(f"--accent-{nivel}:{r} {g} {b}" for nivel, (r, g, b) in tonos.items())

SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL

es_sqlite = SQLALCHEMY_DATABASE_URL.startswith("sqlite")
_es_sqlite = es_sqlite

# Transaction pooler (:6543) en Supabase exige NullPool (habitual en Render).
# Session pooler (:5432) puede usar pool SQLAlchemy; no forzar NullPool ahí.
_usar_null_pool = (
    os.getenv("DB_NULL_POOL", "").lower() in ("1", "true", "yes")
    or ":6543/" in SQLALCHEMY_DATABASE_URL
)

_pg_connect_args = {
    "connect_timeout": int(os.getenv("DB_CONNECT_TIMEOUT", "10")),
    "keepalives": 1,
    "keepalives_idle": 30,
    "keepalives_interval": 10,
    "keepalives_count": 5,
}

if es_sqlite:
    logger.warning("ADVERTENCIA: Usando SQLite. Configura DATABASE_URL con Supabase para produccion.")
    connect_args = {"check_same_thread": False}
    engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
elif _usar_null_pool:
    logger.info("DB: NullPool (Supabase transaction pooler — correcto para Render)")
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        poolclass=NullPool,
        pool_pre_ping=True,
        connect_args=_pg_connect_args,
    )
else:
    logger.info("DB: pool por defecto (solo desarrollo / session mode 5432)")
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        pool_pre_ping=True,
        pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
        max_overflow=int(os.getenv("DB_POOL_OVERFLOW", "5")),
        connect_args=_pg_connect_args,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def _criterio_clinica(clinica_id):
    return lambda modelo: modelo.clinica_id == clinica_id


def activar_clinica(db, clinica_id: int) -> None:
    """Asigna el tenant ORM y el contexto local de RLS a una sesión existente."""
    db.info["clinica_id"] = int(clinica_id)
    if db.bind.dialect.name == "postgresql":
        db.execute(
            text("select set_config('app.clinica_id', :clinica_id, true)"),
            {"clinica_id": str(clinica_id)},
        )


@event.listens_for(Session, "after_begin")
def _establecer_contexto_rls(session, _transaction, connection):
    clinica_id = session.info.get("clinica_id")
    if clinica_id and connection.dialect.name == "postgresql":
        connection.execute(
            text("select set_config('app.clinica_id', :clinica_id, true)"),
            {"clinica_id": str(clinica_id)},
        )


@event.listens_for(Session, "do_orm_execute")
def _filtrar_por_clinica(execute_state):
    """Aplica el aislamiento por clínica a todas las consultas ORM de la sesión."""
    clinica_id = execute_state.session.info.get("clinica_id")
    if not clinica_id or not (execute_state.is_select or execute_state.is_update or execute_state.is_delete):
        return

    for mapper in Base.registry.mappers:
        modelo = mapper.class_
        if hasattr(modelo, "clinica_id"):
            execute_state.statement = execute_state.statement.options(
                with_loader_criteria(
                    modelo,
                    _criterio_clinica(clinica_id),
                    include_aliases=True,
                )
            )


@event.listens_for(Session, "before_flush")
def _asignar_clinica_en_escrituras(session, _flush_context, _instances):
    """Asigna la clínica de la sesión y rechaza escrituras entre clientes."""
    clinica_id = session.info.get("clinica_id")
    if not clinica_id:
        return
    for objeto in session.new.union(session.dirty):
        if hasattr(objeto, "clinica_id"):
            asignada = objeto.clinica_id
            if asignada is None:
                objeto.clinica_id = clinica_id
            elif asignada != clinica_id:
                raise ValueError("La operación intenta modificar datos de otra clínica.")


def get_db(request: Request):
    db = SessionLocal()
    try:
        # El tenant autenticado prevalece; para login/registro se selecciona por slug.
        from jose import JWTError, jwt
        from fastapi import HTTPException
        from models import ConfiguracionClinica
        from config import settings

        token = request.cookies.get("access_token")
        clinica_id = None
        if token:
            try:
                payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
                clinica_id = payload.get("clinica_id")
            except JWTError:
                pass

        seleccionar_slug = request.url.path in ("/login", "/registro")
        if clinica_id is not None and not seleccionar_slug:
            clinica = db.query(ConfiguracionClinica).filter(
                ConfiguracionClinica.id == int(clinica_id),
                ConfiguracionClinica.activo == True,
            ).first()
        else:
            slug = request.query_params.get("clinica", "mediportal")
            clinica = db.query(ConfiguracionClinica).filter(
                ConfiguracionClinica.slug == slug,
                ConfiguracionClinica.activo == True,
            ).first()

        if not clinica:
            raise HTTPException(status_code=404, detail="Clínica no encontrada o inactiva.")

        activar_clinica(db, clinica.id)
        request.state.clinica = clinica
        request.state.paleta_acento = _paleta_acento(clinica.color_primario)
        yield db
    finally:
        db.close()
