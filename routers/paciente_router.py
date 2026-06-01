from templates_config import templates
import os
import re
import mimetypes
import logging
from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from database import get_db
from models import Paciente, Turno, Resultado, Aviso, Notificacion, GrupoFamiliar, SolicitudGrupo
from obras_sociales import listar_obras_sociales
from horarios import catalogo_horarios
from disponibilidad import hora_disponible, horas_sin_disponibilidad
from notif_utils import crear_notificacion
from auth import get_current_user, verify_password, get_password_hash, create_access_token, set_auth_cookie
from mail import mail_cambio_password, mail_turno_cancelado
from storage import generar_url_firmada

router = APIRouter(prefix="/paciente")
logger = logging.getLogger("mediportal.paciente")

RE_SOLO_LETRAS = re.compile(r"^[a-záéíóúüñA-ZÁÉÍÓÚÜÑ\s\-']+$")
RE_SOLO_NUMEROS = re.compile(r"^\d+$")


def require_paciente(request: Request):
    user = get_current_user(request)
    if not user or user.get("tipo") != "paciente":
        return None
    if user.get("primer_login"):
        return None
    return user


def _notif_count(db, paciente_id):
    return db.query(Notificacion).filter(
        Notificacion.paciente_id == paciente_id,
        Notificacion.leido == False
    ).count()


# ─── Turnos ───────────────────────────────────────────────────────────────────

@router.get("/turnos", response_class=HTMLResponse)
async def turnos_page(request: Request, db: Session = Depends(get_db)):
    user = require_paciente(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    pid = int(user["sub"])
    paciente = db.query(Paciente).filter(Paciente.id == pid).first()

    # IDs propios + miembros del grupo
    miembros_rel = db.query(GrupoFamiliar).filter(GrupoFamiliar.titular_id == pid).all()
    miembro_ids = [m.miembro_id for m in miembros_rel]
    todos_ids = [pid] + miembro_ids
    miembros = [db.query(Paciente).filter(Paciente.id == mid).first() for mid in miembro_ids]

    # Paciente seleccionado (para gestionar turno de familiar)
    paciente_sel_id = int(request.query_params.get("para", pid))
    if paciente_sel_id not in todos_ids:
        paciente_sel_id = pid
    paciente_sel = db.query(Paciente).filter(Paciente.id == paciente_sel_id).first()

    turnos = db.query(Turno).filter(
        Turno.paciente_id == paciente_sel_id
    ).order_by(Turno.fecha.desc(), Turno.hora.desc()).all()

    avisos = db.query(Aviso).filter(Aviso.activo == True).order_by(Aviso.orden.asc()).all()
    catalogo = catalogo_horarios(db)

    return templates.TemplateResponse("paciente/turnos.html", {
        "request": request, "user": user,
        "notif_no_leidas": _notif_count(db, pid),
        "paciente": paciente,
        "paciente_sel": paciente_sel,
        "miembros": miembros,
        "turnos": turnos,
        "especialidades": catalogo["especialidades"],
        "turno_por_especialidad": catalogo["turno_por_especialidad"],
        "slots_manana": catalogo["slots_manana"],
        "slots_tarde": catalogo["slots_tarde"],
        "profesionales_json": catalogo["profesionales_json"],
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
    profesional_nombre: str = Form(""),
    tipo_consulta: str = Form("obra_social"),
    observaciones: str = Form(""),
    para_paciente_id: int = Form(None),
    db: Session = Depends(get_db)
):
    user = require_paciente(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    pid = int(user["sub"])
    if tipo_consulta not in ("obra_social", "particular"):
        tipo_consulta = "obra_social"

    # Validar fecha no pasada
    import datetime as dt
    try:
        fecha_dt = dt.datetime.strptime(fecha, "%Y-%m-%d").date()
        if fecha_dt < dt.date.today():
            return RedirectResponse(url=f"/paciente/turnos?msg=No+podes+solicitar+un+turno+en+una+fecha+pasada.&tipo=error&para={para_paciente_id or pid}", status_code=302)
    except ValueError:
        return RedirectResponse(url="/paciente/turnos?msg=Fecha+invalida.&tipo=error", status_code=302)

    # Validar que el paciente destino sea el titular o un miembro del grupo
    if para_paciente_id and para_paciente_id != pid:
        rel = db.query(GrupoFamiliar).filter(
            GrupoFamiliar.titular_id == pid,
            GrupoFamiliar.miembro_id == para_paciente_id
        ).first()
        if not rel:
            return RedirectResponse(url="/paciente/turnos?msg=Paciente+no+autorizado.&tipo=error", status_code=302)
        destino_id = para_paciente_id
    else:
        destino_id = pid

    destino = db.query(Paciente).filter(Paciente.id == destino_id, Paciente.activo == True).first()
    if not destino:
        return RedirectResponse(url="/paciente/turnos?msg=Paciente+no+encontrado.&tipo=error", status_code=302)

    if not hora_disponible(db, fecha, hora, especialidad):
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
    db.add(turno)
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Error de base de datos al solicitar turno.")
        return RedirectResponse(url=f"/paciente/turnos?msg=No+se+pudo+solicitar+el+turno.&tipo=error&para={destino_id}", status_code=302)
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
        pac = db.query(Paciente).filter(Paciente.id == turno.paciente_id).first()
        turno.estado = "cancelado"
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


@router.get("/resultados/imprimir/{resultado_id}", response_class=HTMLResponse)
async def imprimir_resultado(
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

    url_descarga = f"/paciente/resultados/descargar/{resultado_id}"
    nombre = resultado.titulo or resultado.archivo_nombre or "Resultado"

    # Página mínima: embebe el PDF y dispara impresión automáticamente
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <title>{nombre}</title>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: sans-serif; background: #1e293b; display: flex; flex-direction: column; height: 100vh; }}
    #barra {{ background: #0f172a; color: #e2e8f0; padding: 10px 16px; display: flex; align-items: center; gap: 12px; flex-shrink: 0; }}
    #barra span {{ font-size: 14px; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    #barra a {{ text-decoration: none; font-size: 13px; padding: 6px 14px; border-radius: 6px; font-weight: 500; }}
    .btn-imprimir {{ background: #3b82f6; color: #fff; }}
    .btn-imprimir:hover {{ background: #2563eb; }}
    .btn-descargar {{ background: #334155; color: #e2e8f0; border: 1px solid #475569; }}
    .btn-descargar:hover {{ background: #475569; }}
    embed {{ flex: 1; width: 100%; border: none; }}
    @media print {{ #barra {{ display: none; }} embed {{ height: 100vh; }} }}
  </style>
</head>
<body>
  <div id="barra">
    <span>{nombre}</span>
    <a href="{url_descarga}" download class="btn-descargar">⬇ Descargar</a>
    <a href="#" onclick="window.print(); return false;" class="btn-imprimir">🖨 Imprimir</a>
  </div>
  <embed id="visor" src="{url_descarga}" type="application/pdf">
  <script>
    // Dispara el diálogo de impresión una vez que el PDF cargó
    document.getElementById("visor").addEventListener("load", function() {{
      setTimeout(function() {{ window.print(); }}, 400);
    }});
    // Fallback por si el evento load no dispara (algunos browsers con plugins)
    window.addEventListener("load", function() {{
      setTimeout(function() {{ window.print(); }}, 1200);
    }});
  </script>
</body>
</html>"""
    return HTMLResponse(content=html)


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

    # Impedir ciclo — si el familiar ya es titular mío, no puede ser mi miembro
    ciclo = db.query(GrupoFamiliar).filter(
        GrupoFamiliar.titular_id == familiar.id,
        GrupoFamiliar.miembro_id == pid
    ).first()
    if ciclo:
        return RedirectResponse(url="/paciente/perfil?msg=Ese+paciente+ya+te+tiene+en+su+grupo+familiar.&tipo=error", status_code=302)

    ya = db.query(GrupoFamiliar).filter(
        GrupoFamiliar.titular_id == pid, GrupoFamiliar.miembro_id == familiar.id
    ).first()
    if ya:
        return RedirectResponse(url="/paciente/perfil?msg=Ya+es+parte+de+tu+grupo.&tipo=error", status_code=302)

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
