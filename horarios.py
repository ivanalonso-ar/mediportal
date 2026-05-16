"""
Catalogo de horarios y profesionales.

Los defaults se usan solo como semilla/fallback. En runtime, los routers llaman a
catalogo_horarios(db) para leer especialidades y profesionales desde PostgreSQL.
"""


def _slots(hora_inicio: str, hora_fin: str, intervalo_minutos: int = 20) -> list[str]:
    h_ini, m_ini = [int(x) for x in hora_inicio.split(":")]
    h_fin, m_fin = [int(x) for x in hora_fin.split(":")]
    slots, h, m = [], h_ini, m_ini
    while (h, m) < (h_fin, m_fin):
        slots.append(f"{h:02d}:{m:02d}")
        m += intervalo_minutos
        while m >= 60:
            m -= 60
            h += 1
    return slots


DEFAULT_SLOTS_MANANA = _slots("08:00", "14:00")
DEFAULT_SLOTS_TARDE = _slots("14:00", "19:00")

DEFAULT_PROFESIONALES = {
    "Cardiologia": [
        {"nombre": "Dr. Garcia, Roberto", "turno": "manana", "email": "r.garcia@mediportal.com", "nombre_staff": "Roberto", "apellido_staff": "Garcia"},
        {"nombre": "Dra. Molina, Susana", "turno": "tarde", "email": "s.molina@mediportal.com", "nombre_staff": "Susana", "apellido_staff": "Molina"},
    ],
    "Clinica Medica": [
        {"nombre": "Dr. Romero, Luis", "turno": "manana", "email": "l.romero@mediportal.com", "nombre_staff": "Luis", "apellido_staff": "Romero"},
        {"nombre": "Dra. Pedraza, Ana", "turno": "manana", "email": "a.pedraza@mediportal.com", "nombre_staff": "Ana", "apellido_staff": "Pedraza"},
        {"nombre": "Dr. Figueroa, Marcelo", "turno": "tarde", "email": "m.figueroa@mediportal.com", "nombre_staff": "Marcelo", "apellido_staff": "Figueroa"},
    ],
    "Dermatologia": [
        {"nombre": "Dra. Martinez, Claudia", "turno": "manana", "email": "c.martinez@mediportal.com", "nombre_staff": "Claudia", "apellido_staff": "Martinez"},
    ],
    "Endocrinologia": [
        {"nombre": "Dr. Fernandez, Pablo", "turno": "manana", "email": "p.fernandez@mediportal.com", "nombre_staff": "Pablo", "apellido_staff": "Fernandez"},
        {"nombre": "Dra. Rios, Patricia", "turno": "tarde", "email": "p.rios@mediportal.com", "nombre_staff": "Patricia", "apellido_staff": "Rios"},
    ],
    "Gastroenterologia": [
        {"nombre": "Dra. Lopez, Gabriela", "turno": "manana", "email": "g.lopez@mediportal.com", "nombre_staff": "Gabriela", "apellido_staff": "Lopez"},
        {"nombre": "Dr. Torres, Sebastian", "turno": "tarde", "email": "s.torres@mediportal.com", "nombre_staff": "Sebastian", "apellido_staff": "Torres"},
        {"nombre": "Dra. Blanco, Roxana", "turno": "tarde", "email": "r.blanco@mediportal.com", "nombre_staff": "Roxana", "apellido_staff": "Blanco"},
    ],
    "Ginecologia": [
        {"nombre": "Dra. Benitez, Maria", "turno": "manana", "email": "m.benitez@mediportal.com", "nombre_staff": "Maria", "apellido_staff": "Benitez"},
        {"nombre": "Dra. Sanchez, Valeria", "turno": "manana", "email": "v.sanchez@mediportal.com", "nombre_staff": "Valeria", "apellido_staff": "Sanchez"},
        {"nombre": "Dra. Cabrera, Lorena", "turno": "tarde", "email": "l.cabrera@mediportal.com", "nombre_staff": "Lorena", "apellido_staff": "Cabrera"},
    ],
    "Neurologia": [
        {"nombre": "Dr. Herrera, Gonzalo", "turno": "manana", "email": "g.herrera@mediportal.com", "nombre_staff": "Gonzalo", "apellido_staff": "Herrera"},
        {"nombre": "Dra. Quiroga, Beatriz", "turno": "tarde", "email": "b.quiroga@mediportal.com", "nombre_staff": "Beatriz", "apellido_staff": "Quiroga"},
    ],
    "Oftalmologia": [
        {"nombre": "Dr. Vega, Andres", "turno": "manana", "email": "a.vega@mediportal.com", "nombre_staff": "Andres", "apellido_staff": "Vega"},
        {"nombre": "Dra. Castro, Lucia", "turno": "manana", "email": "l.castro@mediportal.com", "nombre_staff": "Lucia", "apellido_staff": "Castro"},
        {"nombre": "Dr. Salinas, Tomas", "turno": "tarde", "email": "t.salinas@mediportal.com", "nombre_staff": "Tomas", "apellido_staff": "Salinas"},
        {"nombre": "Dra. Medina, Elena", "turno": "tarde", "email": "e.medina@mediportal.com", "nombre_staff": "Elena", "apellido_staff": "Medina"},
    ],
    "Ortopedia": [
        {"nombre": "Dr. Morales, Diego", "turno": "tarde", "email": "d.morales@mediportal.com", "nombre_staff": "Diego", "apellido_staff": "Morales"},
        {"nombre": "Dr. Acosta, Nicolas", "turno": "tarde", "email": "n.acosta@mediportal.com", "nombre_staff": "Nicolas", "apellido_staff": "Acosta"},
    ],
    "Otorrinolaringologia": [
        {"nombre": "Dra. Rios, Carmen", "turno": "tarde", "email": "c.rios@mediportal.com", "nombre_staff": "Carmen", "apellido_staff": "Rios"},
    ],
    "Pediatria": [
        {"nombre": "Dr. Mendoza, Javier", "turno": "manana", "email": "j.mendoza@mediportal.com", "nombre_staff": "Javier", "apellido_staff": "Mendoza"},
        {"nombre": "Dra. Guerrero, Sofia", "turno": "tarde", "email": "s.guerrero@mediportal.com", "nombre_staff": "Sofia", "apellido_staff": "Guerrero"},
        {"nombre": "Dra. Vargas, Natalia", "turno": "tarde", "email": "n.vargas@mediportal.com", "nombre_staff": "Natalia", "apellido_staff": "Vargas"},
    ],
    "Psicologia": [
        {"nombre": "Lic. Suarez, Carolina", "turno": "tarde", "email": "c.suarez@mediportal.com", "nombre_staff": "Carolina", "apellido_staff": "Suarez"},
        {"nombre": "Lic. Munoz, Rodrigo", "turno": "tarde", "email": "r.munoz@mediportal.com", "nombre_staff": "Rodrigo", "apellido_staff": "Munoz"},
    ],
    "Psiquiatria": [
        {"nombre": "Dr. Nunez, Hector", "turno": "tarde", "email": "h.nunez@mediportal.com", "nombre_staff": "Hector", "apellido_staff": "Nunez"},
        {"nombre": "Dra. Ibarra, Silvia", "turno": "tarde", "email": "s.ibarra@mediportal.com", "nombre_staff": "Silvia", "apellido_staff": "Ibarra"},
    ],
    "Reumatologia": [
        {"nombre": "Dra. Ibanez, Marta", "turno": "tarde", "email": "m.ibanez@mediportal.com", "nombre_staff": "Marta", "apellido_staff": "Ibanez"},
    ],
    "Traumatologia": [
        {"nombre": "Dr. Dominguez, Esteban", "turno": "manana", "email": "e.dominguez@mediportal.com", "nombre_staff": "Esteban", "apellido_staff": "Dominguez"},
        {"nombre": "Dr. Paredes, Miguel", "turno": "tarde", "email": "m.paredes@mediportal.com", "nombre_staff": "Miguel", "apellido_staff": "Paredes"},
    ],
    "Urologia": [
        {"nombre": "Dr. Villanueva, Omar", "turno": "manana", "email": "o.villanueva@mediportal.com", "nombre_staff": "Omar", "apellido_staff": "Villanueva"},
        {"nombre": "Dra. Rojas, Florencia", "turno": "tarde", "email": "f.rojas@mediportal.com", "nombre_staff": "Florencia", "apellido_staff": "Rojas"},
    ],
}


def _turno_por_especialidad(profesionales: dict[str, list[dict]]) -> dict[str, str]:
    result = {}
    for esp, profs in profesionales.items():
        manana = sum(1 for p in profs if p["turno"] == "manana")
        tarde = sum(1 for p in profs if p["turno"] == "tarde")
        result[esp] = "manana" if manana >= tarde else "tarde"
    return result


PROFESIONALES = DEFAULT_PROFESIONALES
ESPECIALIDADES = sorted(DEFAULT_PROFESIONALES.keys())
TURNO_POR_ESPECIALIDAD = _turno_por_especialidad(DEFAULT_PROFESIONALES)
SLOTS_MANANA = DEFAULT_SLOTS_MANANA
SLOTS_TARDE = DEFAULT_SLOTS_TARDE


def catalogo_horarios(db=None) -> dict:
    if db is None:
        profesionales = DEFAULT_PROFESIONALES
        cfg = None
    else:
        try:
            from models import ConfiguracionClinica, Especialidad, ProfesionalEspecialidad

            cfg = db.query(ConfiguracionClinica).filter(ConfiguracionClinica.activo == True).first()
            especialidades = db.query(Especialidad).filter(Especialidad.activa == True).order_by(Especialidad.orden.asc(), Especialidad.nombre.asc()).all()
            profesionales = {}
            for esp in especialidades:
                rows = db.query(ProfesionalEspecialidad).filter(
                    ProfesionalEspecialidad.especialidad_id == esp.id,
                    ProfesionalEspecialidad.activo == True,
                ).order_by(ProfesionalEspecialidad.nombre_publico.asc()).all()
                profesionales[esp.nombre] = [
                    {"nombre": r.nombre_publico, "turno": r.turno}
                    for r in rows
                ]
            if not profesionales:
                profesionales = DEFAULT_PROFESIONALES
        except Exception:
            profesionales = DEFAULT_PROFESIONALES
            cfg = None

    intervalo = (cfg.duracion_slot_minutos if cfg else 20) or 20
    slots_manana = _slots(cfg.hora_inicio_manana, cfg.hora_fin_manana, intervalo) if cfg else DEFAULT_SLOTS_MANANA
    slots_tarde = _slots(cfg.hora_inicio_tarde, cfg.hora_fin_tarde, intervalo) if cfg else DEFAULT_SLOTS_TARDE
    turno_por_especialidad = _turno_por_especialidad(profesionales)
    profesionales_payload = {
        esp: [
            {
                "nombre": p["nombre"],
                "turno": p["turno"],
                "slots": slots_manana if p["turno"] == "manana" else slots_tarde,
            }
            for p in profs
        ]
        for esp, profs in profesionales.items()
    }
    return {
        "especialidades": sorted(profesionales.keys()),
        "profesionales": profesionales,
        "turno_por_especialidad": turno_por_especialidad,
        "slots_manana": slots_manana,
        "slots_tarde": slots_tarde,
        "profesionales_json": profesionales_payload,
    }


def slots_para_especialidad(especialidad, db=None):
    data = catalogo_horarios(db)
    turno = data["turno_por_especialidad"].get(especialidad, "manana")
    return data["slots_manana"] if turno == "manana" else data["slots_tarde"]


def slots_para_profesional(especialidad, nombre_profesional, db=None):
    data = catalogo_horarios(db)
    for p in data["profesionales"].get(especialidad, []):
        if p["nombre"] == nombre_profesional:
            return data["slots_manana"] if p["turno"] == "manana" else data["slots_tarde"]
    return data["slots_manana"]


def profesionales_json(db=None):
    return catalogo_horarios(db)["profesionales_json"]
