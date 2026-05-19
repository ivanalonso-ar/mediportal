"""Utilidades para crear notificaciones in-app."""
from models import Notificacion


def crear_notificacion(db, paciente_id: int, titulo: str, mensaje: str, tipo: str = "info"):
    n = Notificacion(paciente_id=paciente_id, titulo=titulo, mensaje=mensaje, tipo=tipo)
    db.add(n)
    # db.commit() lo hace el caller
