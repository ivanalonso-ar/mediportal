"""
Configuración de horarios y profesionales por especialidad.
Slots cada 20 minutos.
"""

def _slots(h_ini: int, h_fin: int) -> list:
    s, h, m = [], h_ini, 0
    while (h, m) < (h_fin, 0):
        s.append(f"{h:02d}:{m:02d}")
        m += 20
        if m >= 60:
            m = 0
            h += 1
    return s


SLOTS_MANANA = _slots(8, 14)
SLOTS_TARDE  = _slots(14, 19)

PROFESIONALES = {
    "Cardiología": [
        {"nombre": "Dr. García, Roberto",    "turno": "manana"},
        {"nombre": "Dra. Molina, Susana",    "turno": "tarde"},
    ],
    "Clínica Médica": [
        {"nombre": "Dr. Romero, Luis",       "turno": "manana"},
        {"nombre": "Dra. Pedraza, Ana",      "turno": "manana"},
        {"nombre": "Dr. Figueroa, Marcelo",  "turno": "tarde"},
    ],
    "Dermatología": [
        {"nombre": "Dra. Martínez, Claudia", "turno": "manana"},
    ],
    "Endocrinología": [
        {"nombre": "Dr. Fernández, Pablo",   "turno": "manana"},
        {"nombre": "Dra. Ríos, Patricia",    "turno": "tarde"},
    ],
    "Gastroenterología": [
        {"nombre": "Dra. López, Gabriela",   "turno": "manana"},
        {"nombre": "Dr. Torres, Sebastián",  "turno": "tarde"},
        {"nombre": "Dra. Blanco, Roxana",    "turno": "tarde"},
    ],
    "Ginecología": [
        {"nombre": "Dra. Benítez, María",    "turno": "manana"},
        {"nombre": "Dra. Sánchez, Valeria",  "turno": "manana"},
        {"nombre": "Dra. Cabrera, Lorena",   "turno": "tarde"},
    ],
    "Neurología": [
        {"nombre": "Dr. Herrera, Gonzalo",   "turno": "manana"},
        {"nombre": "Dra. Quiroga, Beatriz",  "turno": "tarde"},
    ],
    "Oftalmología": [
        {"nombre": "Dr. Vega, Andrés",       "turno": "manana"},
        {"nombre": "Dra. Castro, Lucía",     "turno": "manana"},
        {"nombre": "Dr. Salinas, Tomás",     "turno": "tarde"},
        {"nombre": "Dra. Medina, Elena",     "turno": "tarde"},
    ],
    "Ortopedia": [
        {"nombre": "Dr. Morales, Diego",     "turno": "tarde"},
        {"nombre": "Dr. Acosta, Nicolás",    "turno": "tarde"},
    ],
    "Otorrinolaringología": [
        {"nombre": "Dra. Ríos, Carmen",      "turno": "tarde"},
    ],
    "Pediatría": [
        {"nombre": "Dr. Mendoza, Javier",    "turno": "manana"},
        {"nombre": "Dra. Guerrero, Sofía",   "turno": "tarde"},
        {"nombre": "Dra. Vargas, Natalia",   "turno": "tarde"},
    ],
    "Psicología": [
        {"nombre": "Lic. Suárez, Carolina",  "turno": "tarde"},
        {"nombre": "Lic. Muñoz, Rodrigo",    "turno": "tarde"},
    ],
    "Psiquiatría": [
        {"nombre": "Dr. Núñez, Héctor",      "turno": "tarde"},
        {"nombre": "Dra. Ibarra, Silvia",    "turno": "tarde"},
    ],
    "Reumatología": [
        {"nombre": "Dra. Ibáñez, Marta",     "turno": "tarde"},
    ],
    "Traumatología": [
        {"nombre": "Dr. Domínguez, Esteban", "turno": "manana"},
        {"nombre": "Dr. Paredes, Miguel",    "turno": "tarde"},
    ],
    "Urología": [
        {"nombre": "Dr. Villanueva, Omar",   "turno": "manana"},
        {"nombre": "Dra. Rojas, Florencia",  "turno": "tarde"},
    ],
}

ESPECIALIDADES = sorted(PROFESIONALES.keys())

TURNO_POR_ESPECIALIDAD = {}
for _esp, _profs in PROFESIONALES.items():
    _m = sum(1 for p in _profs if p["turno"] == "manana")
    _t = sum(1 for p in _profs if p["turno"] == "tarde")
    TURNO_POR_ESPECIALIDAD[_esp] = "manana" if _m >= _t else "tarde"

def slots_para_especialidad(especialidad):
    turno = TURNO_POR_ESPECIALIDAD.get(especialidad, "manana")
    return SLOTS_MANANA if turno == "manana" else SLOTS_TARDE

def slots_para_profesional(especialidad, nombre_profesional):
    for p in PROFESIONALES.get(especialidad, []):
        if p["nombre"] == nombre_profesional:
            return SLOTS_MANANA if p["turno"] == "manana" else SLOTS_TARDE
    return SLOTS_MANANA

def profesionales_json():
    result = {}
    for esp, profs in PROFESIONALES.items():
        result[esp] = [
            {
                "nombre": p["nombre"],
                "turno":  p["turno"],
                "slots":  SLOTS_MANANA if p["turno"] == "manana" else SLOTS_TARDE,
            }
            for p in profs
        ]
    return result
