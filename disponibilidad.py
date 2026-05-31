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
    lock: bool = False,
) -> bool:
    query = db.query(Turno).filter(
        Turno.fecha == fecha,
        Turno.hora == hora,
        Turno.estado.in_(ESTADOS_ACTIVOS),
    )
    if exclude_turno_id:
        query = query.filter(Turno.id != exclude_turno_id)
    if lock:
        # Bloquea filas conflictivas para serializar inserciones concurrentes
        # en PostgreSQL. En SQLite es no-op silencioso.
        query = query.with_for_update()
    activos = query.all()

    profesional = (profesional or "").strip()
    if profesional:
        return all((t.profesional or "").strip() != profesional for t in activos)

    mismos = [t for t in activos if (t.especialidad or "").strip() == especialidad.strip()]
    return len(mismos) < capacidad_especialidad(especialidad, db)


def horas_sin_disponibilidad(db: Session, fecha: str, especialidad: str, profesional: str = "") -> set[str]:
    query = db.query(Turno).filter(
        Turno.fecha == fecha,
        Turno.estado.in_(ESTADOS_ACTIVOS),
    )
    profesional = (profesional or "").strip()
    if profesional:
        # Si se conoce el profesional, bloqueamos exactamente sus horas ocupadas
        query = query.filter(Turno.profesional == profesional)
        activos = query.all()
        return {t.hora for t in activos}
    else:
        query = query.filter(Turno.especialidad == especialidad)
        activos = query.all()
        cap = capacidad_especialidad(especialidad, db)
        conteo: dict[str, int] = {}
        for t in activos:
            conteo[t.hora] = conteo.get(t.hora, 0) + 1
        return {hora for hora, total in conteo.items() if total >= cap}
