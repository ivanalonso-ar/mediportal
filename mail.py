"""
Servicio de notificaciones por email.
Usa smtplib puro, sin dependencias externas adicionales.
Si MAIL_ENABLED=false en .env, las funciones no hacen nada (modo silencioso).
"""
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from config import settings

logger = logging.getLogger(__name__)


def _send(to_email: str, subject: str, html_body: str) -> bool:
    """Envía un email HTML. Retorna True si tuvo éxito."""
    if not settings.MAIL_ENABLED:
        logger.info(f"[MAIL disabled] Para: {to_email} | Asunto: {subject}")
        return False

    if not to_email or "@" not in to_email:
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{settings.MAIL_FROM_NAME} <{settings.MAIL_FROM}>"
        msg["To"] = to_email

        msg.attach(MIMEText(html_body, "html", "utf-8"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.MAIL_FROM, to_email, msg.as_string())

        logger.info(f"[MAIL ok] Para: {to_email} | Asunto: {subject}")
        return True

    except Exception as e:
        logger.error(f"[MAIL error] Para: {to_email} | {e}")
        return False


def _base_template(titulo: str, contenido: str) -> str:
    """Template HTML base para todos los emails."""
    return f"""
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{titulo}</title>
</head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:32px 16px;">
    <tr><td align="center">
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;">

        <!-- Header -->
        <tr><td style="background:#256a65;border-radius:12px 12px 0 0;padding:24px 32px;">
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
              <td>
                <span style="color:#fff;font-size:18px;font-weight:600;">
                  ❤ {settings.APP_NAME}
                </span>
              </td>
            </tr>
          </table>
        </td></tr>

        <!-- Body -->
        <tr><td style="background:#ffffff;padding:32px;border-left:1px solid #e2e8f0;border-right:1px solid #e2e8f0;">
          {contenido}
        </td></tr>

        <!-- Footer -->
        <tr><td style="background:#f8fafc;border:1px solid #e2e8f0;border-top:none;border-radius:0 0 12px 12px;padding:16px 32px;text-align:center;">
          <p style="color:#94a3b8;font-size:12px;margin:0;">
            Este es un mensaje automático de {settings.APP_NAME}.<br>
            Por favor no respondas este email.
          </p>
        </td></tr>

      </table>
    </td></tr>
  </table>
</body>
</html>
"""


# ─── Emails específicos ───────────────────────────────────────────────────────

def mail_bienvenida(to_email: str, nombre: str, dni: str, password_temp: str) -> bool:
    """Enviado cuando el admin crea un paciente nuevo."""
    contenido = f"""
    <h2 style="color:#1e293b;font-size:22px;margin:0 0 8px;">Bienvenido/a, {nombre}</h2>
    <p style="color:#64748b;font-size:15px;line-height:1.6;margin:0 0 24px;">
      Tu cuenta en <strong>{settings.APP_NAME}</strong> fue creada exitosamente.
      Podés acceder con las siguientes credenciales:
    </p>
    <table width="100%" cellpadding="0" cellspacing="0" style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:20px;margin-bottom:24px;">
      <tr>
        <td style="padding:6px 0;">
          <span style="color:#64748b;font-size:13px;">DNI</span><br>
          <strong style="color:#1e293b;font-size:16px;font-family:monospace;">{dni}</strong>
        </td>
      </tr>
      <tr>
        <td style="padding:6px 0;border-top:1px solid #e2e8f0;">
          <span style="color:#64748b;font-size:13px;">Contraseña temporal</span><br>
          <strong style="color:#1e293b;font-size:16px;font-family:monospace;">{password_temp}</strong>
        </td>
      </tr>
    </table>
    <p style="color:#64748b;font-size:14px;margin:0 0 24px;">
      Al ingresar por primera vez, el sistema te va a pedir que establezcas una contraseña propia.
    </p>
    <a href="{settings.APP_URL}/login"
      style="display:inline-block;background:#256a65;color:#fff;font-size:14px;font-weight:600;padding:12px 24px;border-radius:8px;text-decoration:none;">
      Ingresar al portal
    </a>
    """
    return _send(to_email, f"Bienvenido/a a {settings.APP_NAME}", _base_template("Bienvenida", contenido))


def mail_turno_confirmado(to_email: str, nombre: str, especialidad: str, fecha: str, hora: str, profesional: str = "") -> bool:
    """Enviado cuando se confirma o crea un turno."""
    prof_line = f"<strong>Profesional:</strong> {profesional}" if profesional else ""
    contenido = f"""
    <h2 style="color:#1e293b;font-size:22px;margin:0 0 8px;">Turno confirmado</h2>
    <p style="color:#64748b;font-size:15px;margin:0 0 24px;">
      Hola <strong>{nombre}</strong>, tu turno fue confirmado con los siguientes datos:
    </p>
    <table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f9f8;border:1px solid #99d9d4;border-radius:8px;padding:20px;margin-bottom:24px;">
      <tr><td style="padding:6px 0;color:#1e293b;font-size:15px;">
        📅 <strong>{fecha}</strong> a las <strong>{hora}</strong>
      </td></tr>
      <tr><td style="padding:6px 0;border-top:1px solid #ccece9;color:#1e293b;font-size:15px;">
        🩺 <strong>Especialidad:</strong> {especialidad}
      </td></tr>
      {"<tr><td style='padding:6px 0;border-top:1px solid #ccece9;color:#1e293b;font-size:15px;'>👨‍⚕️ " + prof_line + "</td></tr>" if prof_line else ""}
    </table>
    <p style="color:#64748b;font-size:14px;margin:0 0 24px;">
      Si necesitás cancelar tu turno, podés hacerlo desde el portal hasta 24 horas antes.
    </p>
    <a href="{settings.APP_URL}/paciente/turnos"
      style="display:inline-block;background:#256a65;color:#fff;font-size:14px;font-weight:600;padding:12px 24px;border-radius:8px;text-decoration:none;">
      Ver mis turnos
    </a>
    """
    return _send(to_email, f"Turno confirmado — {especialidad}", _base_template("Turno confirmado", contenido))


def mail_turno_cancelado(to_email: str, nombre: str, especialidad: str, fecha: str, hora: str) -> bool:
    """Enviado cuando se cancela un turno."""
    contenido = f"""
    <h2 style="color:#1e293b;font-size:22px;margin:0 0 8px;">Turno cancelado</h2>
    <p style="color:#64748b;font-size:15px;margin:0 0 24px;">
      Hola <strong>{nombre}</strong>, te informamos que el siguiente turno fue cancelado:
    </p>
    <table width="100%" cellpadding="0" cellspacing="0" style="background:#fef2f2;border:1px solid #fecaca;border-radius:8px;padding:20px;margin-bottom:24px;">
      <tr><td style="padding:6px 0;color:#1e293b;font-size:15px;">
        📅 <strong>{fecha}</strong> a las <strong>{hora}</strong>
      </td></tr>
      <tr><td style="padding:6px 0;border-top:1px solid #fecaca;color:#1e293b;font-size:15px;">
        🩺 <strong>{especialidad}</strong>
      </td></tr>
    </table>
    <p style="color:#64748b;font-size:14px;margin:0 0 24px;">
      Si necesitás un nuevo turno, podés solicitarlo desde el portal.
    </p>
    <a href="{settings.APP_URL}/paciente/turnos"
      style="display:inline-block;background:#256a65;color:#fff;font-size:14px;font-weight:600;padding:12px 24px;border-radius:8px;text-decoration:none;">
      Solicitar nuevo turno
    </a>
    """
    return _send(to_email, f"Turno cancelado — {especialidad}", _base_template("Turno cancelado", contenido))


def mail_resultado_disponible(to_email: str, nombre: str, titulo: str, fecha_estudio: str = "") -> bool:
    """Enviado cuando el staff sube un resultado al paciente."""
    fecha_line = f"<br><span style='color:#64748b;font-size:13px;'>Fecha del estudio: {fecha_estudio}</span>" if fecha_estudio else ""
    contenido = f"""
    <h2 style="color:#1e293b;font-size:22px;margin:0 0 8px;">Nuevo resultado disponible</h2>
    <p style="color:#64748b;font-size:15px;margin:0 0 24px;">
      Hola <strong>{nombre}</strong>, tenés un nuevo resultado médico disponible en tu portal:
    </p>
    <table width="100%" cellpadding="0" cellspacing="0" style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:20px;margin-bottom:24px;">
      <tr><td style="padding:6px 0;color:#1e293b;font-size:16px;font-weight:600;">
        📄 {titulo}{fecha_line}
      </td></tr>
    </table>
    <p style="color:#64748b;font-size:14px;margin:0 0 24px;">
      Podés verlo y descargarlo ingresando a tu portal.
    </p>
    <a href="{settings.APP_URL}/paciente/resultados"
      style="display:inline-block;background:#256a65;color:#fff;font-size:14px;font-weight:600;padding:12px 24px;border-radius:8px;text-decoration:none;">
      Ver mis resultados
    </a>
    """
    return _send(to_email, f"Nuevo resultado: {titulo}", _base_template("Resultado disponible", contenido))


def mail_cambio_password(to_email: str, nombre: str) -> bool:
    """Confirmación de cambio de contraseña exitoso."""
    contenido = f"""
    <h2 style="color:#1e293b;font-size:22px;margin:0 0 8px;">Contraseña actualizada</h2>
    <p style="color:#64748b;font-size:15px;margin:0 0 24px;">
      Hola <strong>{nombre}</strong>, tu contraseña fue cambiada exitosamente.
    </p>
    <p style="color:#64748b;font-size:14px;margin:0 0 24px;">
      Si no realizaste este cambio, contactate con el centro médico de inmediato.
    </p>
    <a href="{settings.APP_URL}/login"
      style="display:inline-block;background:#256a65;color:#fff;font-size:14px;font-weight:600;padding:12px 24px;border-radius:8px;text-decoration:none;">
      Ir al portal
    </a>
    """
    return _send(to_email, "Contraseña actualizada", _base_template("Contraseña actualizada", contenido))


def mail_registro_pendiente_staff(to_email: str, nombre_paciente: str, dni: str) -> bool:
    """Avisa al staff que hay un registro pendiente de aprobación."""
    contenido = f"""
    <h2 style="color:#1e293b;font-size:22px;margin:0 0 8px;">Nuevo registro pendiente</h2>
    <p style="color:#64748b;font-size:15px;margin:0 0 24px;">
      Un paciente completó el formulario de registro y está esperando aprobación:
    </p>
    <table width="100%" cellpadding="0" cellspacing="0" style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:20px;margin-bottom:24px;">
      <tr><td style="padding:6px 0;color:#1e293b;font-size:15px;">
        <strong>Nombre:</strong> {nombre_paciente}
      </td></tr>
      <tr><td style="padding:6px 0;border-top:1px solid #e2e8f0;color:#1e293b;font-size:15px;">
        <strong>DNI:</strong> {dni}
      </td></tr>
    </table>
    <a href="{settings.APP_URL}/admin/pacientes?filtro=pendientes"
      style="display:inline-block;background:#256a65;color:#fff;font-size:14px;font-weight:600;padding:12px 24px;border-radius:8px;text-decoration:none;">
      Revisar registro
    </a>
    """
    return _send(to_email, "Nuevo registro pendiente de aprobación", _base_template("Registro pendiente", contenido))


def mail_registro_aprobado(to_email: str, nombre: str) -> bool:
    """Enviado al paciente cuando su registro es aprobado."""
    contenido = f"""
    <h2 style="color:#1e293b;font-size:22px;margin:0 0 8px;">¡Tu cuenta fue aprobada!</h2>
    <p style="color:#64748b;font-size:15px;margin:0 0 24px;">
      Hola <strong>{nombre}</strong>, tu solicitud de registro fue aprobada.
      Ya podés ingresar al portal con el DNI y la contraseña que elegiste al registrarte.
    </p>
    <a href="{settings.APP_URL}/login"
      style="display:inline-block;background:#256a65;color:#fff;font-size:14px;font-weight:600;padding:12px 24px;border-radius:8px;text-decoration:none;">
      Ingresar al portal
    </a>
    """
    return _send(to_email, "Tu cuenta fue aprobada", _base_template("Cuenta aprobada", contenido))


def mail_registro_rechazado(to_email: str, nombre: str, motivo: str = "") -> bool:
    """Enviado al paciente cuando su registro es rechazado."""
    motivo_line = f"<p style='color:#64748b;font-size:14px;margin:0 0 16px;'><strong>Motivo:</strong> {motivo}</p>" if motivo else ""
    contenido = f"""
    <h2 style="color:#1e293b;font-size:22px;margin:0 0 8px;">Registro no aprobado</h2>
    <p style="color:#64748b;font-size:15px;margin:0 0 16px;">
      Hola <strong>{nombre}</strong>, lamentablemente tu solicitud de registro no pudo ser aprobada.
    </p>
    {motivo_line}
    <p style="color:#64748b;font-size:14px;margin:0 0 24px;">
      Si creés que es un error, comunicate con la clínica directamente.
    </p>
    """
    return _send(to_email, "Tu solicitud de registro no fue aprobada", _base_template("Registro no aprobado", contenido))
