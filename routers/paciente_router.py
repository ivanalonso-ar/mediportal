import os
from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db
from models import Paciente, Turno, Resultado, Aviso
from obras_sociales import OBRAS_SOCIALES
from horarios import ESPECIALIDADES, TURNO_POR_ESPECIALIDAD, SLOTS_MANANA, SLOTS_TARDE
from disponibilidad import hora_disponible, horas_sin_disponibilidad
from notif_utils import crear_notificacion
from models import Notificacion
from auth import get_current_user, verify_password, get_password_hash, create_access_token
from mail import mail_cambio_password, mail_turno_cancelado

router = APIRouter(prefix="/paciente")
templates = Jinja2Templates(directory="templates")

def require_paciente(request: Request):
    user = get_current_user(request)
    if not user or user.get("tipo") != "paciente":
        return None
    if user.get("primer_login"):
        return None
    return user


# ─── Turnos ───────────────────────────────────────────────────────────────────

@router.get("/turnos", response_class=HTMLResponse)
async def turnos_page(request: Request, db: Session = Depends(get_db)):
    user = require_paciente(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    paciente = db.query(Paciente).filter(Paciente.id == int(user["sub"])).first()
    turnos = db.query(Turno).filter(
        Turno.paciente_id == paciente.id
    ).order_by(Turno.fecha.desc(), Turno.hora.desc()).all()

    avisos = db.query(Aviso).filter(Aviso.activo == True).order_by(Aviso.orden.asc()).all()

    notif_no_leidas = db.query(Notificacion).filter(Notificacion.paciente_id == int(user["sub"]), Notificacion.leido == False).count()
    return templates.TemplateResponse("paciente/turnos.html", {
        "request": request, "user": user, "notif_no_leidas": notif_no_leidas, "paciente": paciente,
        "turnos": turnos, "especialidades": ESPECIALIDADES,
        "turno_por_especialidad": TURNO_POR_ESPECIALIDAD,
        "slots_manana": SLOTS_MANANA,
        "slots_tarde": SLOTS_TARDE,
        "avisos": avisos,
        "msg": request.query_params.get("msg", ""),
        "msg_tipo": request.query_params.get("tipo", ""),
    })


@router.post("/turnos/solicitar")
async def solicitar_turno(
    request: Request,
    fecha: str = Form(...),
    hora: str = Form(...),
    especialidad: str = Form(...),
    tipo_consulta: str = Form("obra_social"),
    observaciones: str = Form(""),
    db: Session = Depends(get_db)
):
    user = require_paciente(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    if tipo_consulta not in ("obra_social", "particular"):
        tipo_consulta = "obra_social"
    if not hora_disponible(db, fecha, hora, especialidad):
        return RedirectResponse(
            url="/paciente/turnos?msg=Ese+horario+ya+se+ocupo.+Elegi+otro.&tipo=error",
            status_code=302
        )

    turno = Turno(
        paciente_id=int(user["sub"]),
        fecha=fecha, hora=hora, especialidad=especialidad,
        tipo_consulta=tipo_consulta,
        observaciones=observaciones, estado="confirmado"
    )
    db.add(turno)
    db.commit()
    return RedirectResponse(
        url="/paciente/turnos?msg=Turno+solicitado.+Será+confirmado+a+la+brevedad.&tipo=success",
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

    turno = db.query(Turno).filter(
        Turno.id == turno_id,
        Turno.paciente_id == int(user["sub"])
    ).first()

    if turno and turno.estado in ("pendiente", "confirmado"):
        paciente = db.query(Paciente).filter(Paciente.id == int(user["sub"])).first()
        turno.estado = "cancelado"
        db.commit()
        if paciente and paciente.email:
            mail_turno_cancelado(paciente.email, paciente.nombre, turno.especialidad, turno.fecha, turno.hora)
        return RedirectResponse(url="/paciente/turnos?msg=Turno+cancelado.&tipo=success", status_code=302)

    return RedirectResponse(url="/paciente/turnos?msg=No+se+pudo+cancelar+el+turno.&tipo=error", status_code=302)


# ─── Resultados ───────────────────────────────────────────────────────────────

@router.get("/resultados", response_class=HTMLResponse)
async def resultados_page(request: Request, db: Session = Depends(get_db)):
    user = require_paciente(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    resultados = db.query(Resultado).filter(
        Resultado.paciente_id == int(user["sub"])
    ).order_by(Resultado.created_at.desc()).all()

    notif_no_leidas = db.query(Notificacion).filter(Notificacion.paciente_id == int(user["sub"]), Notificacion.leido == False).count()
    return templates.TemplateResponse("paciente/resultados.html", {
        "request": request, "user": user, "notif_no_leidas": notif_no_leidas, "resultados": resultados,
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

    resultado = db.query(Resultado).filter(
        Resultado.id == resultado_id,
        Resultado.paciente_id == int(user["sub"])
    ).first()

    if not resultado or not resultado.archivo_path:
        return RedirectResponse(url="/paciente/resultados?msg=Archivo+no+encontrado.&tipo=error", status_code=302)
    if not os.path.exists(resultado.archivo_path):
        return RedirectResponse(url="/paciente/resultados?msg=Archivo+no+disponible+en+el+servidor.&tipo=error", status_code=302)

    return FileResponse(
        path=resultado.archivo_path,
        filename=resultado.archivo_nombre or "resultado.pdf",
        media_type="application/pdf"
    )


# ─── Perfil ───────────────────────────────────────────────────────────────────

@router.get("/perfil", response_class=HTMLResponse)
async def perfil_page(request: Request, db: Session = Depends(get_db)):
    user = require_paciente(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    paciente = db.query(Paciente).filter(Paciente.id == int(user["sub"])).first()
    notif_no_leidas = db.query(Notificacion).filter(Notificacion.paciente_id == int(user["sub"]), Notificacion.leido == False).count()
    return templates.TemplateResponse("paciente/perfil.html", {
        "request": request, "user": user, "notif_no_leidas": notif_no_leidas, "paciente": paciente,
        "obras_sociales": OBRAS_SOCIALES,
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

    paciente = db.query(Paciente).filter(Paciente.id == int(user["sub"])).first()
    if not paciente:
        return RedirectResponse(url="/login", status_code=302)

    paciente.nombre = nombre.strip()
    paciente.apellido = apellido.strip()
    paciente.email = email.strip()
    paciente.telefono = telefono.strip()
    paciente.obra_social = obra_social.strip()
    db.commit()

    # Refrescar token con nombre actualizado
    token = create_access_token({
        "sub": str(paciente.id),
        "tipo": "paciente",
        "nombre": paciente.nombre,
        "apellido": paciente.apellido,
        "primer_login": False
    })
    response = RedirectResponse(url="/paciente/perfil?msg=Datos+actualizados+correctamente.&tipo=success", status_code=302)
    response.set_cookie(key="access_token", value=token, httponly=True, max_age=28800, samesite="lax")
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
        return templates.TemplateResponse("paciente/perfil.html", {
            "request": request, "user": user, "paciente": paciente,
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


@router.get("/notificaciones", response_class=HTMLResponse)
async def notificaciones_page(request: Request, db: Session = Depends(get_db)):
    user = require_paciente(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    notifs = db.query(Notificacion).filter(
        Notificacion.paciente_id == int(user["sub"])
    ).order_by(Notificacion.created_at.desc()).all()
    notif_no_leidas = sum(1 for n in notifs if not n.leido)
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
