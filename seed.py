from database import SessionLocal
from models import Paciente, UsuarioStaff
from auth import get_password_hash

db = SessionLocal()

# ADMIN
if not db.query(UsuarioStaff).filter_by(email="admin@mediportal.com").first():
    db.add(UsuarioStaff(
        nombre="Admin",
        apellido="Sistema",
        email="admin@mediportal.com",
        password_hash=get_password_hash("admin123"),
        rol="admin",
        activo=True
    ))

# RECEPCION
if not db.query(UsuarioStaff).filter_by(email="recepcion@mediportal.com").first():
    db.add(UsuarioStaff(
        nombre="Recepcion",
        apellido="Principal",
        email="recepcion@mediportal.com",
        password_hash=get_password_hash("recepcion123"),
        rol="recepcion",
        activo=True
    ))

# MEDICO
if not db.query(UsuarioStaff).filter_by(email="medico@mediportal.com").first():
    db.add(UsuarioStaff(
        nombre="Juan",
        apellido="Perez",
        email="medico@mediportal.com",
        password_hash=get_password_hash("medico123"),
        rol="profesional",
        activo=True
    ))

# PACIENTES
for i in range(1, 4):

    dni = f"1000{i}"

    if not db.query(Paciente).filter_by(dni=dni).first():

        db.add(Paciente(
            dni=dni,
            nombre=f"Paciente{i}",
            apellido="Demo",
            email=f"paciente{i}@mail.com",
            password_hash=get_password_hash("123456"),
            primer_login=False,
            activo=True,
            aprobado=True
        ))

db.commit()
db.close()

print("Usuarios demo creados.")