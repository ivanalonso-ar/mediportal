"""
Provisiona una instancia nueva de cliente.

Requiere DATABASE_URL apuntando al PostgreSQL de Supabase.

Ejemplo:
    python setup_cliente.py --clinica "Centro Medico Norte" --slug centro-norte \
      --admin-email admin@centronorte.com --admin-password "cambiar-esta-clave"
"""

from __future__ import annotations

import argparse
import re
import sys

from database import SQLALCHEMY_DATABASE_URL, SessionLocal
from init_db import (
    create_admin,
    ensure_configuracion_base,
    run_migrations,
    seed_especialidades,
    seed_especialidades_y_profesionales,
    seed_obras_sociales,
)
from supabase_client import get_supabase_client


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "cliente"


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
    parser.add_argument("--sin-catalogos", action="store_true", help="No carga especialidades/obras sociales base.")
    parser.add_argument("--sin-profesionales-demo", action="store_true", help="Carga obras/especialidades, pero no profesionales demo.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    slug = args.slug or slugify(args.clinica)

    if len(args.admin_password) < 12:
        print("ERROR: --admin-password debe tener al menos 12 caracteres para provisioning.", file=sys.stderr)
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
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print("OK cliente inicializado")
    print(f"Clinica: {args.clinica} ({slug})")
    print(f"Admin: {args.admin_email}")
    if not args.sin_catalogos:
        print(f"Catalogos: {obras} obras sociales, {especialidades} especialidades, {staff} profesionales, {relaciones} relaciones")


if __name__ == "__main__":
    main()
