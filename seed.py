from database import SessionLocal, engine
from models import Base, UsuarioStaff, Paciente
from auth import get_password_hash

# Crear tablas
Base.metadata.create_all(bind=engine)

db = SessionLocal()

try:

    # =========================
    # ADMIN
    # =========================
    admin = db.query(UsuarioStaff).filter_by(
        email="admin@mediportal.com"
    ).first()

    if not admin:

        admin = UsuarioStaff(
            nombre="Admin",
            apellido="Sistema",
            email="admin@mediportal.com",
            password_hash=get_password_hash("admin123"),
            rol="admin",
            activo=True
        )

        db.add(admin)

    # =========================
    # RECEPCIONISTA
    # =========================
    recep = db.query(UsuarioStaff).filter_by(
        email="recepcion@mediportal.com"
    ).first()

    if not recep:

        recep = UsuarioStaff(
            nombre="Lucia",
            apellido="Recepcion",
            email="recepcion@mediportal.com",
            password_hash=get_password_hash("recepcion123"),
            rol="recepcionista",
            activo=True
        )

        db.add(recep)

    # =========================
    # MEDICO
    # =========================
    medico = db.query(UsuarioStaff).filter_by(
        email="medico@mediportal.com"
    ).first()

    if not medico:

        medico = UsuarioStaff(
            nombre="Juan",
            apellido="Perez",
            email="medico@mediportal.com",
            password_hash=get_password_hash("medico123"),
            rol="medico",
            activo=True
        )

        db.add(medico)

    # =========================
    # PACIENTES
    # =========================
    pacientes = [
        {
            "dni": "10001",
            "nombre": "Carlos",
            "apellido": "Lopez",
            "email": "paciente1@mail.com"
        },
        {
            "dni": "10002",
            "nombre": "Ana",
            "apellido": "Martinez",
            "email": "paciente2@mail.com"
        },
        {
            "dni": "10003",
            "nombre": "Pedro",
            "apellido": "Gomez",
            "email": "paciente3@mail.com"
        }
    ]

    for p in pacientes:

        existe = db.query(Paciente).filter_by(
            dni=p["dni"]
        ).first()

        if not existe:

            paciente = Paciente(
                dni=p["dni"],
                nombre=p["nombre"],
                apellido=p["apellido"],
                email=p["email"],
                password_hash=get_password_hash("123456"),
                primer_login=False,
                activo=True,
                aprobado=True
            )

            db.add(paciente)

    db.commit()

    print("===================================")
    print("USUARIOS DEMO CREADOS")
    print("===================================")
    print("")
    print("ADMIN")
    print("admin@mediportal.com")
    print("admin123")
    print("")
    print("RECEPCIONISTA")
    print("recepcion@mediportal.com")
    print("recepcion123")
    print("")
    print("MEDICO")
    print("medico@mediportal.com")
    print("medico123")
    print("")
    print("PACIENTES")
    print("10001 / 123456")
    print("10002 / 123456")
    print("10003 / 123456")
    print("===================================")

except Exception as e:

    db.rollback()

    print("ERROR:")
    print(e)

finally:

    db.close()