import os
import uuid
import datetime
from fastapi import APIRouter, Request, Form, Depends, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db
from models import Paciente, UsuarioStaff, Turno, TurnoLog, Resultado, Aviso
from obras_sociales import OBRAS_SOCIALES
from notif_utils import crear_notificacion
from horarios import ESPECIALIDADES, TURNO_POR_ESPECIALIDAD, SLOTS_MANANA, SLOTS_TARDE, profesionales_json
from disponibilidad import hora_disponible
from auth import get_current_user, get_password_hash
from mail import mail_bienvenida, mail_turno_confirmado, mail_turno_cancelado, mail_resultado_disponible, mail_registro_aprobado, mail_registro_rechazado

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory="templates")

UPLOAD_DIR = "uploads/resultados"

ESTADOS_TURNO = ["pendiente", "confirmado", "cancelado", "completado"]


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

    ultimos_turnos = db.query(Turno).order_by(Turno.created_at.desc()).limit(5).all()

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

    turnos = query.order_by(Turno.fecha.desc(), Turno.hora.asc()).all()
    pacientes = db.query(Paciente).filter(Paciente.activo == True).order_by(Paciente.apellido).all()

    # Profesionales disponibles para asignar
    profesionales = db.query(UsuarioStaff).filter(
        UsuarioStaff.rol == "profesional", UsuarioStaff.activo == True
    ).order_by(UsuarioStaff.apellido).all()

    return templates.TemplateResponse("admin/turnos.html", {
        "request": request, "user": user,
        "turnos": turnos, "pacientes": pacientes,
        "profesionales": profesionales,
        "especialidades": ESPECIALIDADES,
        "obras_sociales": OBRAS_SOCIALES,
        "turno_por_especialidad": TURNO_POR_ESPECIALIDAD,
        "slots_manana": SLOTS_MANANA,
        "slots_tarde": SLOTS_TARDE,
        "profesionales_json": profesionales_json(),
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

    query = db.query(Turno).filter(
        Turno.fecha == fecha_str,
        Turno.estado.notin_(["cancelado"])
    )
    if filtro_prof:
        query = query.filter(Turno.profesional == filtro_prof)

    turnos = query.order_by(Turno.hora.asc(), Turno.tipo.asc()).all()

    profesionales = db.query(UsuarioStaff).filter(
        UsuarioStaff.rol == "profesional", UsuarioStaff.activo == True
    ).order_by(UsuarioStaff.apellido).all()

    # Calcular fecha anterior y siguiente para navegación
    fecha_obj = datetime.datetime.strptime(fecha_str, "%Y-%m-%d").date()
    fecha_anterior = (fecha_obj - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    fecha_siguiente = (fecha_obj + datetime.timedelta(days=1)).strftime("%Y-%m-%d")

    return templates.TemplateResponse("admin/agenda.html", {
        "request": request, "user": user,
        "turno_por_especialidad": TURNO_POR_ESPECIALIDAD,
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
    if not hora_disponible(db, fecha, hora, especialidad, profesional.strip()):
        return RedirectResponse(
            url="/admin/turnos?msg=Ese+horario+ya+no+esta+disponible.+Elegi+otro.&tipo=error",
            status_code=302
        )

    nombre_staff = staff_nombre(user)
    turno = Turno(
        paciente_id=paciente_id, fecha=fecha, hora=hora,
        especialidad=especialidad, profesional=profesional.strip(),
        observaciones=observaciones.strip(),
        estado="confirmado", tipo=tipo, tipo_consulta=tipo_consulta,
        created_by=nombre_staff,
    )
    db.add(turno)
    db.flush()

    log_turno(db, turno.id, "creado",
        f"{nombre_staff} creó {'sobreturno' if tipo == 'sobreturno' else 'turno'} — {fecha} {hora}hs — {especialidad}",
        nombre_staff)
    db.commit()

    paciente = db.query(Paciente).filter(Paciente.id == paciente_id).first()
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

    turno.fecha = fecha
    turno.hora = hora
    turno.especialidad = especialidad
    turno.profesional = profesional.strip()
    turno.tipo = tipo if tipo in ("normal", "sobreturno") else "normal"
    turno.tipo_consulta = tipo_consulta if tipo_consulta in ("obra_social", "particular") else "obra_social"
    turno.observaciones = observaciones.strip()

    if cambios:
        log_turno(db, turno.id, "modificado",
            f"{nombre_staff} modificó: {', '.join(cambios)}",
            nombre_staff)

    db.commit()
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

@router.get("/resultados", response_class=HTMLResponse)
async def resultados_page(request: Request, db: Session = Depends(get_db)):
    user = require_staff(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    resultados = db.query(Resultado).order_by(Resultado.created_at.desc()).all()
    pacientes = db.query(Paciente).filter(Paciente.activo == True).order_by(Paciente.apellido).all()

    return templates.TemplateResponse("admin/resultados.html", {
        "request": request, "user": user,
        "resultados": resultados, "pacientes": pacientes,
        "msg": request.query_params.get("msg", ""),
        "msg_tipo": request.query_params.get("tipo", ""),
        "is_admin": is_admin(user),
    })


@router.post("/resultados/subir")
async def subir_resultado(
    request: Request,
    paciente_id: int = Form(...),
    titulo: str = Form(...),
    descripcion: str = Form(""),
    fecha_estudio: str = Form(""),
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    user = require_staff(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    if not archivo.filename.lower().endswith(".pdf"):
        return RedirectResponse(url="/admin/resultados?msg=Solo+se+permiten+archivos+PDF.&tipo=error", status_code=302)

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    unique_name = f"{uuid.uuid4().hex}_{archivo.filename}"
    file_path = os.path.join(UPLOAD_DIR, unique_name)

    with open(file_path, "wb") as f:
        content = await archivo.read()
        f.write(content)

    resultado = Resultado(
        paciente_id=paciente_id, titulo=titulo.strip(),
        descripcion=descripcion.strip(), archivo_nombre=archivo.filename,
        archivo_path=file_path, fecha_estudio=fecha_estudio,
        subido_por=staff_nombre(user),
    )
    db.add(resultado)
    db.commit()

    paciente = db.query(Paciente).filter(Paciente.id == paciente_id).first()
    if paciente and paciente.email:
        mail_resultado_disponible(paciente.email, paciente.nombre, titulo.strip(), fecha_estudio)

    return RedirectResponse(url="/admin/resultados?msg=Resultado+subido+correctamente.&tipo=success", status_code=302)


@router.post("/resultados/eliminar/{resultado_id}")
async def eliminar_resultado(request: Request, resultado_id: int, db: Session = Depends(get_db)):
    user = require_staff(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    resultado = db.query(Resultado).filter(Resultado.id == resultado_id).first()
    if resultado:
        if resultado.archivo_path and os.path.exists(resultado.archivo_path):
            os.remove(resultado.archivo_path)
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
