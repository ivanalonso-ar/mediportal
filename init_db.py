"""
Inicializa la base PostgreSQL/Supabase.

Uso:
    python init_db.py
    python init_db.py --no-catalogos
"""

from __future__ import annotations

import argparse
import secrets
from pathlib import Path

from sqlalchemy import inspect, text

from auth import get_password_hash
from database import SessionLocal, activar_clinica, engine
from horarios import DEFAULT_PROFESIONALES
from models import (
    Base,
    ConfiguracionClinica,
    Especialidad,
    ObraSocial,
    ProfesionalEspecialidad,
    UsuarioStaff,
)
from obras_sociales import DEFAULT_OBRAS_SOCIALES

ROOT = Path(__file__).resolve().parent
MIGRATIONS_DIR = ROOT / "migrations"


def run_migrations() -> None:
    if engine.dialect.name == "sqlite":
        tablas_tenant = (
            "pacientes", "usuarios_staff", "especialidades", "obras_sociales",
            "profesionales_especialidades", "turnos", "turno_logs", "resultados",
            "avisos", "notificaciones", "grupos_familiares", "solicitudes_grupo", "bonos",
        )
        tablas_existentes = set(inspect(engine).get_table_names())
        ConfiguracionClinica.__table__.create(bind=engine, checkfirst=True)
        with engine.begin() as conn:
            for tabla in tablas_tenant:
                if tabla not in tablas_existentes:
                    continue
                columnas = {row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({tabla})").all()}
                if "clinica_id" not in columnas:
                    conn.exec_driver_sql(f"ALTER TABLE {tabla} ADD COLUMN clinica_id INTEGER")

        Base.metadata.create_all(bind=engine)
        db_inicial = SessionLocal()
        try:
            if not db_inicial.query(ConfiguracionClinica).filter(ConfiguracionClinica.slug == "mediportal").first():
                db_inicial.add(ConfiguracionClinica(nombre="MediPortal", slug="mediportal", color_primario="#2563eb"))
                db_inicial.commit()
        finally:
            db_inicial.close()
        with engine.begin() as conn:
            clinica_id = conn.exec_driver_sql(
                "SELECT id FROM configuracion_clinica WHERE slug = 'mediportal'"
            ).scalar_one()
            for tabla in tablas_tenant:
                columnas = {row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({tabla})").all()}
                if "clinica_id" not in columnas:
                    conn.exec_driver_sql(f"ALTER TABLE {tabla} ADD COLUMN clinica_id INTEGER")
                conn.exec_driver_sql(f"UPDATE {tabla} SET clinica_id = ? WHERE clinica_id IS NULL", (clinica_id,))
                conn.exec_driver_sql(f"CREATE INDEX IF NOT EXISTS idx_{tabla}_clinica ON {tabla}(clinica_id)")

            for tabla, columnas, indice in (
                ("pacientes", "clinica_id, dni", "uq_paciente_clinica_dni"),
                ("usuarios_staff", "clinica_id, email", "uq_staff_clinica_email"),
                ("especialidades", "clinica_id, nombre", "uq_especialidad_clinica_nombre"),
                ("obras_sociales", "clinica_id, nombre", "uq_obra_social_clinica_nombre"),
            ):
                conn.exec_driver_sql(f"CREATE UNIQUE INDEX IF NOT EXISTS {indice} ON {tabla}({columnas})")

            conn.exec_driver_sql("DROP INDEX IF EXISTS uq_turno_profesional_activo")
            conn.exec_driver_sql("DROP INDEX IF EXISTS idx_turno_slot_profesional")
            conn.exec_driver_sql(
                "CREATE UNIQUE INDEX idx_turno_slot_profesional ON turnos(clinica_id, fecha, hora, profesional) "
                "WHERE profesional IS NOT NULL AND profesional <> '' AND estado IN ('pendiente', 'confirmado')"
            )
            turnos_cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(turnos)").all()}
            if "profesional_id" not in turnos_cols:
                conn.exec_driver_sql("ALTER TABLE turnos ADD COLUMN profesional_id INTEGER")

            resultados_cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(resultados)").all()}
            if "subido_por_id" not in resultados_cols:
                conn.exec_driver_sql("ALTER TABLE resultados ADD COLUMN subido_por_id INTEGER")
        print("OK schema SQLite local creado via SQLAlchemy")
        return

    sql_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not sql_files:
        raise RuntimeError(f"No hay migrations SQL en {MIGRATIONS_DIR}")

    with engine.begin() as conn:
        for path in sql_files:
            sql = path.read_text(encoding="utf-8")
            conn.exec_driver_sql(sql)
            print(f"OK migration: {path.name}")


def ensure_configuracion_base(
    db,
    *,
    nombre: str = "MediPortal",
    slug: str = "mediportal",
    timezone: str = "America/Argentina/Buenos_Aires",
    email: str = "",
    telefono: str = "",
    direccion: str = "",
    color_primario: str | None = None,
) -> ConfiguracionClinica:
    config = db.query(ConfiguracionClinica).filter(ConfiguracionClinica.slug == slug).first()
    if not config:
        config = ConfiguracionClinica(
            nombre=nombre,
            slug=slug,
            timezone=timezone,
            color_primario=color_primario or "#2563eb",
            email=email or None,
            telefono=telefono or None,
            direccion=direccion or None,
        )
        db.add(config)
    else:
        config.nombre = nombre
        config.timezone = timezone
        if color_primario:
            config.color_primario = color_primario
        config.email = email or config.email
        config.telefono = telefono or config.telefono
        config.direccion = direccion or config.direccion
    return config


def seed_obras_sociales(db) -> int:
    creadas = 0
    for nombre in DEFAULT_OBRAS_SOCIALES:
        if not nombre.strip():
            continue
        exists = db.query(ObraSocial).filter(ObraSocial.nombre == nombre).first()
        if not exists:
            db.add(ObraSocial(nombre=nombre.strip(), tipo="obra_social", activa=True))
            creadas += 1
    return creadas


def seed_especialidades(db) -> int:
    especialidades_creadas = 0
    for orden, (nombre_esp, profesionales) in enumerate(sorted(DEFAULT_PROFESIONALES.items()), start=1):
        especialidad = db.query(Especialidad).filter(Especialidad.nombre == nombre_esp).first()
        if not especialidad:
            especialidad = Especialidad(nombre=nombre_esp, activa=True, orden=orden)
            db.add(especialidad)
            db.flush()
            especialidades_creadas += 1
    return especialidades_creadas


def seed_especialidades_y_profesionales(db) -> tuple[int, int, int]:
    especialidades_creadas = seed_especialidades(db)
    staff_creado = 0
    relaciones_creadas = 0

    for nombre_esp, profesionales in sorted(DEFAULT_PROFESIONALES.items()):
        especialidad = db.query(Especialidad).filter(Especialidad.nombre == nombre_esp).first()
        for prof in profesionales:
            email = prof["email"].lower()
            staff = db.query(UsuarioStaff).filter(UsuarioStaff.email == email).first()
            if not staff:
                staff = UsuarioStaff(
                    nombre=prof["nombre_staff"],
                    apellido=prof["apellido_staff"],
                    email=email,
                    password_hash=get_password_hash(secrets.token_urlsafe(24)),
                    rol="profesional",
                    activo=True,
                )
                db.add(staff)
                db.flush()
                staff_creado += 1

            relacion = db.query(ProfesionalEspecialidad).filter(
                ProfesionalEspecialidad.profesional_id == staff.id,
                ProfesionalEspecialidad.especialidad_id == especialidad.id,
            ).first()
            if not relacion:
                db.add(ProfesionalEspecialidad(
                    profesional_id=staff.id,
                    especialidad_id=especialidad.id,
                    nombre_publico=prof["nombre"],
                    turno=prof["turno"],
                    activo=True,
                ))
                relaciones_creadas += 1

    return especialidades_creadas, staff_creado, relaciones_creadas


def create_admin(db, *, email: str, password: str, nombre: str = "Admin", apellido: str = "Principal") -> UsuarioStaff:
    admin = db.query(UsuarioStaff).filter(UsuarioStaff.email == email.lower()).first()
    if not admin:
        admin = UsuarioStaff(
            nombre=nombre.strip() or "Admin",
            apellido=apellido.strip() or "Principal",
            email=email.lower(),
            password_hash=get_password_hash(password),
            rol="admin",
            activo=True,
        )
        db.add(admin)
    else:
        admin.nombre = nombre.strip() or admin.nombre
        admin.apellido = apellido.strip() or admin.apellido
        admin.password_hash = get_password_hash(password)
        admin.rol = "admin"
        admin.activo = True
    return admin


def initialize_database(seed_catalogos: bool = True) -> None:
    run_migrations()

    db = SessionLocal()
    try:
        config_clinica = ensure_configuracion_base(db)
        db.flush()
        activar_clinica(db, config_clinica.id)
        if seed_catalogos:
            obras = seed_obras_sociales(db)
            especialidades, staff, relaciones = seed_especialidades_y_profesionales(db)
            print(f"OK catalogos: {obras} obras sociales, {especialidades} especialidades, {staff} profesionales, {relaciones} relaciones")
        db.commit()
        db.execute(text("select 1"))
        print("OK base inicializada")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Inicializa schema y catalogos base en Supabase/PostgreSQL.")
    parser.add_argument("--no-catalogos", action="store_true", help="Solo corre migrations y configuracion base.")
    args = parser.parse_args()
    initialize_database(seed_catalogos=not args.no_catalogos)


if __name__ == "__main__":
    main()
