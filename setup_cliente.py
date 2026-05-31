"""
Provisiona una instancia nueva de cliente.

Requiere DATABASE_URL apuntando al PostgreSQL de Supabase.

Ejemplo:
    python setup_cliente.py --clinica "Centro Medico Norte" --slug centro-norte \
      --admin-email admin@centronorte.com --admin-password "cambiar-esta-clave"

    python setup_cliente.py --clinica "Centro Medico Norte" --slug centro-norte \
      --admin-email admin@centronorte.com --admin-password "cambiar-esta-clave" \
      --staff-email recepcion@centronorte.com --staff-password "otra-clave-segura" \
      --paciente-dni 30111222 --paciente-password "clave-paciente"
"""

from __future__ import annotations

import argparse
import re
import sys

from auth import get_password_hash
from database import SQLALCHEMY_DATABASE_URL, SessionLocal
from init_db import (
    create_admin,
    ensure_configuracion_base,
    run_migrations,
    seed_especialidades,
    seed_especialidades_y_profesionales,
    seed_obras_sociales,
)
from models import Paciente, UsuarioStaff
from supabase_client import get_supabase_client


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "cliente"


def solo_numeros(value: str) -> bool:
    return bool(re.fullmatch(r"\d+", value.strip()))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Crea schema, config base, catalogos y admin para un cliente.")
    parser.add_argument("--clinica", required=True, help="Nombre visible de la clinica.")
    parser.add_argument("--slug", default="", help="Identificador corto del cliente. Default: derivado de --clinica.")
    parser.add_argument("--timezone", default="America/Argentina/Buenos_Aires")
    parser.add_argument("--email", default="", help="Email publico de la clinica.")
    parser.add_argument("--telefono", default="", help="Telefono publico de la clinica.")
    parser.add_argument("--direccion", default="", help="Direccion publica de la clinica.")
    parser.add_argument("--admin-email", required=True)
    parser.add_argument("--admin-password", required=True)
    parser.add_argument("--admin-nombre", default="Admin")
    parser.add_argument("--admin-apellido", default="Principal")
    parser.add_argument("--staff-email", default="", help="Email de un staff adicional opcional.")
    parser.add_argument("--staff-password", default="", help="Password del staff adicional opcional.")
    parser.add_argument("--staff-nombre", default="Recepcion")
    parser.add_argument("--staff-apellido", default="Principal")
    parser.add_argument("--staff-rol", default="recepcion", choices=["admin", "recepcion", "profesional"])
    parser.add_argument("--paciente-dni", default="", help="DNI de un paciente inicial opcional.")
    parser.add_argument("--paciente-password", default="", help="Password del paciente inicial opcional.")
    parser.add_argument("--paciente-nombre", default="Paciente")
    parser.add_argument("--paciente-apellido", default="Inicial")
    parser.add_argument("--paciente-email", default="")
    parser.add_argument("--paciente-telefono", default="")
    parser.add_argument("--paciente-obra-social", default="")
    parser.add_argument("--sin-catalogos", action="store_true", help="No carga especialidades/obras sociales base.")
    parser.add_argument("--sin-profesionales-demo", action="store_true", help="Carga obras/especialidades, pero no profesionales demo.")
    return parser.parse_args()


def create_staff_user(db, *, email: str, password: str, nombre: str, apellido: str, rol: str) -> UsuarioStaff:
    staff = db.query(UsuarioStaff).filter(UsuarioStaff.email == email.lower()).first()
    if not staff:
        staff = UsuarioStaff(
            nombre=nombre.strip() or "Staff",
            apellido=apellido.strip() or "Inicial",
            email=email.lower(),
            password_hash=get_password_hash(password),
            rol=rol,
            activo=True,
        )
        db.add(staff)
    else:
        staff.nombre = nombre.strip() or staff.nombre
        staff.apellido = apellido.strip() or staff.apellido
        staff.password_hash = get_password_hash(password)
        staff.rol = rol
        staff.activo = True
    return staff


def create_paciente_user(
    db,
    *,
    dni: str,
    password: str,
    nombre: str,
    apellido: str,
    email: str = "",
    telefono: str = "",
    obra_social: str = "",
) -> Paciente:
    paciente = db.query(Paciente).filter(Paciente.dni == dni.strip()).first()
    if not paciente:
        paciente = Paciente(
            dni=dni.strip(),
            nombre=nombre.strip() or "Paciente",
            apellido=apellido.strip() or "Inicial",
            email=email.strip(),
            telefono=telefono.strip(),
            obra_social=obra_social.strip(),
            password_hash=get_password_hash(password),
            primer_login=True,
            activo=True,
            aprobado=True,
        )
        db.add(paciente)
    else:
        paciente.nombre = nombre.strip() or paciente.nombre
        paciente.apellido = apellido.strip() or paciente.apellido
        paciente.email = email.strip() or paciente.email
        paciente.telefono = telefono.strip() or paciente.telefono
        paciente.obra_social = obra_social.strip() or paciente.obra_social
        paciente.password_hash = get_password_hash(password)
        paciente.primer_login = True
        paciente.activo = True
        paciente.aprobado = True
    return paciente


def main() -> None:
    args = parse_args()
    slug = args.slug or slugify(args.clinica)

    if len(args.admin_password) < 12:
        print("ERROR: --admin-password debe tener al menos 12 caracteres para provisioning.", file=sys.stderr)
        raise SystemExit(2)
    if args.staff_email and len(args.staff_password) < 12:
        print("ERROR: --staff-password debe tener al menos 12 caracteres.", file=sys.stderr)
        raise SystemExit(2)
    if args.paciente_dni and len(args.paciente_password) < 8:
        print("ERROR: --paciente-password debe tener al menos 8 caracteres.", file=sys.stderr)
        raise SystemExit(2)
    if args.paciente_dni and not solo_numeros(args.paciente_dni):
        print("ERROR: --paciente-dni solo puede contener numeros.", file=sys.stderr)
        raise SystemExit(2)
    if args.paciente_telefono and not solo_numeros(args.paciente_telefono):
        print("ERROR: --paciente-telefono solo puede contener numeros.", file=sys.stderr)
        raise SystemExit(2)
    if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
        print("ERROR: setup_cliente.py requiere DATABASE_URL de Supabase/PostgreSQL, no SQLite.", file=sys.stderr)
        raise SystemExit(2)

    supabase = get_supabase_client()
    if supabase:
        print("OK Supabase client configurado")
    else:
        print("INFO: SUPABASE_URL/SUPABASE_KEY no configurados; se usara solo PostgreSQL via DATABASE_URL")

    run_migrations()

    db = SessionLocal()
    try:
        ensure_configuracion_base(
            db,
            nombre=args.clinica,
            slug=slug,
            timezone=args.timezone,
            email=args.email,
            telefono=args.telefono,
            direccion=args.direccion,
        )

        obras = especialidades = staff = relaciones = 0
        if not args.sin_catalogos:
            obras = seed_obras_sociales(db)
            if not args.sin_profesionales_demo:
                especialidades, staff, relaciones = seed_especialidades_y_profesionales(db)
            else:
                especialidades = seed_especialidades(db)

        create_admin(
            db,
            email=args.admin_email,
            password=args.admin_password,
            nombre=args.admin_nombre,
            apellido=args.admin_apellido,
        )

        staff_extra = None
        if args.staff_email:
            staff_extra = create_staff_user(
                db,
                email=args.staff_email,
                password=args.staff_password,
                nombre=args.staff_nombre,
                apellido=args.staff_apellido,
                rol=args.staff_rol,
            )

        paciente_inicial = None
        if args.paciente_dni:
            paciente_inicial = create_paciente_user(
                db,
                dni=args.paciente_dni,
                password=args.paciente_password,
                nombre=args.paciente_nombre,
                apellido=args.paciente_apellido,
                email=args.paciente_email,
                telefono=args.paciente_telefono,
                obra_social=args.paciente_obra_social,
            )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print("OK cliente inicializado")
    print(f"Clinica: {args.clinica} ({slug})")
    print(f"Admin: {args.admin_email}")
    if args.staff_email:
        print(f"Staff adicional: {args.staff_email} ({args.staff_rol})")
    if args.paciente_dni:
        print(f"Paciente inicial: {args.paciente_dni}")
    if not args.sin_catalogos:
        print(f"Catalogos: {obras} obras sociales, {especialidades} especialidades, {staff} profesionales, {relaciones} relaciones")


if __name__ == "__main__":
    main()
