import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, ForeignKey, Text, UniqueConstraint, Index
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
    aprobado = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    turnos = relationship("Turno", back_populates="paciente", cascade="all, delete-orphan")
    resultados = relationship("Resultado", back_populates="paciente", cascade="all, delete-orphan")
    notificaciones = relationship("Notificacion", back_populates="paciente", cascade="all, delete-orphan")


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


class ConfiguracionClinica(Base):
    __tablename__ = "configuracion_clinica"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(150), nullable=False, default="MediPortal")
    slug = Column(String(80), unique=True, nullable=False, default="mediportal")
    timezone = Column(String(80), nullable=False, default="America/Argentina/Buenos_Aires")
    telefono = Column(String(50))
    email = Column(String(200))
    direccion = Column(String(250))
    sitio_web = Column(String(250))
    logo_url = Column(String(500))
    color_primario = Column(String(20), default="#0284c7")
    duracion_slot_minutos = Column(Integer, default=20)
    hora_inicio_manana = Column(String(5), default="08:00")
    hora_fin_manana = Column(String(5), default="14:00")
    hora_inicio_tarde = Column(String(5), default="14:00")
    hora_fin_tarde = Column(String(5), default="19:00")
    permite_sobreturnos = Column(Boolean, default=True)
    permite_turnos_particulares = Column(Boolean, default=True)
    requiere_aprobacion_pacientes = Column(Boolean, default=False)
    cancelacion_horas_minimas = Column(Integer, default=24)
    upload_dir_resultados = Column(String(300), default="uploads/resultados")
    activo = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class Especialidad(Base):
    __tablename__ = "especialidades"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(120), nullable=False, unique=True, index=True)
    descripcion = Column(Text)
    activa = Column(Boolean, default=True)
    orden = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class ObraSocial(Base):
    __tablename__ = "obras_sociales"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(160), nullable=False, unique=True, index=True)
    tipo = Column(String(60), default="obra_social")
    activa = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class ProfesionalEspecialidad(Base):
    __tablename__ = "profesionales_especialidades"

    id = Column(Integer, primary_key=True, index=True)
    profesional_id = Column(Integer, ForeignKey("usuarios_staff.id", ondelete="CASCADE"), nullable=False)
    especialidad_id = Column(Integer, ForeignKey("especialidades.id", ondelete="CASCADE"), nullable=False)
    nombre_publico = Column(String(160), nullable=False)
    turno = Column(String(20), nullable=False, default="manana")
    activo = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    profesional = relationship("UsuarioStaff")
    especialidad = relationship("Especialidad")

    __table_args__ = (
        UniqueConstraint("profesional_id", "especialidad_id", name="uq_profesional_especialidad"),
    )


class Turno(Base):
    __tablename__ = "turnos"

    id = Column(Integer, primary_key=True, index=True)
    paciente_id = Column(Integer, ForeignKey("pacientes.id", ondelete="CASCADE"), nullable=False)
    # Fix 4: profesional_id como FK además del nombre (nombre se mantiene para compatibilidad)
    profesional_id = Column(Integer, ForeignKey("usuarios_staff.id", ondelete="SET NULL"), nullable=True)
    fecha = Column(String(20), nullable=False)
    hora = Column(String(10), nullable=False)
    especialidad = Column(String(100), nullable=False)
    profesional = Column(String(150))   # nombre denormalizado para display rápido
    estado = Column(String(50), default="pendiente")  # pendiente, confirmado, cancelado, completado
    tipo = Column(String(20), default="normal")
    tipo_consulta = Column(String(20), default="obra_social")
    observaciones = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    created_by = Column(String(100))

    paciente = relationship("Paciente", back_populates="turnos")
    profesional_ref = relationship("UsuarioStaff", foreign_keys=[profesional_id])
    logs = relationship("TurnoLog", back_populates="turno", cascade="all, delete-orphan")

    # Fix 9: unique constraint para evitar doble turno mismo paciente/fecha/hora/especialidad
    __table_args__ = (
        UniqueConstraint("paciente_id", "fecha", "hora", "especialidad", name="uq_turno_paciente"),
    )


class TurnoLog(Base):
    __tablename__ = "turno_logs"

    id = Column(Integer, primary_key=True, index=True)
    turno_id = Column(Integer, ForeignKey("turnos.id", ondelete="CASCADE"), nullable=False)
    accion = Column(String(50), nullable=False)
    descripcion = Column(Text, nullable=False)
    realizado_por = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    turno = relationship("Turno", back_populates="logs")


class Resultado(Base):
    __tablename__ = "resultados"

    id = Column(Integer, primary_key=True, index=True)
    paciente_id = Column(Integer, ForeignKey("pacientes.id", ondelete="CASCADE"), nullable=False)
    # Fix 5: staff_id como FK además del nombre
    subido_por_id = Column(Integer, ForeignKey("usuarios_staff.id", ondelete="SET NULL"), nullable=True)
    titulo = Column(String(200), nullable=False)
    descripcion = Column(Text)
    archivo_nombre = Column(String(300))
    archivo_path = Column(String(500))
    fecha_estudio = Column(String(20))
    subido_por = Column(String(100))  # nombre denormalizado para display
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    paciente = relationship("Paciente", back_populates="resultados")
    subido_por_ref = relationship("UsuarioStaff", foreign_keys=[subido_por_id])


class Aviso(Base):
    __tablename__ = "avisos"

    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(String(200), nullable=False)
    contenido = Column(Text, nullable=False)
    tipo = Column(String(20), default="info")
    activo = Column(Boolean, default=True)
    orden = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class Notificacion(Base):
    __tablename__ = "notificaciones"

    id = Column(Integer, primary_key=True, index=True)
    paciente_id = Column(Integer, ForeignKey("pacientes.id", ondelete="CASCADE"), nullable=False)
    titulo = Column(String(200), nullable=False)
    mensaje = Column(Text, nullable=False)
    tipo = Column(String(40), default="info")
    leido = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Fix 7: cascade correcto, relationship en Paciente
    paciente = relationship("Paciente", back_populates="notificaciones")


class GrupoFamiliar(Base):
    __tablename__ = "grupos_familiares"

    id = Column(Integer, primary_key=True, index=True)
    titular_id = Column(Integer, ForeignKey("pacientes.id", ondelete="CASCADE"), nullable=False)
    miembro_id = Column(Integer, ForeignKey("pacientes.id", ondelete="CASCADE"), nullable=False)
    parentesco = Column(String(50))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    titular = relationship("Paciente", foreign_keys=[titular_id])
    miembro = relationship("Paciente", foreign_keys=[miembro_id])

    __table_args__ = (
        UniqueConstraint("titular_id", "miembro_id", name="uq_grupo_familiar"),
        # Fix 8: impedir ciclos — se maneja también a nivel de lógica en el router
    )


class SolicitudGrupo(Base):
    __tablename__ = "solicitudes_grupo"

    id = Column(Integer, primary_key=True, index=True)
    solicitante_id = Column(Integer, ForeignKey("pacientes.id", ondelete="CASCADE"), nullable=False)
    destinatario_id = Column(Integer, ForeignKey("pacientes.id", ondelete="CASCADE"), nullable=False)
    parentesco = Column(String(50))
    estado = Column(String(20), default="pendiente")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    solicitante = relationship("Paciente", foreign_keys=[solicitante_id])
    destinatario = relationship("Paciente", foreign_keys=[destinatario_id])


class Bono(Base):
    __tablename__ = "bonos"

    id = Column(Integer, primary_key=True, index=True)
    paciente_id = Column(Integer, ForeignKey("pacientes.id", ondelete="CASCADE"), nullable=False)
    especialidad = Column(String(100), nullable=False)
    fecha = Column(String(20), nullable=False)
    hora = Column(String(10), nullable=False)
    emitido_por = Column(String(150), nullable=False)
    observaciones = Column(Text)
    estado = Column(String(20), default="activo")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    paciente = relationship("Paciente")

    # Fix 11: índice para buscar por fecha+especialidad rápido
    __table_args__ = (
        Index("idx_bonos_fecha_esp", "fecha", "especialidad"),
    )
