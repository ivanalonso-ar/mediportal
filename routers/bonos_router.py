import datetime
from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db
from models import Bono, Paciente, Especialidad
from auth import get_current_user
from horarios import catalogo_horarios

router = APIRouter(prefix="/bonos")
templates = Jinja2Templates(directory="templates")


def require_recepcion(request: Request):
    user = get_current_user(request)
    if not user or user.get("tipo") != "staff":
        return None
    if user.get("rol") not in ("recepcion", "admin"):
        return None
    return user


def staff_nombre(user: dict) -> str:
    return f"{user.get('nombre', '')} {user.get('apellido', '')}".strip()


@router.get("/", response_class=HTMLResponse)
async def bonos_page(request: Request, db: Session = Depends(get_db)):
    user = require_recepcion(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    especialidad_sel = request.query_params.get("especialidad", "")
    hoy = datetime.date.today().strftime("%Y-%m-%d")

    # Buscar paciente
    q_pac = request.query_params.get("q", "").strip()
    pacientes = []
    if q_pac:
        pacientes = db.query(Paciente).filter(
            Paciente.activo == True,
            (Paciente.dni.contains(q_pac)) |
            (Paciente.nombre.contains(q_pac)) |
            (Paciente.apellido.contains(q_pac))
        ).limit(10).all()

    # Cola activa de la especialidad seleccionada (hoy)
    cola = []
    if especialidad_sel:
        cola = db.query(Bono).filter(
            Bono.especialidad == especialidad_sel,
            Bono.fecha == hoy,
            Bono.estado == "activo"
        ).order_by(Bono.hora.asc(), Bono.id.asc()).all()

    catalogo = catalogo_horarios(db)

    return templates.TemplateResponse("admin/bonos.html", {
        "request": request, "user": user,
        "especialidades": catalogo["especialidades"],
        "especialidad_sel": especialidad_sel,
        "cola": cola,
        "pacientes": pacientes,
        "q_pac": q_pac,
        "hoy": hoy,
        "msg": request.query_params.get("msg", ""),
        "msg_tipo": request.query_params.get("tipo", ""),
        "is_admin": user.get("rol") == "admin",
    })


@router.post("/emitir")
async def emitir_bono(
    request: Request,
    paciente_id: int = Form(...),
    especialidad: str = Form(...),
    hora: str = Form(...),
    observaciones: str = Form(""),
    db: Session = Depends(get_db)
):
    user = require_recepcion(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    hoy = datetime.date.today().strftime("%Y-%m-%d")
    bono = Bono(
        paciente_id=paciente_id,
        especialidad=especialidad,
        fecha=hoy,
        hora=hora,
        emitido_por=staff_nombre(user),
        observaciones=observaciones.strip(),
        estado="activo"
    )
    db.add(bono)
    db.commit()

    return RedirectResponse(
        url=f"/bonos/?especialidad={especialidad}&msg=Bono+emitido+correctamente.&tipo=success",
        status_code=302
    )


@router.post("/atender/{bono_id}")
async def marcar_atendido(request: Request, bono_id: int, db: Session = Depends(get_db)):
    user = require_recepcion(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    bono = db.query(Bono).filter(Bono.id == bono_id).first()
    especialidad = bono.especialidad if bono else ""
    if bono and bono.estado == "activo":
        bono.estado = "atendido"
        db.commit()

    return RedirectResponse(url=f"/bonos/?especialidad={especialidad}&msg=Bono+marcado+como+atendido.&tipo=success", status_code=302)


@router.post("/cancelar/{bono_id}")
async def cancelar_bono(request: Request, bono_id: int, db: Session = Depends(get_db)):
    user = require_recepcion(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    bono = db.query(Bono).filter(Bono.id == bono_id).first()
    especialidad = bono.especialidad if bono else ""
    if bono and bono.estado == "activo":
        bono.estado = "cancelado"
        db.commit()

    return RedirectResponse(url=f"/bonos/?especialidad={especialidad}&msg=Bono+cancelado.&tipo=success", status_code=302)
