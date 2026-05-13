from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db
from models import Paciente, UsuarioStaff
from auth import verify_password, get_password_hash, create_access_token, get_current_user
from mail import mail_cambio_password, mail_registro_pendiente_staff, mail_registro_aprobado, mail_registro_rechazado

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return RedirectResponse(url="/login")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    user = get_current_user(request)
    if user:
        if user.get("tipo") == "staff":
            return RedirectResponse(url="/admin/")
        return RedirectResponse(url="/paciente/turnos")
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login")
async def login_post(
    request: Request,
    tipo: str = Form(...),
    dni_email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    if tipo == "paciente":
        paciente = db.query(Paciente).filter(
            Paciente.dni == dni_email.strip(),
            Paciente.activo == True
        ).first()
        if not paciente or not verify_password(password, paciente.password_hash):
            return templates.TemplateResponse("login.html", {
                "request": request,
                "error": "DNI o contraseña incorrectos."
            })
        if not paciente.aprobado:
            return templates.TemplateResponse("login.html", {
                "request": request,
                "error": "Tu cuenta está pendiente de aprobación. Te avisaremos por email cuando esté lista."
            })
        token = create_access_token({
            "sub": str(paciente.id),
            "tipo": "paciente",
            "nombre": paciente.nombre,
            "apellido": paciente.apellido,
            "primer_login": paciente.primer_login
        })
        if paciente.primer_login:
            response = RedirectResponse(url="/cambiar-password", status_code=302)
        else:
            response = RedirectResponse(url="/paciente/turnos", status_code=302)
        response.set_cookie(key="access_token", value=token, httponly=True, max_age=28800, samesite="lax")
        return response

    else:
        staff = db.query(UsuarioStaff).filter(
            UsuarioStaff.email == dni_email.strip().lower(),
            UsuarioStaff.activo == True
        ).first()
        if not staff or not verify_password(password, staff.password_hash):
            return templates.TemplateResponse("login.html", {
                "request": request,
                "error": "Email o contraseña incorrectos."
            })
        token = create_access_token({
            "sub": str(staff.id),
            "tipo": "staff",
            "nombre": staff.nombre,
            "apellido": staff.apellido,
            "rol": staff.rol
        })
        if staff.rol == "profesional":
            response = RedirectResponse(url="/profesional/agenda", status_code=302)
        else:
            response = RedirectResponse(url="/admin/", status_code=302)
        response.set_cookie(key="access_token", value=token, httponly=True, max_age=28800, samesite="lax")
        return response


@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("access_token")
    return response


# ─── Cambiar contraseña (primer login) ────────────────────────────────────────

@router.get("/cambiar-password", response_class=HTMLResponse)
async def cambiar_password_page(request: Request):
    user = get_current_user(request)
    if not user or user.get("tipo") != "paciente":
        return RedirectResponse(url="/login", status_code=302)
    if not user.get("primer_login"):
        return RedirectResponse(url="/paciente/turnos", status_code=302)
    return templates.TemplateResponse("cambiar_password.html", {"request": request, "user": user, "primer_login": True})


@router.post("/cambiar-password")
async def cambiar_password_post(
    request: Request,
    nueva_password: str = Form(...),
    confirmar_password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = get_current_user(request)
    if not user or user.get("tipo") != "paciente":
        return RedirectResponse(url="/login", status_code=302)

    if nueva_password != confirmar_password:
        return templates.TemplateResponse("cambiar_password.html", {
            "request": request, "user": user, "primer_login": True,
            "error": "Las contraseñas no coinciden."
        })
    if len(nueva_password) < 6:
        return templates.TemplateResponse("cambiar_password.html", {
            "request": request, "user": user, "primer_login": True,
            "error": "La contraseña debe tener al menos 6 caracteres."
        })

    paciente = db.query(Paciente).filter(Paciente.id == int(user["sub"])).first()
    if not paciente:
        return RedirectResponse(url="/login", status_code=302)

    paciente.password_hash = get_password_hash(nueva_password)
    paciente.primer_login = False
    db.commit()

    # Notificación
    if paciente.email:
        mail_cambio_password(paciente.email, paciente.nombre)

    token = create_access_token({
        "sub": str(paciente.id),
        "tipo": "paciente",
        "nombre": paciente.nombre,
        "apellido": paciente.apellido,
        "primer_login": False
    })
    response = RedirectResponse(url="/paciente/turnos", status_code=302)
    response.set_cookie(key="access_token", value=token, httponly=True, max_age=28800, samesite="lax")
    return response


# ─── Registro público ─────────────────────────────────────────────────────────

@router.get("/registro", response_class=HTMLResponse)
async def registro_page(request: Request):
    user = get_current_user(request)
    if user:
        return RedirectResponse(url="/paciente/turnos" if user.get("tipo") == "paciente" else "/admin/", status_code=302)
    from obras_sociales import OBRAS_SOCIALES
    return templates.TemplateResponse("registro.html", {"request": request, "obras_sociales": OBRAS_SOCIALES})


@router.post("/registro")
async def registro_post(
    request: Request,
    dni: str = Form(...),
    nombre: str = Form(...),
    apellido: str = Form(...),
    email: str = Form(""),
    telefono: str = Form(""),
    fecha_nacimiento: str = Form(""),
    obra_social: str = Form(""),
    password: str = Form(...),
    confirmar_password: str = Form(...),
    db: Session = Depends(get_db)
):
    def error(msg):
        from obras_sociales import OBRAS_SOCIALES
        return templates.TemplateResponse("registro.html", {
            "request": request, "error": msg,
            "obras_sociales": OBRAS_SOCIALES,
            "form": {"dni": dni, "nombre": nombre, "apellido": apellido,
                     "email": email, "telefono": telefono,
                     "fecha_nacimiento": fecha_nacimiento, "obra_social": obra_social}
        })

    if password != confirmar_password:
        return error("Las contraseñas no coinciden.")
    if len(password) < 6:
        return error("La contraseña debe tener al menos 6 caracteres.")

    existente = db.query(Paciente).filter(Paciente.dni == dni.strip()).first()
    if existente:
        return error("Ya existe una cuenta con ese DNI. Si olvidaste tu contraseña, contactá a la clínica.")

    paciente = Paciente(
        dni=dni.strip(), nombre=nombre.strip(), apellido=apellido.strip(),
        email=email.strip(), telefono=telefono.strip(),
        fecha_nacimiento=fecha_nacimiento, obra_social=obra_social.strip(),
        password_hash=get_password_hash(password),
        primer_login=False,
        activo=True,
        aprobado=True,  # aprobación automática
    )
    db.add(paciente)
    db.commit()

    # Login automático después del registro
    token = create_access_token({
        "sub": str(paciente.id),
        "tipo": "paciente",
        "nombre": paciente.nombre,
        "apellido": paciente.apellido,
        "primer_login": False
    })
    response = RedirectResponse(url="/paciente/turnos?msg=Bienvenido/a+al+portal.&tipo=success", status_code=302)
    response.set_cookie(key="access_token", value=token, httponly=True, max_age=28800, samesite="lax")
    return response
