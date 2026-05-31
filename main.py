import datetime
import logging
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

from database import engine
import models
from routers import auth_router, paciente_router, admin_router, profesional_router
from routers import bonos_router

models.Base.metadata.create_all(bind=engine)

# Rate limiter
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])

app = FastAPI(title="MediPortal", version="1.0.0")
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
