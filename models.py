import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from database import Base


class Paciente(Base):
    __tablename__ = "pacientes"

    id = Column(Integer, primary_key=True, index=True)
    dni = Column(String(20), unique=True, nullable=False, index=True)
    nombre = Column(String(100), nullable=False)
    apellido = Column(String(100), nullable=False)
    email = Column(String(200))
    telefono = Column(String(50))
    fecha_nacimiento = Column(String(20))
    obra_social = Column(String(100))
    password_hash = Column(String(256), nullable=False)
    primer_login = Column(Boolean, default=True)
    activo = Column(Boolean, default=True)
    aprobado = Column(Boolean, default=True)  # False = registro pendiente de aprobación
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    turnos = relationship("Turno", back_populates="paciente", cascade="all, delete-orphan")
    resultados = relationship("Resultado", back_populates="paciente", cascade="all, delete-orphan")


class UsuarioStaff(Base):
    __tablename__ = "usuarios_staff"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    apellido = Column(String(100), nullable=False)
    email = Column(String(200), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    rol = Column(String(50), default="recepcion")  # admin, profesional, recepcion
    activo = Column(Boolean, default=True)
    atiende_particular = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class Turno(Base):
    __tablename__ = "turnos"

    id = Column(Integer, primary_key=True, index=True)
    paciente_id = Column(Integer, ForeignKey("pacientes.id"), nullable=False)
    fecha = Column(String(20), nullable=False)
    hora = Column(String(10), nullable=False)
    especialidad = Column(String(100), nullable=False)
    profesional = Column(String(100))
    estado = Column(String(50), default="pendiente")  # pendiente, confirmado, cancelado, completado
    tipo = Column(String(20), default="normal")       # normal, sobreturno
    tipo_consulta = Column(String(20), default="obra_social")  # obra_social, particular
    observaciones = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    created_by = Column(String(100))   # quien creó el turno

    paciente = relationship("Paciente", back_populates="turnos")
    logs = relationship("TurnoLog", back_populates="turno", cascade="all, delete-orphan")


class TurnoLog(Base):
    """Registro de cada modificación/cancelación sobre un turno."""
    __tablename__ = "turno_logs"

    id = Column(Integer, primary_key=True, index=True)
    turno_id = Column(Integer, ForeignKey("turnos.id"), nullable=False)
    accion = Column(String(50), nullable=False)   # creado, modificado, cancelado, estado_cambiado
    descripcion = Column(Text, nullable=False)     # detalle legible del cambio
    realizado_por = Column(String(100), nullable=False)  # nombre del staff
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    turno = relationship("Turno", back_populates="logs")


class Resultado(Base):
    __tablename__ = "resultados"

    id = Column(Integer, primary_key=True, index=True)
    paciente_id = Column(Integer, ForeignKey("pacientes.id"), nullable=False)
    titulo = Column(String(200), nullable=False)
    descripcion = Column(Text)
    archivo_nombre = Column(String(300))
    archivo_path = Column(String(500))
    fecha_estudio = Column(String(20))
    subido_por = Column(String(100))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    paciente = relationship("Paciente", back_populates="resultados")


class Aviso(Base):
    """Carteles/avisos configurables que se muestran en el portal."""
    __tablename__ = "avisos"

    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(String(200), nullable=False)
    contenido = Column(Text, nullable=False)
    tipo = Column(String(20), default="info")   # info, warning, importante
    activo = Column(Boolean, default=True)
    orden = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class Notificacion(Base):
    """Notificaciones in-app para pacientes."""
    __tablename__ = "notificaciones"

    id = Column(Integer, primary_key=True, index=True)
    paciente_id = Column(Integer, ForeignKey("pacientes.id"), nullable=False)
    titulo = Column(String(200), nullable=False)
    mensaje = Column(Text, nullable=False)
    tipo = Column(String(40), default="info")   # turno_confirmado, turno_cancelado, informe, turno_modificado
    leido = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    paciente = relationship("Paciente", backref="notificaciones")
