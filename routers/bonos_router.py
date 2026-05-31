from templates_config import templates
import io
import datetime
import logging
import re
from urllib.parse import urlencode
from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

from database import get_db
from models import Bono, Paciente, Especialidad
from auth import get_current_user
from horarios import catalogo_horarios

router = APIRouter(prefix="/bonos")
logger = logging.getLogger("mediportal.bonos")
RE_HORA = re.compile(r"^\d{2}:\d{2}$")


def require_recepcion(request: Request):
    user = get_current_user(request)
    if not user or user.get("tipo") != "staff":
        return None
    if user.get("rol") not in ("recepcion", "admin"):
        return None
    return user


def staff_nombre(user: dict) -> str:
    return f"{user.get('nombre', '')} {user.get('apellido', '')}".strip()


def bonos_redirect(
    *,
    especialidad: str = "",
    msg: str = "",
    tipo: str = "",
    status_code: int = 302,
):
    params = {}
    if especialidad:
        params["especialidad"] = especialidad
    if msg:
        params["msg"] = msg
    if tipo:
        params["tipo"] = tipo
    query = urlencode(params)
    url = f"/bonos/?{query}" if query else "/bonos/"
    return RedirectResponse(url=url, status_code=status_code)


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

    especialidad = especialidad.strip()
    hora = hora.strip()
    observaciones = observaciones.strip()

    paciente = db.query(Paciente).filter(
        Paciente.id == paciente_id,
        Paciente.activo == True,
    ).first()
    if not paciente:
        return bonos_redirect(msg="Paciente no encontrado o inactivo.", tipo="error")

    catalogo = catalogo_horarios(db)
    if especialidad not in catalogo["especialidades"]:
        return bonos_redirect(msg="Especialidad invalida.", tipo="error")

    if not RE_HORA.match(hora):
        return bonos_redirect(especialidad=especialidad, msg="Hora invalida.", tipo="error")

    hoy = datetime.date.today().strftime("%Y-%m-%d")
    bono = Bono(
        paciente_id=paciente_id,
        especialidad=especialidad,
        fecha=hoy,
        hora=hora,
        emitido_por=staff_nombre(user),
        observaciones=observaciones,
        estado="activo"
    )
    try:
        db.add(bono)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Error de base de datos al emitir bono.")
        return bonos_redirect(especialidad=especialidad, msg="No se pudo emitir el bono.", tipo="error")

    return bonos_redirect(especialidad=especialidad, msg="Bono emitido correctamente.", tipo="success")


@router.post("/atender/{bono_id}")
async def marcar_atendido(request: Request, bono_id: int, db: Session = Depends(get_db)):
    user = require_recepcion(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    bono = db.query(Bono).filter(Bono.id == bono_id).first()
    especialidad = bono.especialidad if bono else ""
    if bono and bono.estado == "activo":
        try:
            bono.estado = "atendido"
            db.commit()
        except SQLAlchemyError:
            db.rollback()
            logger.exception("Error de base de datos al marcar bono como atendido.")
            return bonos_redirect(especialidad=especialidad, msg="No se pudo actualizar el bono.", tipo="error")

    return bonos_redirect(especialidad=especialidad, msg="Bono marcado como atendido.", tipo="success")


@router.post("/cancelar/{bono_id}")
async def cancelar_bono(request: Request, bono_id: int, db: Session = Depends(get_db)):
    user = require_recepcion(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    bono = db.query(Bono).filter(Bono.id == bono_id).first()
    especialidad = bono.especialidad if bono else ""
    if bono and bono.estado == "activo":
        try:
            bono.estado = "cancelado"
            db.commit()
        except SQLAlchemyError:
            db.rollback()
            logger.exception("Error de base de datos al cancelar bono.")
            return bonos_redirect(especialidad=especialidad, msg="No se pudo cancelar el bono.", tipo="error")

    return bonos_redirect(especialidad=especialidad, msg="Bono cancelado.", tipo="success")


@router.get("/imprimir/{bono_id}")
async def imprimir_bono(request: Request, bono_id: int, db: Session = Depends(get_db)):
    user = require_recepcion(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    bono = db.query(Bono).filter(Bono.id == bono_id).first()
    if not bono:
        return RedirectResponse(url="/bonos/?msg=Bono+no+encontrado.&tipo=error", status_code=302)

    pac = bono.paciente
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm
    )

    styles = getSampleStyleSheet()
    titulo_style = ParagraphStyle("titulo", parent=styles["Normal"],
        fontSize=18, fontName="Helvetica-Bold", alignment=TA_CENTER, spaceAfter=4)
    subtitulo_style = ParagraphStyle("subtitulo", parent=styles["Normal"],
        fontSize=11, fontName="Helvetica", alignment=TA_CENTER, textColor=colors.HexColor("#555555"), spaceAfter=16)
    label_style = ParagraphStyle("label", parent=styles["Normal"],
        fontSize=8, fontName="Helvetica-Bold", textColor=colors.HexColor("#888888"), spaceBefore=0, spaceAfter=2)
    valor_style = ParagraphStyle("valor", parent=styles["Normal"],
        fontSize=12, fontName="Helvetica", spaceAfter=10)
    esp_style = ParagraphStyle("esp", parent=styles["Normal"],
        fontSize=20, fontName="Helvetica-Bold", alignment=TA_CENTER,
        textColor=colors.HexColor("#1a56db"), spaceBefore=8, spaceAfter=8)
    footer_style = ParagraphStyle("footer", parent=styles["Normal"],
        fontSize=8, fontName="Helvetica", alignment=TA_CENTER,
        textColor=colors.HexColor("#aaaaaa"))

    story = []

    # Encabezado
    story.append(Paragraph("MediPortal", titulo_style))
    story.append(Paragraph("Bono de Atención", subtitulo_style))
    story.append(Paragraph(f"N° {bono.id:04d}", ParagraphStyle("num", parent=styles["Normal"],
        fontSize=10, fontName="Helvetica", alignment=TA_CENTER,
        textColor=colors.HexColor("#888888"), spaceAfter=8)))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1a56db"), spaceAfter=16))

    # Especialidad destacada
    story.append(Paragraph("ESPECIALIDAD", label_style))
    story.append(Paragraph(bono.especialidad.upper(), esp_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#dddddd"), spaceAfter=14))

    # Datos del paciente
    story.append(Paragraph("PACIENTE", label_style))
    story.append(Paragraph(f"{pac.apellido.upper()}, {pac.nombre}", valor_style))

    story.append(Paragraph("DNI", label_style))
    story.append(Paragraph(pac.dni, valor_style))

    if pac.obra_social:
        story.append(Paragraph("OBRA SOCIAL / PREPAGA", label_style))
        story.append(Paragraph(pac.obra_social, valor_style))

    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#dddddd"), spaceBefore=4, spaceAfter=12))

    # Datos del bono
    data = [
        ["FECHA", "HORA ESTIMADA"],
        [bono.fecha, bono.hora],
    ]
    t = Table(data, colWidths=[8*cm, 8*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#f1f5f9")),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,0), 8),
        ("TEXTCOLOR", (0,0), (-1,0), colors.HexColor("#888888")),
        ("FONTNAME", (0,1), (-1,1), "Helvetica-Bold"),
        ("FONTSIZE", (0,1), (-1,1), 14),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0,1), (-1,1), [colors.white]),
        ("BOX", (0,0), (-1,-1), 0.5, colors.HexColor("#dddddd")),
        ("INNERGRID", (0,0), (-1,-1), 0.5, colors.HexColor("#dddddd")),
        ("TOPPADDING", (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
    ]))
    story.append(t)
    story.append(Spacer(1, 12))

    if bono.observaciones:
        story.append(Paragraph("OBSERVACIONES", label_style))
        obs_style = ParagraphStyle("obs", parent=styles["Normal"],
            fontSize=10, fontName="Helvetica-Oblique",
            textColor=colors.HexColor("#444444"), spaceAfter=12)
        story.append(Paragraph(bono.observaciones, obs_style))

    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#dddddd"), spaceAfter=8))

    story.append(Paragraph("EMITIDO POR", label_style))
    story.append(Paragraph(bono.emitido_por, valor_style))

    story.append(Spacer(1, 20))
    ts = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    story.append(Paragraph(f"Documento generado el {ts} · MediPortal", footer_style))

    doc.build(story)
    buffer.seek(0)

    filename = f"bono_{bono.id}_{pac.apellido.lower()}.pdf"
    return Response(
        content=buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename=\"{filename}\""}
    )
