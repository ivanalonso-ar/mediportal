import asyncio
import datetime
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from logging_config import setup_logging
setup_logging()

from templates_config import templates
from fecha_utils import fecha_es, fecha_corta_es
templates.env.filters["fecha_es"] = fecha_es
templates.env.filters["fecha_corta_es"] = fecha_corta_es

from database import engine, SessionLocal
import models
from models import Turno
from routers import auth_router, paciente_router, admin_router, profesional_router
from routers import bonos_router

models.Base.metadata.create_all(bind=engine)

logger = logging.getLogger(__name__)

ESTADOS_ACTIVOS = ("pendiente", "confirmado")
INTERVALO_EXPIRACION_HORAS = 1  # cada cuánto corre el job


async def _expirar_turnos_vencidos():
    """Marca como 'ausente' los turnos cuya fecha+hora ya pasó y siguen activos."""
    while True:
        try:
            ahora = datetime.datetime.now()
            fecha_hoy = ahora.strftime("%Y-%m-%d")
            hora_ahora = ahora.strftime("%H:%M")
            db = SessionLocal()
            try:
                # Turnos de días anteriores con estado activo
                vencidos_dias_anteriores = (
                    db.query(Turno)
                    .filter(
                        Turno.estado.in_(ESTADOS_ACTIVOS),
                        Turno.fecha < fecha_hoy,
                    )
                    .all()
                )
                # Turnos de hoy cuya hora ya pasó
                vencidos_hoy = (
                    db.query(Turno)
                    .filter(
                        Turno.estado.in_(ESTADOS_ACTIVOS),
                        Turno.fecha == fecha_hoy,
                        Turno.hora < hora_ahora,
                    )
                    .all()
                )
                todos = vencidos_dias_anteriores + vencidos_hoy
                if todos:
                    ids = [t.id for t in todos]
                    for turno in todos:
                        turno.estado = "ausente"
                    db.commit()
                    logger.info(f"[expirar_turnos] {len(todos)} turno(s) marcado(s) como ausente: IDs {ids}")
            finally:
                db.close()
        except Exception:
            logger.exception("[expirar_turnos] Error al expirar turnos")

        await asyncio.sleep(INTERVALO_EXPIRACION_HORAS * 3600)


@asynccontextmanager
async def lifespan(app: FastAPI):
    tarea = asyncio.create_task(_expirar_turnos_vencidos())
    yield
    tarea.cancel()


# Rate limiter
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])

app = FastAPI(title="MediPortal", version="1.0.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.middleware("http")
async def add_global_context(request: Request, call_next):
    request.state.year = datetime.date.today().year
    return await call_next(request)

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse("static/favicon.svg", media_type="image/svg+xml")

@app.get("/ping", include_in_schema=False)
async def ping():
    return {"status": "ok"}

app.include_router(auth_router.router)
app.include_router(paciente_router.router)
app.include_router(admin_router.router)
app.include_router(profesional_router.router)
app.include_router(bonos_router.router)
