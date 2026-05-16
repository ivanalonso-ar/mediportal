from sqlalchemy.orm import Session

from models import Turno
from horarios import catalogo_horarios

ESTADOS_ACTIVOS = ("pendiente", "confirmado")


def capacidad_especialidad(especialidad: str, db: Session | None = None) -> int:
    profesionales = catalogo_horarios(db)["profesionales"]
    return max(1, len(profesionales.get(especialidad, [])))


def hora_disponible(
    db: Session,
    fecha: str,
    hora: str,
    especialidad: str,
    profesional: str = "",
    exclude_turno_id: int | None = None,
) -> bool:
    query = db.query(Turno).filter(
        Turno.fecha == fecha,
        Turno.hora == hora,
        Turno.estado.in_(ESTADOS_ACTIVOS),
    )
    if exclude_turno_id:
        query = query.filter(Turno.id != exclude_turno_id)
    activos = query.all()

    profesional = (profesional or "").strip()
    if profesional:
        return all((t.profesional or "").strip() != profesional for t in activos)

    mismos = [t for t in activos if (t.especialidad or "").strip() == especialidad.strip()]
    return len(mismos) < capacidad_especialidad(especialidad, db)


def horas_sin_disponibilidad(db: Session, fecha: str, especialidad: str) -> set[str]:
    activos = db.query(Turno).filter(
        Turno.fecha == fecha,
        Turno.especialidad == especialidad,
        Turno.estado.in_(ESTADOS_ACTIVOS),
    ).all()
    cap = capacidad_especialidad(especialidad, db)
    conteo: dict[str, int] = {}
    for t in activos:
        conteo[t.hora] = conteo.get(t.hora, 0) + 1
    return {hora for hora, total in conteo.items() if total >= cap}
