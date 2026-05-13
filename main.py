import datetime
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from database import engine
import models
from fecha_utils import fecha_es, fecha_corta_es

from routers import auth_router, paciente_router, admin_router, profesional_router

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="MediPortal", version="1.0.0")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Registrar filtros Jinja2 globales
templates = Jinja2Templates(directory="templates")
templates.env.filters["fecha_es"] = fecha_es
templates.env.filters["fecha_corta_es"] = fecha_corta_es

@app.middleware("http")
async def add_global_context(request: Request, call_next):
    request.state.year = datetime.date.today().year
    return await call_next(request)

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse("static/favicon.svg", media_type="image/svg+xml")

app.include_router(auth_router.router)
app.include_router(paciente_router.router)
app.include_router(admin_router.router)
app.include_router(profesional_router.router)
