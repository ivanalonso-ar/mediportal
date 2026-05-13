import os
import uuid
import datetime
from fastapi import APIRouter, Request, Form, Depends, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db
from models import Paciente, Turno, Resultado, UsuarioStaff
from auth import get_current_user

router = APIRouter(prefix="/profesional")
templates = Jinja2Templates(directory="templates")

UPLOAD_DIR = "uploads/resultados"


def require_profesional(request: Request):
    user = get_current_user(request)
    if not user or user.get("tipo") != "staff" or user.get("rol") != "profesional":
        return None
    return user


def nombre_completo(user: dict) -> str:
    return f"{user.get('nombre', '')} {user.get('apellido', '')}".strip()


@router.get("/agenda", response_class=HTMLResponse)
async def agenda(request: Request, db: Session = Depends(get_db)):
    user = require_profesional(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    vista = request.query_params.get("vista", "dia")  # dia | mes
    fecha_str = request.query_params.get("fecha", datetime.date.today().strftime("%Y-%m-%d"))
    fecha_obj = datetime.datetime.strptime(fecha_str, "%Y-%m-%d").date()
    fecha_anterior = (fecha_obj - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    fecha_siguiente = (fecha_obj + datetime.timedelta(days=1)).strftime("%Y-%m-%d")

    mi_nombre = nombre_completo(user)

    if vista == "mes":
        # Todos los turnos futuros del mes (desde hoy hasta fin de mes)
        hoy = datetime.date.today()
        primer_dia_mes = fecha_obj.replace(day=1)
        # Último día del mes
        if fecha_obj.month == 12:
            ultimo_dia_mes = fecha_obj.replace(year=fecha_obj.year+1, month=1, day=1) - datetime.timedelta(days=1)
        else:
            ultimo_dia_mes = fecha_obj.replace(month=fecha_obj.month+1, day=1) - datetime.timedelta(days=1)

        desde = max(hoy, primer_dia_mes).strftime("%Y-%m-%d")
        hasta = ultimo_dia_mes.strftime("%Y-%m-%d")

        turnos_raw = db.query(Turno).filter(
            Turno.profesional == mi_nombre,
            Turno.fecha >= desde,
            Turno.fecha <= hasta,
            Turno.estado.notin_(["cancelado"])
        ).order_by(Turno.fecha.asc(), Turno.hora.asc()).all()

        # Agrupar por fecha
        from collections import defaultdict
        turnos_por_dia = defaultdict(list)
        for t in turnos_raw:
            turnos_por_dia[t.fecha].append(t)
        turnos_mes = dict(sorted(turnos_por_dia.items()))

        # Días sin turnos del mes (para ver disponibilidad)
        dias_mes = []
        d = max(hoy, primer_dia_mes)
        while d <= ultimo_dia_mes:
            dias_mes.append(d.strftime("%Y-%m-%d"))
            d += datetime.timedelta(days=1)

        dias_libres = [d for d in dias_mes if d not in turnos_mes]

        return templates.TemplateResponse("profesional/agenda.html", {
            "request": request, "user": user,
            "vista": "mes",
            "fecha": fecha_str,
            "fecha_obj": fecha_obj,
            "turnos_mes": turnos_mes,
            "dias_libres": dias_libres,
            "mes_anterior": (primer_dia_mes - datetime.timedelta(days=1)).replace(day=1).strftime("%Y-%m-%d"),
            "mes_siguiente": (ultimo_dia_mes + datetime.timedelta(days=1)).strftime("%Y-%m-%d"),
        })

    else:
        # Vista día (por defecto)
        turnos = db.query(Turno).filter(
            Turno.fecha == fecha_str,
            Turno.profesional == mi_nombre,
            Turno.estado.notin_(["cancelado"])
        ).order_by(Turno.hora.asc(), Turno.tipo.asc()).all()

        return templates.TemplateResponse("profesional/agenda.html", {
            "request": request, "user": user,
            "vista": "dia",
            "turnos": turnos,
            "fecha": fecha_str,
            "fecha_obj": fecha_obj,
            "fecha_anterior": fecha_anterior,
            "fecha_siguiente": fecha_siguiente,
            "msg": request.query_params.get("msg", ""),
            "msg_tipo": request.query_params.get("tipo_msg", ""),
        })


@router.get("/informes", response_class=HTMLResponse)
async def informes(request: Request, db: Session = Depends(get_db)):
    user = require_profesional(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    mi_nombre = nombre_completo(user)
    buscar = request.query_params.get("q", "").strip()

    pacientes_ids = db.query(Turno.paciente_id).filter(
        Turno.profesional == mi_nombre
    ).distinct().all()
    pacientes_ids = [p[0] for p in pacientes_ids]

    query = db.query(Paciente).filter(Paciente.id.in_(pacientes_ids), Paciente.activo == True)
    if buscar:
        query = query.filter(
            (Paciente.dni.contains(buscar)) |
            (Paciente.nombre.contains(buscar)) |
            (Paciente.apellido.contains(buscar))
        )
    pacientes = query.order_by(Paciente.apellido).all()

    resultados = db.query(Resultado).filter(
        Resultado.subido_por == mi_nombre
    ).order_by(Resultado.created_at.desc()).limit(20).all()

    return templates.TemplateResponse("profesional/informes.html", {
        "request": request, "user": user,
        "pacientes": pacientes, "resultados": resultados,
        "buscar": buscar,
        "msg": request.query_params.get("msg", ""),
        "msg_tipo": request.query_params.get("tipo_msg", ""),
    })


@router.post("/informes/subir")
async def subir_informe(
    request: Request,
    paciente_id: int = Form(...),
    titulo: str = Form(...),
    descripcion: str = Form(""),
    fecha_estudio: str = Form(""),
    tipo_carga: str = Form("pdf"),
    archivo: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    user = require_profesional(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    mi_nombre = nombre_completo(user)
    file_path = None
    file_name = None

    if tipo_carga == "pdf" and archivo and archivo.filename:
        if not archivo.filename.lower().endswith(".pdf"):
            return RedirectResponse(url="/profesional/informes?msg=Solo+se+permiten+archivos+PDF.&tipo_msg=error", status_code=302)
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        unique_name = f"{uuid.uuid4().hex}_{archivo.filename}"
        file_path = os.path.join(UPLOAD_DIR, unique_name)
        with open(file_path, "wb") as f:
            content = await archivo.read()
            f.write(content)
        file_name = archivo.filename

    resultado = Resultado(
        paciente_id=paciente_id, titulo=titulo.strip(),
        descripcion=descripcion.strip(), archivo_nombre=file_name,
        archivo_path=file_path, fecha_estudio=fecha_estudio,
        subido_por=mi_nombre,
    )
    db.add(resultado)
    db.commit()

    return RedirectResponse(url="/profesional/informes?msg=Informe+cargado+correctamente.&tipo_msg=success", status_code=302)
