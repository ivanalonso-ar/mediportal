import os
import datetime
import logging
from fastapi import APIRouter, Request, Form, Depends, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from database import get_db
from models import Paciente, Turno, Resultado, UsuarioStaff
from auth import get_current_user
from notif_utils import crear_notificacion
from storage import subir_archivo
from constants import ALLOWED_EXTENSIONS

from templates_config import templates

router = APIRouter(prefix="/paciente")
logger = logging.getLogger("mediportal.paciente")

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
        return RedirectResponse(url="/paciente/informes?msg=Paciente+no+autorizado.&tipo_msg=error", status_code=302)

    file_path = None
    file_name = None

    if archivo and archivo.filename:
        ext = os.path.splitext(archivo.filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            return RedirectResponse(
                url="/paciente/informes?msg=Tipo+de+archivo+no+permitido.&tipo_msg=error",
                status_code=302
            )
        contenido = await archivo.read()
        try:
            file_path, file_name = subir_archivo(contenido, archivo.filename, ext)
        except Exception:
            logger.exception("Error al subir archivo de informe.")
            return RedirectResponse(url="/paciente/informes?msg=No+se+pudo+guardar+el+archivo.&tipo_msg=error", status_code=302)

    resultado = Resultado(
        paciente_id=paciente_id, titulo=titulo.strip(),
        descripcion=descripcion.strip(), archivo_nombre=file_name,
        archivo_path=file_path, fecha_estudio=fecha_estudio,
        subido_por=mi_nombre,
    )
    db.add(resultado)
    db.flush()

    # Verificación con lock para serializar requests concurrentes en PostgreSQL
    if not hora_disponible(db, fecha, hora, especialidad,
                           profesional=profesional_nombre.strip() if profesional_nombre else "",
                           lock=True):
        return RedirectResponse(
            url=f"/paciente/turnos?msg=Ese+horario+ya+se+ocupo.+Elegi+otro.&tipo=error&para={destino_id}",
            status_code=302
        )

    turno = Turno(
        paciente_id=destino_id,
        fecha=fecha, hora=hora, especialidad=especialidad,
        profesional=profesional_nombre.strip() if profesional_nombre else None,
        tipo_consulta=tipo_consulta,
        observaciones=observaciones, estado="confirmado"
    )
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Error de base de datos al solicitar turno.")
        return RedirectResponse(url=f"/paciente/turnos?msg=Ese+horario+ya+fue+tomado.+Elegi+otro.&tipo=error&para={destino_id}", status_code=302)
    return RedirectResponse(
        url=f"/paciente/turnos?msg=Turno+solicitado.&tipo=success&para={destino_id}",
        status_code=302
    )


@router.get("/turnos/disponibilidad")
async def disponibilidad_turnos(
    request: Request,
    fecha: str,
    especialidad: str,
    db: Session = Depends(get_db)
):
    user = require_paciente(request)
    if not user:
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
    bloqueados = sorted(horas_sin_disponibilidad(db, fecha, especialidad))
    return {"ok": True, "ocupados": bloqueados}


@router.post("/turnos/cancelar/{turno_id}")
async def cancelar_turno(
    request: Request,
    turno_id: int,
    db: Session = Depends(get_db)
):
    user = require_paciente(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    pid = int(user["sub"])
    miembro_ids = [m.miembro_id for m in db.query(GrupoFamiliar).filter(GrupoFamiliar.titular_id == pid).all()]
    todos_ids = [pid] + miembro_ids

    turno = db.query(Turno).filter(
        Turno.id == turno_id,
        Turno.paciente_id.in_(todos_ids)
    ).first()

    if turno and turno.estado in ("pendiente", "confirmado"):
        import datetime as _dt
        pac = db.query(Paciente).filter(Paciente.id == turno.paciente_id).first()
        turno.estado = "cancelado"
        try:
            fecha_fmt = _dt.datetime.strptime(turno.fecha, "%Y-%m-%d").strftime("%d/%m/%Y")
        except ValueError:
            fecha_fmt = turno.fecha
        profesional_nombre_notif = turno.profesional or "el profesional asignado"
        crear_notificacion(
            db, turno.paciente_id,
            titulo="Turno cancelado",
            mensaje=f"Tu turno para el día {fecha_fmt} a las {turno.hora} hs con {profesional_nombre_notif} ha sido cancelado.",
            tipo="turno_cancelado",
        )
        db.commit()
        if pac and pac.email:
            mail_turno_cancelado(pac.email, pac.nombre, turno.especialidad, turno.fecha, turno.hora)
        return RedirectResponse(url="/paciente/turnos?msg=Turno+cancelado.&tipo=success", status_code=302)

    return RedirectResponse(url="/paciente/turnos?msg=No+se+pudo+cancelar+el+turno.&tipo=error", status_code=302)


# ─── Resultados ───────────────────────────────────────────────────────────────

@router.get("/resultados", response_class=HTMLResponse)
async def resultados_page(request: Request, db: Session = Depends(get_db)):
    user = require_paciente(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    pid = int(user["sub"])
    miembro_ids = [m.miembro_id for m in db.query(GrupoFamiliar).filter(GrupoFamiliar.titular_id == pid).all()]
    todos_ids = [pid] + miembro_ids
    miembros = [db.query(Paciente).filter(Paciente.id == mid).first() for mid in miembro_ids]

    para = int(request.query_params.get("para", pid))
    if para not in todos_ids:
        para = pid
    pac_sel = db.query(Paciente).filter(Paciente.id == para).first()

    resultados = db.query(Resultado).filter(
        Resultado.paciente_id == para
    ).order_by(Resultado.created_at.desc()).all()

    return templates.TemplateResponse("paciente/resultados.html", {
        "request": request, "user": user,
        "notif_no_leidas": _notif_count(db, pid),
        "resultados": resultados,
        "miembros": miembros,
        "paciente_sel": pac_sel,
        "para": para,
        "msg": request.query_params.get("msg", ""),
        "msg_tipo": request.query_params.get("tipo", ""),
    })


@router.get("/resultados/descargar/{resultado_id}")
async def descargar_resultado(
    request: Request,
    resultado_id: int,
    db: Session = Depends(get_db)
):
    user = require_paciente(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    pid = int(user["sub"])
    miembro_ids = [m.miembro_id for m in db.query(GrupoFamiliar).filter(GrupoFamiliar.titular_id == pid).all()]
    todos_ids = [pid] + miembro_ids

    resultado = db.query(Resultado).filter(
        Resultado.id == resultado_id,
        Resultado.paciente_id.in_(todos_ids)
    ).first()

    if not resultado or not resultado.archivo_path:
        return RedirectResponse(url="/paciente/resultados?msg=Archivo+no+encontrado.&tipo=error", status_code=302)

    if not os.path.exists(resultado.archivo_path):
        try:
            url_firmada = generar_url_firmada(resultado.archivo_path)
        except Exception:
            return RedirectResponse(url="/paciente/resultados?msg=Archivo+no+disponible.&tipo=error", status_code=302)
        if url_firmada and url_firmada.startswith("http"):
            return RedirectResponse(url=url_firmada, status_code=302)
        return RedirectResponse(url="/paciente/resultados?msg=Archivo+no+disponible+en+el+servidor.&tipo=error", status_code=302)

    media_type, _ = mimetypes.guess_type(resultado.archivo_path)
    media_type = media_type or "application/octet-stream"

    return FileResponse(
        path=resultado.archivo_path,
        filename=resultado.archivo_nombre or "resultado",
        media_type=media_type
    )


# ─── Perfil ───────────────────────────────────────────────────────────────────

@router.get("/perfil", response_class=HTMLResponse)
async def perfil_page(request: Request, db: Session = Depends(get_db)):
    user = require_paciente(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    pid = int(user["sub"])
    paciente = db.query(Paciente).filter(Paciente.id == pid).first()

    miembros_rel = db.query(GrupoFamiliar).filter(GrupoFamiliar.titular_id == pid).all()
    miembros = [(rel, db.query(Paciente).filter(Paciente.id == rel.miembro_id).first()) for rel in miembros_rel]

    solicitudes_recibidas = db.query(SolicitudGrupo).filter(
        SolicitudGrupo.destinatario_id == pid,
        SolicitudGrupo.estado == "pendiente"
    ).all()

    return templates.TemplateResponse("paciente/perfil.html", {
        "request": request, "user": user,
        "notif_no_leidas": _notif_count(db, pid),
        "paciente": paciente,
        "obras_sociales": listar_obras_sociales(db),
        "miembros": miembros,
        "solicitudes_recibidas": solicitudes_recibidas,
        "msg": request.query_params.get("msg", ""),
        "msg_tipo": request.query_params.get("tipo", ""),
    })


@router.post("/perfil/editar")
async def perfil_editar(
    request: Request,
    nombre: str = Form(...),
    apellido: str = Form(...),
    email: str = Form(""),
    telefono: str = Form(""),
    obra_social: str = Form(""),
    db: Session = Depends(get_db)
):
    user = require_paciente(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    nombre = nombre.strip()
    apellido = apellido.strip()

    if not RE_SOLO_LETRAS.match(nombre):
        return RedirectResponse(url="/paciente/perfil?msg=El+nombre+no+puede+contener+numeros.&tipo=error", status_code=302)
    if not RE_SOLO_LETRAS.match(apellido):
        return RedirectResponse(url="/paciente/perfil?msg=El+apellido+no+puede+contener+numeros.&tipo=error", status_code=302)
    if telefono.strip() and not RE_SOLO_NUMEROS.match(telefono.strip()):
        return RedirectResponse(url="/paciente/perfil?msg=El+telefono+solo+puede+contener+numeros.&tipo=error", status_code=302)

    paciente = db.query(Paciente).filter(Paciente.id == int(user["sub"])).first()
    if not paciente:
        return RedirectResponse(url="/login", status_code=302)

    paciente.nombre = nombre
    paciente.apellido = apellido
    paciente.email = email.strip()
    paciente.telefono = telefono.strip()
    paciente.obra_social = obra_social.strip()
    db.commit()

    token = create_access_token({
        "sub": str(paciente.id),
        "tipo": "paciente",
        "nombre": paciente.nombre,
        "apellido": paciente.apellido,
        "primer_login": False
    })
    response = RedirectResponse(url="/paciente/perfil?msg=Datos+actualizados+correctamente.&tipo=success", status_code=302)
    set_auth_cookie(response, token)
    return response


@router.post("/perfil/cambiar-password")
async def perfil_cambiar_password(
    request: Request,
    password_actual: str = Form(...),
    nueva_password: str = Form(...),
    confirmar_password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = require_paciente(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    paciente = db.query(Paciente).filter(Paciente.id == int(user["sub"])).first()
    if not paciente:
        return RedirectResponse(url="/login", status_code=302)

    def error(msg):
        pid = int(user["sub"])
        miembros_rel = db.query(GrupoFamiliar).filter(GrupoFamiliar.titular_id == pid).all()
        miembros = [(rel, db.query(Paciente).filter(Paciente.id == rel.miembro_id).first()) for rel in miembros_rel]
        solicitudes_recibidas = db.query(SolicitudGrupo).filter(
            SolicitudGrupo.destinatario_id == pid, SolicitudGrupo.estado == "pendiente"
        ).all()
        return templates.TemplateResponse("paciente/perfil.html", {
            "request": request, "user": user, "paciente": paciente,
            "obras_sociales": listar_obras_sociales(db),
            "miembros": miembros,
            "solicitudes_recibidas": solicitudes_recibidas,
            "msg": msg, "msg_tipo": "error", "tab": "password"
        })

    if not verify_password(password_actual, paciente.password_hash):
        return error("La contraseña actual es incorrecta.")
    if nueva_password != confirmar_password:
        return error("Las contraseñas nuevas no coinciden.")
    if len(nueva_password) < 6:
        return error("La contraseña debe tener al menos 6 caracteres.")
    if nueva_password == password_actual:
        return error("La nueva contraseña debe ser diferente a la actual.")

    paciente.password_hash = get_password_hash(nueva_password)
    db.commit()
    if paciente.email:
        mail_cambio_password(paciente.email, paciente.nombre)

    return RedirectResponse(url="/paciente/perfil?msg=Contraseña+cambiada+correctamente.&tipo=success", status_code=302)


# ─── Grupo familiar ───────────────────────────────────────────────────────────

@router.post("/familia/invitar")
async def invitar_familiar(
    request: Request,
    dni_familiar: str = Form(...),
    parentesco: str = Form(""),
    db: Session = Depends(get_db)
):
    user = require_paciente(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    pid = int(user["sub"])
    dni_familiar = dni_familiar.strip()

    if not RE_SOLO_NUMEROS.match(dni_familiar):
        return RedirectResponse(url="/paciente/perfil?msg=DNI+invalido.&tipo=error", status_code=302)

    familiar = db.query(Paciente).filter(Paciente.dni == dni_familiar, Paciente.activo == True).first()
    if not familiar:
        return RedirectResponse(url="/paciente/perfil?msg=No+se+encontro+un+paciente+con+ese+DNI.&tipo=error", status_code=302)
    if familiar.id == pid:
        return RedirectResponse(url="/paciente/perfil?msg=No+podes+agregarte+a+vos+mismo.&tipo=error", status_code=302)

    # Fix 8: impedir ciclo — si el familiar ya es titular mío, no puede ser mi miembro
    ciclo = db.query(GrupoFamiliar).filter(
        GrupoFamiliar.titular_id == familiar.id,
        GrupoFamiliar.miembro_id == pid
    ).first()
    if ciclo:
        return RedirectResponse(url="/paciente/perfil?msg=Ese+paciente+ya+te+tiene+en+su+grupo+familiar.&tipo=error", status_code=302)

    # Ya vinculados
    ya = db.query(GrupoFamiliar).filter(
        GrupoFamiliar.titular_id == pid, GrupoFamiliar.miembro_id == familiar.id
    ).first()
    if ya:
        return RedirectResponse(url="/paciente/perfil?msg=Ya+es+parte+de+tu+grupo.&tipo=error", status_code=302)

    # Solicitud existente
    sol_existente = db.query(SolicitudGrupo).filter(
        SolicitudGrupo.solicitante_id == pid,
        SolicitudGrupo.destinatario_id == familiar.id,
        SolicitudGrupo.estado == "pendiente"
    ).first()
    if sol_existente:
        return RedirectResponse(url="/paciente/perfil?msg=Ya+enviaste+una+solicitud+a+esa+persona.&tipo=error", status_code=302)

    sol = SolicitudGrupo(solicitante_id=pid, destinatario_id=familiar.id, parentesco=parentesco.strip())
    db.add(sol)
    db.commit()

    return RedirectResponse(url="/paciente/perfil?msg=Solicitud+enviada.+El+familiar+debe+aceptarla.&tipo=success", status_code=302)


@router.post("/familia/aceptar/{solicitud_id}")
async def aceptar_solicitud(
    request: Request,
    solicitud_id: int,
    db: Session = Depends(get_db)
):
    user = require_paciente(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    pid = int(user["sub"])
    sol = db.query(SolicitudGrupo).filter(
        SolicitudGrupo.id == solicitud_id,
        SolicitudGrupo.destinatario_id == pid,
        SolicitudGrupo.estado == "pendiente"
    ).first()

    if not sol:
        return RedirectResponse(url="/paciente/perfil?msg=Solicitud+no+encontrada.&tipo=error", status_code=302)

    sol.estado = "aceptada"
    # El solicitante pasa a ser titular, el destinatario (yo) pasa a ser miembro
    vinculo = GrupoFamiliar(
        titular_id=sol.solicitante_id,
        miembro_id=pid,
        parentesco=sol.parentesco
    )
    db.add(vinculo)
    db.commit()

    return RedirectResponse(url="/paciente/perfil?msg=Te+uniste+al+grupo+familiar.&tipo=success", status_code=302)


@router.post("/familia/rechazar/{solicitud_id}")
async def rechazar_solicitud(
    request: Request,
    solicitud_id: int,
    db: Session = Depends(get_db)
):
    user = require_paciente(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    pid = int(user["sub"])
    sol = db.query(SolicitudGrupo).filter(
        SolicitudGrupo.id == solicitud_id,
        SolicitudGrupo.destinatario_id == pid,
        SolicitudGrupo.estado == "pendiente"
    ).first()
    if sol:
        sol.estado = "rechazada"
        db.commit()

    return RedirectResponse(url="/paciente/perfil?msg=Solicitud+rechazada.&tipo=success", status_code=302)


@router.post("/familia/eliminar/{miembro_id}")
async def eliminar_familiar(
    request: Request,
    miembro_id: int,
    db: Session = Depends(get_db)
):
    user = require_paciente(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    pid = int(user["sub"])
    vinculo = db.query(GrupoFamiliar).filter(
        GrupoFamiliar.titular_id == pid,
        GrupoFamiliar.miembro_id == miembro_id
    ).first()
    if vinculo:
        db.delete(vinculo)
        db.commit()

    return RedirectResponse(url="/paciente/perfil?msg=Familiar+eliminado+del+grupo.&tipo=success", status_code=302)


# ─── Notificaciones ───────────────────────────────────────────────────────────

@router.get("/notificaciones", response_class=HTMLResponse)
async def notificaciones_page(request: Request, db: Session = Depends(get_db)):
    user = require_paciente(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    pid = int(user["sub"])
    notifs = db.query(Notificacion).filter(
        Notificacion.paciente_id == pid
    ).order_by(Notificacion.created_at.desc()).all()
    # Marcar todas como leídas al visitar
    for n in notifs:
        if not n.leido:
            n.leido = True
    db.commit()
    notif_no_leidas = 0
    return templates.TemplateResponse("paciente/notificaciones.html", {
        "request": request, "user": user,
        "notificaciones": notifs,
        "notif_no_leidas": notif_no_leidas,
    })


@router.post("/notificaciones/marcar-todas")
async def marcar_todas_leidas(request: Request, db: Session = Depends(get_db)):
    user = require_paciente(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    db.query(Notificacion).filter(
        Notificacion.paciente_id == int(user["sub"]),
        Notificacion.leido == False
    ).update({"leido": True})
    db.commit()
    return RedirectResponse(url="/paciente/notificaciones", status_code=302)


@router.post("/notificaciones/eliminar/{notif_id}")
async def eliminar_notificacion(request: Request, notif_id: int, db: Session = Depends(get_db)):
    user = require_paciente(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    n = db.query(Notificacion).filter(
        Notificacion.id == notif_id,
        Notificacion.paciente_id == int(user["sub"])
    ).first()
    if n:
        db.delete(n)
        db.commit()
    return RedirectResponse(url="/paciente/notificaciones", status_code=302)
