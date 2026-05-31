import os
import datetime
import logging
from fastapi import APIRouter, Request, Form, Depends, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from database import get_db
from models import Paciente, Turno, Resultado, UsuarioStaff
from auth import get_current_user
from notif_utils import crear_notificacion
from storage import subir_archivo
from constants import ALLOWED_EXTENSIONS
from fecha_utils import fecha_es, fecha_corta_es

router = APIRouter(prefix="/profesional")
templates = Jinja2Templates(directory="templates")
templates.env.filters["fecha_es"] = fecha_es
templates.env.filters["fecha_corta_es"] = fecha_corta_es
logger = logging.getLogger("mediportal.profesional")

UPLOAD_DIR = "uploads/resultados"

ALLOWED_EXTENSIONS = {
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp",
    ".tiff", ".tif", ".doc", ".docx", ".xls", ".xlsx", ".txt",
    ".zip", ".rar", ".dcm", ".mp4", ".avi", ".mov",
}


def require_profesional(request: Request):
    user = get_current_user(request)
    if not user or user.get("tipo") != "staff" or user.get("rol") != "profesional":
        return None
    return user


def nombre_completo(user: dict) -> str:
    return f"{user.get('nombre', '')} {user.get('apellido', '')}".strip()


def nombre_publico(user: dict, db) -> str:
    from horarios import catalogo_horarios
    nombre = user.get("nombre", "")
    apellido = user.get("apellido", "")
    catalogo = catalogo_horarios(db)
    for profs in catalogo["profesionales"].values():
        for p in profs:
            # Match por nombre_staff/apellido_staff (defaults hardcodeados)
            if p.get("nombre_staff") == nombre and p.get("apellido_staff") == apellido:
                return p["nombre"]
            # Match por apellido dentro del nombre_publico (ej: "Dr. Torres, Sebastian")
            nombre_pub = p.get("nombre", "")
            if apellido and apellido.lower() in nombre_pub.lower() and nombre and nombre.lower() in nombre_pub.lower():
                return nombre_pub
    return f"{nombre} {apellido}".strip()


@router.get("/agenda", response_class=HTMLResponse)
async def agenda(request: Request, db: Session = Depends(get_db)):
    user = require_profesional(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    vista = request.query_params.get("vista", "dia")
    fecha_str = request.query_params.get("fecha", datetime.date.today().strftime("%Y-%m-%d"))
    fecha_obj = datetime.datetime.strptime(fecha_str, "%Y-%m-%d").date()
    fecha_anterior = (fecha_obj - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    fecha_siguiente = (fecha_obj + datetime.timedelta(days=1)).strftime("%Y-%m-%d")

    mi_nombre = nombre_publico(user, db)

    if vista == "mes":
        hoy = datetime.date.today()
        primer_dia_mes = fecha_obj.replace(day=1)
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

        from collections import defaultdict
        turnos_por_dia = defaultdict(list)
        for t in turnos_raw:
            turnos_por_dia[t.fecha].append(t)
        turnos_mes = dict(sorted(turnos_por_dia.items()))

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

    mi_nombre = nombre_publico(user, db)
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
    archivo: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    user = require_profesional(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    mi_nombre = nombre_publico(user, db)
    paciente = db.query(Paciente).join(Turno, Turno.paciente_id == Paciente.id).filter(
        Paciente.id == paciente_id,
        Paciente.activo == True,
        Turno.profesional == mi_nombre,
    ).first()
    if not paciente:
        return RedirectResponse(url="/profesional/informes?msg=Paciente+no+autorizado.&tipo_msg=error", status_code=302)

    file_path = None
    file_name = None

    if archivo and archivo.filename:
        ext = os.path.splitext(archivo.filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            return RedirectResponse(
                url="/profesional/informes?msg=Tipo+de+archivo+no+permitido.&tipo_msg=error",
                status_code=302
            )
        contenido = await archivo.read()
        try:
            file_path, file_name = subir_archivo(contenido, archivo.filename, ext)
        except Exception:
            logger.exception("Error al subir archivo de informe.")
            return RedirectResponse(url="/profesional/informes?msg=No+se+pudo+guardar+el+archivo.&tipo_msg=error", status_code=302)

    resultado = Resultado(
        paciente_id=paciente_id, titulo=titulo.strip(),
        descripcion=descripcion.strip(), archivo_nombre=file_name,
        archivo_path=file_path, fecha_estudio=fecha_estudio,
        subido_por=mi_nombre,
    )
    db.add(resultado)
    db.flush()

    crear_notificacion(
        db, paciente_id,
        titulo="Resultado disponible",
        mensaje=f"Los resultados de tu estudio {titulo.strip()} han sido cargados.",
        tipo="resultado"
    )
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Error de base de datos al subir informe.")
        return RedirectResponse(url="/profesional/informes?msg=No+se+pudo+cargar+el+informe.&tipo_msg=error", status_code=302)

    return RedirectResponse(url="/profesional/informes?msg=Informe+cargado+correctamente.&tipo_msg=success", status_code=302)