from templates_config import templates
import os
import datetime
import logging
from fastapi import APIRouter, Request, Form, Depends, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, Response
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import SQLAlchemyError

from database import get_db
from models import Paciente, UsuarioStaff, Turno, TurnoLog, Resultado, Aviso
from obras_sociales import listar_obras_sociales
from notif_utils import crear_notificacion
from horarios import catalogo_horarios, resolver_profesional_id
from disponibilidad import hora_disponible
from auth import get_current_user, get_password_hash
from mail import mail_bienvenida, mail_turno_confirmado, mail_turno_cancelado, mail_resultado_disponible, mail_registro_aprobado, mail_registro_rechazado
from storage import subir_archivo, leer_archivo, eliminar_archivo
from constants import ALLOWED_EXTENSIONS

router = APIRouter(prefix="/admin")
logger = logging.getLogger("mediportal.admin")

ESTADOS_TURNO = ["pendiente", "confirmado", "cancelado", "completado", "ausente"]


def require_staff(request: Request):
    user = get_current_user(request)
    if not user or user.get("tipo") != "staff":
        return None
    return user


def require_admin(request: Request):
    user = get_current_user(request)
    if not user or user.get("tipo") != "staff" or user.get("rol") != "admin":
        return None
    return user


def is_admin(user: dict) -> bool:
    return user and user.get("rol") == "admin"


def staff_nombre(user: dict) -> str:
    return f"{user.get('nombre', '')} {user.get('apellido', '')}".strip()


def nombre_publico_staff(user: dict, db) -> str:
    from horarios import catalogo_horarios
    nombre = user.get("nombre", "")
    apellido = user.get("apellido", "")
    catalogo = catalogo_horarios(db)
    for profs in catalogo["profesionales"].values():
        for p in profs:
            if p.get("nombre_staff") == nombre and p.get("apellido_staff") == apellido:
                return p["nombre"]
    return f"{nombre} {apellido}".strip()


def log_turno(db: Session, turno_id: int, accion: str, descripcion: str, realizado_por: str):
    entry = TurnoLog(
        turno_id=turno_id,
        accion=accion,
        descripcion=descripcion,
        realizado_por=realizado_por,
    )
    db.add(entry)


# ─── Dashboard ────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    user = require_staff(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    hoy = datetime.date.today().strftime("%Y-%m-%d")
    mes_actual = datetime.date.today().strftime("%Y-%m")

    total_pacientes = db.query(Paciente).filter(Paciente.activo == True).count()
    turnos_hoy = db.query(Turno).filter(Turno.fecha == hoy).count()
    turnos_pendientes = db.query(Turno).filter(Turno.estado == "pendiente").count()
    resultados_mes = db.query(Resultado).filter(
        Resultado.created_at >= datetime.datetime.strptime(mes_actual + "-01", "%Y-%m-%d")
    ).count()

    ultimos_turnos = (
        db.query(Turno)
        .options(joinedload(Turno.paciente))
        .order_by(Turno.created_at.desc())
        .limit(5)
        .all()
    )

    return templates.TemplateResponse("admin/dashboard.html", {
        "request": request, "user": user,
        "stats": {
            "total_pacientes": total_pacientes,
            "turnos_hoy": turnos_hoy,
            "turnos_pendientes": turnos_pendientes,
            "resultados_mes": resultados_mes,
        },
        "ultimos_turnos": ultimos_turnos,
        "is_admin": is_admin(user),
    })


# ─── Pacientes ────────────────────────────────────────────────────────────────

@router.get("/pacientes", response_class=HTMLResponse)
async def pacientes_page(request: Request, db: Session = Depends(get_db)):
    user = require_staff(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    buscar = request.query_params.get("q", "").strip()
    filtro = request.query_params.get("filtro", "")
    query = db.query(Paciente)
    if buscar:
        query = query.filter(
            (Paciente.dni.contains(buscar)) |
            (Paciente.nombre.contains(buscar)) |
            (Paciente.apellido.contains(buscar))
        )
    if filtro == "pendientes":
        query = query.filter(Paciente.aprobado == False)
    pacientes = query.order_by(Paciente.apellido).all()
    pendientes_count = db.query(Paciente).filter(Paciente.aprobado == False).count()

    return templates.TemplateResponse("admin/pacientes.html", {
        "request": request, "user": user,
        "pacientes": pacientes, "buscar": buscar,
        "filtro": filtro,
        "pendientes_count": pendientes_count,
        "msg": request.query_params.get("msg", ""),
        "msg_tipo": request.query_params.get("tipo", ""),
        "is_admin": is_admin(user),
    })


@router.post("/pacientes/nuevo")
async def nuevo_paciente(
    request: Request,
    dni: str = Form(...),
    nombre: str = Form(...),
    apellido: str = Form(...),
    email: str = Form(""),
    telefono: str = Form(""),
    fecha_nacimiento: str = Form(""),
    obra_social: str = Form(""),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = require_staff(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    import re
    RE_LETRAS = re.compile(r"^[a-záéíóúüñA-ZÁÉÍÓÚÜÑ\s\-']+$")
    RE_NUMS = re.compile(r"^\d+$")

    if not RE_LETRAS.match(nombre.strip()):
        return RedirectResponse(url="/admin/pacientes?msg=El+nombre+no+puede+contener+números.&tipo=error", status_code=302)
    if not RE_LETRAS.match(apellido.strip()):
        return RedirectResponse(url="/admin/pacientes?msg=El+apellido+no+puede+contener+números.&tipo=error", status_code=302)
    if not RE_NUMS.match(dni.strip()):
        return RedirectResponse(url="/admin/pacientes?msg=El+DNI+solo+puede+contener+números.&tipo=error", status_code=302)
    if telefono.strip() and not RE_NUMS.match(telefono.strip()):
        return RedirectResponse(url="/admin/pacientes?msg=El+telefono+solo+puede+contener+numeros.&tipo=error", status_code=302)

    existente = db.query(Paciente).filter(Paciente.dni == dni.strip()).first()
    if existente:
        return RedirectResponse(url="/admin/pacientes?msg=Ya+existe+un+paciente+con+ese+DNI.&tipo=error", status_code=302)

    paciente = Paciente(
        dni=dni.strip(), nombre=nombre.strip(), apellido=apellido.strip(),
        email=email.strip(), telefono=telefono.strip(),
        fecha_nacimiento=fecha_nacimiento, obra_social=obra_social.strip(),
        password_hash=get_password_hash(password),
        primer_login=True, activo=True,
    )
    db.add(paciente)
    db.commit()

    if email.strip():
        mail_bienvenida(email.strip(), nombre.strip(), dni.strip(), password)

    return RedirectResponse(url="/admin/pacientes?msg=Paciente+creado+correctamente.&tipo=success", status_code=302)




@router.post("/pacientes/aprobar/{paciente_id}")
async def aprobar_paciente(request: Request, paciente_id: int, db: Session = Depends(get_db)):
    user = require_staff(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    paciente = db.query(Paciente).filter(Paciente.id == paciente_id).first()
    if paciente:
        paciente.aprobado = True
        db.commit()
        if paciente.email:
            mail_registro_aprobado(paciente.email, paciente.nombre)
        return RedirectResponse(url="/admin/pacientes?filtro=pendientes&msg=Paciente+aprobado.&tipo=success", status_code=302)
    return RedirectResponse(url="/admin/pacientes?msg=Paciente+no+encontrado.&tipo=error", status_code=302)


@router.post("/pacientes/rechazar/{paciente_id}")
async def rechazar_paciente(
    request: Request, paciente_id: int,
    motivo: str = Form(""),
    db: Session = Depends(get_db)
):
    user = require_staff(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    paciente = db.query(Paciente).filter(Paciente.id == paciente_id).first()
    if paciente:
        if paciente.email:
            mail_registro_rechazado(paciente.email, paciente.nombre, motivo)
        db.delete(paciente)
        db.commit()
        return RedirectResponse(url="/admin/pacientes?filtro=pendientes&msg=Registro+rechazado+y+eliminado.&tipo=success", status_code=302)
    return RedirectResponse(url="/admin/pacientes?msg=Paciente+no+encontrado.&tipo=error", status_code=302)

@router.post("/pacientes/toggle/{paciente_id}")
async def toggle_paciente(request: Request, paciente_id: int, db: Session = Depends(get_db)):
    user = require_staff(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    paciente = db.query(Paciente).filter(Paciente.id == paciente_id).first()
    if paciente:
        paciente.activo = not paciente.activo
        db.commit()
        estado = "activado" if paciente.activo else "desactivado"
        return RedirectResponse(url=f"/admin/pacientes?msg=Paciente+{estado}.&tipo=success", status_code=302)

    return RedirectResponse(url="/admin/pacientes?msg=Paciente+no+encontrado.&tipo=error", status_code=302)


# ─── Staff (solo admin) ───────────────────────────────────────────────────────

@router.get("/staff", response_class=HTMLResponse)
async def staff_page(request: Request, db: Session = Depends(get_db)):
    user = require_admin(request)
    if not user:
        return RedirectResponse(url="/admin/?msg=Acceso+restringido+a+administradores.&tipo=error", status_code=302)

    staff = db.query(UsuarioStaff).order_by(UsuarioStaff.apellido).all()
    return templates.TemplateResponse("admin/staff.html", {
        "request": request, "user": user, "staff": staff,
        "msg": request.query_params.get("msg", ""),
        "msg_tipo": request.query_params.get("tipo", ""),
        "is_admin": True,
    })


@router.post("/staff/nuevo")
async def nuevo_staff(
    request: Request,
    nombre: str = Form(...),
    apellido: str = Form(...),
    email: str = Form(...),
    rol: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = require_admin(request)
    if not user:
        return RedirectResponse(url="/admin/", status_code=302)

    existente = db.query(UsuarioStaff).filter(UsuarioStaff.email == email.strip().lower()).first()
    if existente:
        return RedirectResponse(url="/admin/staff?msg=Ya+existe+un+usuario+con+ese+email.&tipo=error", status_code=302)

    if rol not in ("admin", "recepcion", "profesional"):
        rol = "recepcion"

    miembro = UsuarioStaff(
        nombre=nombre.strip(), apellido=apellido.strip(),
        email=email.strip().lower(), rol=rol,
        password_hash=get_password_hash(password), activo=True,
    )
    db.add(miembro)
    db.commit()
    return RedirectResponse(url="/admin/staff?msg=Usuario+creado+correctamente.&tipo=success", status_code=302)


@router.post("/staff/toggle/{staff_id}")
async def toggle_staff(request: Request, staff_id: int, db: Session = Depends(get_db)):
    user = require_admin(request)
    if not user:
        return RedirectResponse(url="/admin/", status_code=302)

    miembro = db.query(UsuarioStaff).filter(UsuarioStaff.id == staff_id).first()
    if miembro:
        if miembro.id == int(user["sub"]):
            return RedirectResponse(url="/admin/staff?msg=No+podés+desactivarte+a+vos+mismo.&tipo=error", status_code=302)
        miembro.activo = not miembro.activo
        db.commit()
        estado = "activado" if miembro.activo else "desactivado"
        return RedirectResponse(url=f"/admin/staff?msg=Usuario+{estado}.&tipo=success", status_code=302)

    return RedirectResponse(url="/admin/staff?msg=Usuario+no+encontrado.&tipo=error", status_code=302)


# ─── Turnos ───────────────────────────────────────────────────────────────────

@router.get("/turnos", response_class=HTMLResponse)
async def turnos_page(request: Request, db: Session = Depends(get_db)):
    user = require_staff(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    filtro_estado = request.query_params.get("estado", "")
    filtro_fecha = request.query_params.get("fecha", "")
    filtro_tipo = request.query_params.get("tipo_turno", "")

    query = db.query(Turno)
    if filtro_estado:
        query = query.filter(Turno.estado == filtro_estado)
    if filtro_fecha:
        query = query.filter(Turno.fecha == filtro_fecha)
    if filtro_tipo:
        query = query.filter(Turno.tipo == filtro_tipo)

    turnos = query.options(joinedload(Turno.paciente)).order_by(
        Turno.fecha.desc(), Turno.hora.asc()
    ).all()
    pacientes = db.query(Paciente).filter(Paciente.activo == True).order_by(Paciente.apellido).all()

    # Profesionales disponibles para asignar
    profesionales = db.query(UsuarioStaff).filter(
        UsuarioStaff.rol == "profesional", UsuarioStaff.activo == True
    ).order_by(UsuarioStaff.apellido).all()
    catalogo = catalogo_horarios(db)

    return templates.TemplateResponse("admin/turnos.html", {
        "request": request, "user": user,
        "turnos": turnos, "pacientes": pacientes,
        "profesionales": profesionales,
        "especialidades": catalogo["especialidades"],
        "obras_sociales": listar_obras_sociales(db),
        "turno_por_especialidad": catalogo["turno_por_especialidad"],
        "slots_manana": catalogo["slots_manana"],
        "slots_tarde": catalogo["slots_tarde"],
        "profesionales_json": catalogo["profesionales_json"],
        "today": __import__("datetime").date.today().strftime("%Y-%m-%d"),
        "estados": ESTADOS_TURNO,
        "filtro_estado": filtro_estado,
        "filtro_fecha": filtro_fecha,
        "filtro_tipo": filtro_tipo,
        "msg": request.query_params.get("msg", ""),
        "msg_tipo": request.query_params.get("tipo", ""),
        "is_admin": is_admin(user),
    })


@router.get("/agenda", response_class=HTMLResponse)
async def agenda_page(request: Request, db: Session = Depends(get_db)):
    user = require_staff(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    fecha_str = request.query_params.get("fecha", datetime.date.today().strftime("%Y-%m-%d"))
    filtro_prof = request.query_params.get("profesional", "")
    if user.get("rol") == "profesional" and not filtro_prof:
        filtro_prof = nombre_publico_staff(user, db)

    query = db.query(Turno).filter(
        Turno.fecha == fecha_str,
        Turno.estado.notin_(["cancelado"])
    )
    if filtro_prof:
        query = query.filter(Turno.profesional == filtro_prof)

    turnos = query.options(joinedload(Turno.paciente)).order_by(
        Turno.hora.asc(), Turno.tipo.asc()
    ).all()

    profesionales = db.query(UsuarioStaff).filter(
        UsuarioStaff.rol == "profesional", UsuarioStaff.activo == True
    ).order_by(UsuarioStaff.apellido).all()

    catalogo = catalogo_horarios(db)

    # Calcular fecha anterior y siguiente para navegación
    fecha_obj = datetime.datetime.strptime(fecha_str, "%Y-%m-%d").date()
    fecha_anterior = (fecha_obj - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    fecha_siguiente = (fecha_obj + datetime.timedelta(days=1)).strftime("%Y-%m-%d")

    return templates.TemplateResponse("admin/agenda.html", {
        "request": request, "user": user,
        "turno_por_especialidad": catalogo["turno_por_especialidad"],
        "turnos": turnos,
        "fecha": fecha_str,
        "fecha_obj": fecha_obj,
        "fecha_anterior": fecha_anterior,
        "fecha_siguiente": fecha_siguiente,
        "profesionales": profesionales,
        "filtro_prof": filtro_prof,
        "is_admin": is_admin(user),
    })


@router.post("/turnos/nuevo")
async def nuevo_turno(
    request: Request,
    paciente_id: int = Form(...),
    fecha: str = Form(...),
    hora: str = Form(...),
    especialidad: str = Form(...),
    profesional: str = Form(""),
    tipo: str = Form("normal"),
    tipo_consulta: str = Form("obra_social"),
    observaciones: str = Form(""),
    db: Session = Depends(get_db)
):
    user = require_staff(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    if tipo not in ("normal", "sobreturno"):
        tipo = "normal"
    if tipo_consulta not in ("obra_social", "particular"):
        tipo_consulta = "obra_social"

    paciente = db.query(Paciente).filter(Paciente.id == paciente_id, Paciente.activo == True).first()
    if not paciente:
        return RedirectResponse(url="/admin/turnos?msg=Paciente+no+encontrado+o+inactivo.&tipo=error", status_code=302)

    if not hora_disponible(db, fecha, hora, especialidad, profesional.strip()):
        return RedirectResponse(
            url="/admin/turnos?msg=Ese+horario+ya+no+esta+disponible.+Elegi+otro.&tipo=error",
            status_code=302
        )

    nombre_staff = staff_nombre(user)
    prof_nombre = profesional.strip()
    turno = Turno(
        paciente_id=paciente_id, fecha=fecha, hora=hora,
        especialidad=especialidad, profesional=prof_nombre,
        profesional_id=resolver_profesional_id(db, especialidad, prof_nombre),
        observaciones=observaciones.strip(),
        estado="confirmado", tipo=tipo, tipo_consulta=tipo_consulta,
        created_by=nombre_staff,
    )
    db.add(turno)
    db.flush()

    log_turno(db, turno.id, "creado",
        f"{nombre_staff} creó {'sobreturno' if tipo == 'sobreturno' else 'turno'} — {fecha} {hora}hs — {especialidad}",
        nombre_staff)
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Error de base de datos al crear turno.")
        return RedirectResponse(url="/admin/turnos?msg=No+se+pudo+crear+el+turno.&tipo=error", status_code=302)

    if paciente and paciente.email:
        mail_turno_confirmado(paciente.email, paciente.nombre, especialidad, fecha, hora, profesional.strip())

    return RedirectResponse(url="/admin/turnos?msg=Turno+creado+correctamente.&tipo=success", status_code=302)


@router.post("/turnos/modificar/{turno_id}")
async def modificar_turno(
    request: Request,
    turno_id: int,
    fecha: str = Form(...),
    hora: str = Form(...),
    especialidad: str = Form(...),
    profesional: str = Form(""),
    tipo: str = Form("normal"),
    tipo_consulta: str = Form("obra_social"),
    observaciones: str = Form(""),
    db: Session = Depends(get_db)
):
    user = require_staff(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    turno = db.query(Turno).filter(Turno.id == turno_id).first()
    if not turno:
        return RedirectResponse(url="/admin/turnos?msg=Turno+no+encontrado.&tipo=error", status_code=302)
    if not hora_disponible(db, fecha, hora, especialidad, profesional.strip(), exclude_turno_id=turno.id):
        return RedirectResponse(
            url="/admin/turnos?msg=No+se+pudo+guardar:+horario+ocupado.&tipo=error",
            status_code=302
        )

    nombre_staff = staff_nombre(user)
    cambios = []
    if turno.fecha != fecha:
        cambios.append(f"fecha {turno.fecha}→{fecha}")
    if turno.hora != hora:
        cambios.append(f"hora {turno.hora}→{hora}")
    if turno.especialidad != especialidad:
        cambios.append(f"especialidad {turno.especialidad}→{especialidad}")
    if turno.profesional != profesional.strip():
        cambios.append(f"profesional {turno.profesional or '—'}→{profesional.strip() or '—'}")
    if turno.tipo != tipo:
        cambios.append(f"tipo {turno.tipo}→{tipo}")

    prof_nombre = profesional.strip()
    turno.fecha = fecha
    turno.hora = hora
    turno.especialidad = especialidad
    turno.profesional = prof_nombre
    turno.profesional_id = resolver_profesional_id(db, especialidad, prof_nombre)
    turno.tipo = tipo if tipo in ("normal", "sobreturno") else "normal"
    turno.tipo_consulta = tipo_consulta if tipo_consulta in ("obra_social", "particular") else "obra_social"
    turno.observaciones = observaciones.strip()

    if cambios:
        log_turno(db, turno.id, "modificado",
            f"{nombre_staff} modificó: {', '.join(cambios)}",
            nombre_staff)

    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Error de base de datos al modificar turno.")
        return RedirectResponse(url="/admin/turnos?msg=No+se+pudo+modificar+el+turno.&tipo=error", status_code=302)
    return RedirectResponse(url="/admin/turnos?msg=Turno+modificado+correctamente.&tipo=success", status_code=302)


@router.get("/turnos/disponibilidad")
async def disponibilidad_turnos(
    request: Request,
    fecha: str,
    especialidad: str,
    profesional: str = "",
    db: Session = Depends(get_db)
):
    user = require_staff(request)
    if not user:
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)

    ocupados = []
    if profesional.strip():
        turnos = db.query(Turno).filter(
            Turno.fecha == fecha,
            Turno.especialidad == especialidad,
            Turno.profesional == profesional.strip(),
            Turno.estado.in_(["pendiente", "confirmado"]),
        ).all()
        ocupados = sorted({t.hora for t in turnos})
    return {"ok": True, "ocupados": ocupados}


@router.post("/turnos/estado/{turno_id}")
async def actualizar_estado_turno(
    request: Request,
    turno_id: int,
    estado: str = Form(...),
    db: Session = Depends(get_db)
):
    user = require_staff(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    turno = db.query(Turno).filter(Turno.id == turno_id).first()
    if turno and estado in ESTADOS_TURNO:
        nombre_staff = staff_nombre(user)
        estado_anterior = turno.estado
        turno.estado = estado

        log_turno(db, turno.id, "estado_cambiado",
            f"{nombre_staff} cambió estado: {estado_anterior}→{estado}",
            nombre_staff)
        db.commit()

        paciente = turno.paciente
        if estado == "cancelado" and paciente:
            import datetime as _dt
            try:
                fecha_fmt = _dt.datetime.strptime(turno.fecha, "%Y-%m-%d").strftime("%d/%m/%Y")
            except ValueError:
                fecha_fmt = turno.fecha
            profesional_notif = turno.profesional or "el profesional asignado"
            crear_notificacion(
                db, paciente.id,
                titulo="Turno cancelado",
                mensaje=f"Tu turno para el día {fecha_fmt} a las {turno.hora} hs con {profesional_notif} ha sido cancelado.",
                tipo="turno_cancelado",
            )
            db.commit()
        if paciente and paciente.email:
            if estado == "confirmado":
                mail_turno_confirmado(paciente.email, paciente.nombre, turno.especialidad,
                    turno.fecha, turno.hora, turno.profesional or "")
            elif estado == "cancelado":
                mail_turno_cancelado(paciente.email, paciente.nombre,
                    turno.especialidad, turno.fecha, turno.hora)

    return RedirectResponse(url="/admin/turnos?msg=Estado+actualizado.&tipo=success", status_code=302)


@router.get("/turnos/log/{turno_id}", response_class=HTMLResponse)
async def turno_log(request: Request, turno_id: int, db: Session = Depends(get_db)):
    user = require_staff(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    turno = db.query(Turno).filter(Turno.id == turno_id).first()
    if not turno:
        return RedirectResponse(url="/admin/turnos?msg=Turno+no+encontrado.&tipo=error", status_code=302)

    logs = db.query(TurnoLog).filter(
        TurnoLog.turno_id == turno_id
    ).order_by(TurnoLog.created_at.desc()).all()

    return templates.TemplateResponse("admin/turno_log.html", {
        "request": request, "user": user,
        "turno": turno, "logs": logs,
        "is_admin": is_admin(user),
    })


# ─── Resultados ───────────────────────────────────────────────────────────────

ALLOWED_EXTENSIONS = {
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp",
    ".tiff", ".tif", ".doc", ".docx", ".xls", ".xlsx", ".txt",
    ".zip", ".rar", ".dcm",
}


@router.get("/resultados", response_class=HTMLResponse)
async def resultados_page(request: Request, db: Session = Depends(get_db)):
    user = require_staff(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    mi_nombre = nombre_publico_staff(user, db)
    nombre_raw = staff_nombre(user)
    rol = user.get("rol", "")

    # Profesionales ven solo sus pacientes; admin/recepcion ven todos
    if rol == "profesional":
        paciente_ids = [t[0] for t in db.query(Turno.paciente_id).filter(
            (Turno.profesional == mi_nombre) | (Turno.profesional == nombre_raw)
        ).distinct().all()]
        pacientes = db.query(Paciente).filter(
            Paciente.id.in_(paciente_ids), Paciente.activo == True
        ).order_by(Paciente.apellido).all()
        resultados = db.query(Resultado).filter(
            Resultado.paciente_id.in_(paciente_ids)
        ).order_by(Resultado.created_at.desc()).all()
    else:
        pacientes = db.query(Paciente).filter(Paciente.activo == True).order_by(Paciente.apellido).all()
        resultados = db.query(Resultado).order_by(Resultado.created_at.desc()).all()

    # Turnos por paciente para selector de turno en el modal
    paciente_ids_visibles = [p.id for p in pacientes]
    turnos_por_paciente = {pid: [] for pid in paciente_ids_visibles}
    if paciente_ids_visibles:
        turnos = db.query(Turno).filter(
            Turno.paciente_id.in_(paciente_ids_visibles),
            Turno.estado.notin_(["cancelado"])
        ).order_by(Turno.paciente_id.asc(), Turno.fecha.desc()).all()
        for turno in turnos:
            if len(turnos_por_paciente[turno.paciente_id]) < 20:
                turnos_por_paciente[turno.paciente_id].append(turno)

    return templates.TemplateResponse("admin/resultados.html", {
        "request": request, "user": user,
        "resultados": resultados, "pacientes": pacientes,
        "turnos_por_paciente": turnos_por_paciente,
        "msg": request.query_params.get("msg", ""),
        "msg_tipo": request.query_params.get("tipo", ""),
        "is_admin": is_admin(user),
    })


@router.post("/resultados/subir")
async def subir_resultado(
    request: Request,
    paciente_id: int = Form(...),
    turno_id: int = Form(None),
    titulo: str = Form(...),
    descripcion: str = Form(""),
    fecha_estudio: str = Form(""),
    archivo: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    user = require_staff(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    paciente = db.query(Paciente).filter(Paciente.id == paciente_id, Paciente.activo == True).first()
    if not paciente:
        return RedirectResponse(url="/admin/resultados?msg=Paciente+no+encontrado+o+inactivo.&tipo=error", status_code=302)

    file_path = None
    file_name = None

    if archivo and archivo.filename:
        ext = os.path.splitext(archivo.filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            return RedirectResponse(url="/admin/resultados?msg=Tipo+de+archivo+no+permitido.&tipo=error", status_code=302)
        contenido = await archivo.read()
        try:
            file_path, file_name = subir_archivo(contenido, archivo.filename, ext)
        except Exception:
            logger.exception("Error al subir archivo de resultado.")
            return RedirectResponse(url="/admin/resultados?msg=No+se+pudo+guardar+el+archivo.&tipo=error", status_code=302)

    staff_id = int(user["sub"]) if user.get("sub") else None
    resultado = Resultado(
        paciente_id=paciente_id, titulo=titulo.strip(),
        descripcion=descripcion.strip(), archivo_nombre=file_name,
        archivo_path=file_path, fecha_estudio=fecha_estudio,
        subido_por=staff_nombre(user),
        subido_por_id=staff_id,
    )
    db.add(resultado)
    db.flush()

    crear_notificacion(
        db, paciente_id,
        titulo="Resultado disponible",
        mensaje=f"Los resultados de tu estudio {titulo.strip()} han sido cargados.",
        tipo="resultado",
    )
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Error de base de datos al subir resultado.")
        return RedirectResponse(url="/admin/resultados?msg=No+se+pudo+subir+el+resultado.&tipo=error", status_code=302)

    if paciente and paciente.email:
        mail_resultado_disponible(paciente.email, paciente.nombre, titulo.strip(), fecha_estudio)

    return RedirectResponse(url="/admin/resultados?msg=Resultado+subido+correctamente.&tipo=success", status_code=302)


@router.get("/resultados/ver/{resultado_id}")
async def ver_resultado(request: Request, resultado_id: int, db: Session = Depends(get_db)):
    user = require_staff(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    resultado = db.query(Resultado).filter(Resultado.id == resultado_id).first()
    if not resultado or not resultado.archivo_path:
        return RedirectResponse(url="/admin/resultados?msg=Archivo+no+encontrado.&tipo=error", status_code=302)
    try:
        contenido, media_type = leer_archivo(resultado.archivo_path)
    except Exception:
        return RedirectResponse(url="/admin/resultados?msg=Archivo+no+disponible.&tipo=error", status_code=302)
    headers = {"Content-Disposition": f"inline; filename=\"{resultado.archivo_nombre or 'archivo'}\""}
    return Response(content=contenido, media_type=media_type, headers=headers)


@router.post("/resultados/eliminar/{resultado_id}")
async def eliminar_resultado(request: Request, resultado_id: int, db: Session = Depends(get_db)):
    user = require_staff(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    resultado = db.query(Resultado).filter(Resultado.id == resultado_id).first()
    if resultado:
        if resultado.archivo_path:
            eliminar_archivo(resultado.archivo_path)
        db.delete(resultado)
        db.commit()

    return RedirectResponse(url="/admin/resultados?msg=Resultado+eliminado.&tipo=success", status_code=302)


# ─── Avisos ───────────────────────────────────────────────────────────────────

@router.get("/avisos", response_class=HTMLResponse)
async def avisos_page(request: Request, db: Session = Depends(get_db)):
    user = require_admin(request)
    if not user:
        return RedirectResponse(url="/admin/?msg=Acceso+restringido.&tipo=error", status_code=302)
    avisos = db.query(Aviso).order_by(Aviso.orden.asc(), Aviso.created_at.desc()).all()
    return templates.TemplateResponse("admin/avisos.html", {
        "request": request, "user": user, "avisos": avisos,
        "msg": request.query_params.get("msg", ""),
        "msg_tipo": request.query_params.get("tipo", ""),
        "is_admin": True,
    })


@router.post("/avisos/nuevo")
async def nuevo_aviso(
    request: Request,
    titulo: str = Form(...),
    contenido: str = Form(...),
    tipo: str = Form("info"),
    orden: int = Form(0),
    db: Session = Depends(get_db)
):
    user = require_admin(request)
    if not user:
        return RedirectResponse(url="/admin/", status_code=302)
    if tipo not in ("info", "warning", "importante"):
        tipo = "info"
    aviso = Aviso(titulo=titulo.strip(), contenido=contenido.strip(), tipo=tipo, orden=orden, activo=True)
    db.add(aviso)
    db.commit()
    return RedirectResponse(url="/admin/avisos?msg=Aviso+creado.&tipo=success", status_code=302)


@router.post("/avisos/toggle/{aviso_id}")
async def toggle_aviso(request: Request, aviso_id: int, db: Session = Depends(get_db)):
    user = require_admin(request)
    if not user:
        return RedirectResponse(url="/admin/", status_code=302)
    aviso = db.query(Aviso).filter(Aviso.id == aviso_id).first()
    if aviso:
        aviso.activo = not aviso.activo
        db.commit()
    return RedirectResponse(url="/admin/avisos?msg=Aviso+actualizado.&tipo=success", status_code=302)


@router.post("/avisos/eliminar/{aviso_id}")
async def eliminar_aviso(request: Request, aviso_id: int, db: Session = Depends(get_db)):
    user = require_admin(request)
    if not user:
        return RedirectResponse(url="/admin/", status_code=302)
    aviso = db.query(Aviso).filter(Aviso.id == aviso_id).first()
    if aviso:
        db.delete(aviso)
        db.commit()
    return RedirectResponse(url="/admin/avisos?msg=Aviso+eliminado.&tipo=success", status_code=302)


@router.post("/avisos/editar/{aviso_id}")
async def editar_aviso(
    request: Request,
    aviso_id: int,
    titulo: str = Form(...),
    contenido: str = Form(...),
    tipo: str = Form("info"),
    orden: int = Form(0),
    db: Session = Depends(get_db)
):
    user = require_admin(request)
    if not user:
        return RedirectResponse(url="/admin/", status_code=302)
    aviso = db.query(Aviso).filter(Aviso.id == aviso_id).first()
    if aviso:
        aviso.titulo = titulo.strip()
        aviso.contenido = contenido.strip()
        aviso.tipo = tipo if tipo in ("info", "warning", "importante") else "info"
        aviso.orden = orden
        db.commit()
    return RedirectResponse(url="/admin/avisos?msg=Aviso+actualizado.&tipo=success", status_code=302)
