"""
Script para inicializar la base de datos con datos de prueba.
Ejecutar UNA sola vez: python init_db.py
"""
import datetime
from database import engine, SessionLocal
import models
from auth import get_password_hash

models.Base.metadata.create_all(bind=engine)

db = SessionLocal()

try:
    # ─── Staff ────────────────────────────────────────────────────────────────
    if not db.query(models.UsuarioStaff).first():
        # Admin y recepción
        staff_base = [
            models.UsuarioStaff(nombre="Admin", apellido="Principal",
                email="admin@mediportal.com", password_hash=get_password_hash("admin123"),
                rol="admin", activo=True),
            models.UsuarioStaff(nombre="Laura", apellido="Gómez",
                email="recepcion@mediportal.com", password_hash=get_password_hash("recep123"),
                rol="recepcion", activo=True),
        ]

        # Todos los profesionales de la clínica
        # Formato nombre/apellido según como aparecen en el campo profesional de Turno:
        # "Dr. García, Roberto" → nombre="García", apellido="Roberto", pero para el login
        # usamos email derivado. El campo profesional del turno debe matchear exactamente.
        profesionales_data = [
            # Cardiología
            ("Roberto",   "García",      "r.garcia@mediportal.com",    "med123"),
            ("Susana",    "Molina",      "s.molina@mediportal.com",    "med123"),
            # Clínica Médica
            ("Luis",      "Romero",      "l.romero@mediportal.com",    "med123"),
            ("Ana",       "Pedraza",     "a.pedraza@mediportal.com",   "med123"),
            ("Marcelo",   "Figueroa",    "m.figueroa@mediportal.com",  "med123"),
            # Dermatología
            ("Claudia",   "Martínez",    "c.martinez@mediportal.com",  "med123"),
            # Endocrinología
            ("Pablo",     "Fernández",   "p.fernandez@mediportal.com", "med123"),
            ("Patricia",  "Ríos",        "p.rios@mediportal.com",      "med123"),
            # Gastroenterología
            ("Gabriela",  "López",       "g.lopez@mediportal.com",     "med123"),
            ("Sebastián", "Torres",      "s.torres@mediportal.com",    "med123"),
            ("Roxana",    "Blanco",      "r.blanco@mediportal.com",    "med123"),
            # Ginecología
            ("María",     "Benítez",     "m.benitez@mediportal.com",   "med123"),
            ("Valeria",   "Sánchez",     "v.sanchez@mediportal.com",   "med123"),
            ("Lorena",    "Cabrera",     "l.cabrera@mediportal.com",   "med123"),
            # Neurología
            ("Gonzalo",   "Herrera",     "g.herrera@mediportal.com",   "med123"),
            ("Beatriz",   "Quiroga",     "b.quiroga@mediportal.com",   "med123"),
            # Oftalmología
            ("Andrés",    "Vega",        "a.vega@mediportal.com",      "med123"),
            ("Lucía",     "Castro",      "l.castro@mediportal.com",    "med123"),
            ("Tomás",     "Salinas",     "t.salinas@mediportal.com",   "med123"),
            ("Elena",     "Medina",      "e.medina@mediportal.com",    "med123"),
            # Ortopedia
            ("Diego",     "Morales",     "d.morales@mediportal.com",   "med123"),
            ("Nicolás",   "Acosta",      "n.acosta@mediportal.com",    "med123"),
            # Otorrinolaringología
            ("Carmen",    "Ríos",        "c.rios@mediportal.com",      "med123"),
            # Pediatría
            ("Javier",    "Mendoza",     "j.mendoza@mediportal.com",   "med123"),
            ("Sofía",     "Guerrero",    "s.guerrero@mediportal.com",  "med123"),
            ("Natalia",   "Vargas",      "n.vargas@mediportal.com",    "med123"),
            # Psicología
            ("Carolina",  "Suárez",      "c.suarez@mediportal.com",    "med123"),
            ("Rodrigo",   "Muñoz",       "r.munoz@mediportal.com",     "med123"),
            # Psiquiatría
            ("Héctor",    "Núñez",       "h.nunez@mediportal.com",     "med123"),
            ("Silvia",    "Ibarra",      "s.ibarra@mediportal.com",    "med123"),
            # Reumatología
            ("Marta",     "Ibáñez",      "m.ibanez@mediportal.com",    "med123"),
            # Traumatología
            ("Esteban",   "Domínguez",   "e.dominguez@mediportal.com", "med123"),
            ("Miguel",    "Paredes",     "m.paredes@mediportal.com",   "med123"),
            # Urología
            ("Omar",      "Villanueva",  "o.villanueva@mediportal.com","med123"),
            ("Florencia", "Rojas",       "f.rojas@mediportal.com",     "med123"),
        ]

        profs_staff = [
            models.UsuarioStaff(
                nombre=nombre, apellido=apellido, email=email,
                password_hash=get_password_hash(pw),
                rol="profesional", activo=True
            )
            for nombre, apellido, email, pw in profesionales_data
        ]

        db.add_all(staff_base + profs_staff)
        db.commit()
        print(f"✓ Staff creado: 2 admin/recepción + {len(profs_staff)} profesionales")

    # ─── Pacientes ────────────────────────────────────────────────────────────
    if not db.query(models.Paciente).first():
        p1 = models.Paciente(
            dni="30000001",
            nombre="Juan",
            apellido="Pérez",
            email="juan.perez@email.com",
            telefono="11-1234-5678",
            fecha_nacimiento="1985-03-15",
            obra_social="OSDE",
            password_hash=get_password_hash("paciente123"),
            primer_login=False,
            activo=True,
        )
        p2 = models.Paciente(
            dni="35000002",
            nombre="María",
            apellido="González",
            email="maria.g@email.com",
            telefono="11-9876-5432",
            fecha_nacimiento="1992-07-22",
            obra_social="Swiss Medical",
            password_hash=get_password_hash("paciente123"),
            primer_login=True,  # Debe cambiar contraseña
            activo=True,
        )
        p3 = models.Paciente(
            dni="28000003",
            nombre="Carlos",
            apellido="Rodríguez",
            email="carlos.r@email.com",
            telefono="11-5555-1234",
            fecha_nacimiento="1978-11-10",
            obra_social="Galeno",
            password_hash=get_password_hash("paciente123"),
            primer_login=False,
            activo=True,
        )
        db.add_all([p1, p2, p3])
        db.commit()

        # ─── Turnos ───────────────────────────────────────────────────────────
        hoy = datetime.date.today()
        turnos = [
            models.Turno(
                paciente_id=p1.id,
                fecha=(hoy + datetime.timedelta(days=3)).strftime("%Y-%m-%d"),
                hora="09:30",
                especialidad="Cardiología",
                profesional="Dr. Carlos Méndez",
                estado="confirmado",
                observaciones="Control anual",
            ),
            models.Turno(
                paciente_id=p1.id,
                fecha=(hoy - datetime.timedelta(days=10)).strftime("%Y-%m-%d"),
                hora="14:00",
                especialidad="Clínica Médica",
                profesional="Dra. Ana Soria",
                estado="completado",
            ),
            models.Turno(
                paciente_id=p3.id,
                fecha=hoy.strftime("%Y-%m-%d"),
                hora="10:00",
                especialidad="Neurología",
                estado="pendiente",
            ),
            models.Turno(
                paciente_id=p3.id,
                fecha=(hoy + datetime.timedelta(days=7)).strftime("%Y-%m-%d"),
                hora="11:30",
                especialidad="Oftalmología",
                profesional="Dr. Luis Vega",
                estado="confirmado",
            ),
        ]
        db.add_all(turnos)
        db.commit()

        # ─── Resultados (sin archivo, solo demo) ──────────────────────────────
        resultados = [
            models.Resultado(
                paciente_id=p1.id,
                titulo="Electrocardiograma",
                descripcion="ECG en reposo. Ritmo sinusal normal.",
                fecha_estudio=(hoy - datetime.timedelta(days=10)).strftime("%Y-%m-%d"),
                subido_por="Dr. Carlos Méndez",
                archivo_nombre=None,
                archivo_path=None,
            ),
            models.Resultado(
                paciente_id=p1.id,
                titulo="Análisis de Sangre Completo",
                descripcion="Hemograma, glucemia, colesterol. Ver informe adjunto.",
                fecha_estudio=(hoy - datetime.timedelta(days=30)).strftime("%Y-%m-%d"),
                subido_por="Lab. Central",
                archivo_nombre=None,
                archivo_path=None,
            ),
            models.Resultado(
                paciente_id=p3.id,
                titulo="Resonancia Magnética Cerebral",
                descripcion="Sin hallazgos patológicos.",
                fecha_estudio=(hoy - datetime.timedelta(days=5)).strftime("%Y-%m-%d"),
                subido_por="Dr. Carlos Méndez",
                archivo_nombre=None,
                archivo_path=None,
            ),
        ]
        db.add_all(resultados)
        db.commit()
        print("✓ Pacientes, turnos y resultados de prueba creados")

    print("\n✅ Base de datos inicializada correctamente.")
    print("\n─── Credenciales de acceso ───────────────────────────────")
    print("ADMIN:    admin@mediportal.com     /  admin123")
    print("RECEP:    recepcion@mediportal.com /  recep123")
    print("MÉDICOS:  [nombre]@mediportal.com  /  med123")
    print("          (ver lista completa en init_db.py)")
    print("")
    print("PACIENTE: DNI 30000001  /  paciente123  (acceso directo)")
    print("PACIENTE: DNI 35000002  /  paciente123  (debe cambiar contraseña)")
    print("PACIENTE: DNI 28000003  /  paciente123  (acceso directo)")
    print("──────────────────────────────────────────────────────────")

except Exception as e:
    print(f"❌ Error: {e}")
    db.rollback()
    raise
finally:
    db.close()
