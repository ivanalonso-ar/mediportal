from database import SessionLocal, engine
from models import Base, UsuarioStaff, Paciente
from auth import get_password_hash

Base.metadata.create_all(bind=engine)

db = SessionLocal()

try:

    admin = UsuarioStaff(
        nombre="Admin",
        apellido="Sistema",
        email="admin@mediportal.com",
        password_hash=get_password_hash("admin123"),
        rol="admin"
    )

    db.add(admin)

    paciente = Paciente(
        nombre="Paciente",
        apellido="Demo",
        dni="10001",
        email="paciente@mail.com",
        password_hash=get_password_hash("123456")
    )

    db.add(paciente)

    db.commit()

    print("OK INSERTADO")

except Exception as e:
    db.rollback()
    print("ERROR:")
    print(e)

finally:
    db.close()