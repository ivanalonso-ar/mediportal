"""
Utilidades de formato de fecha en español para templates Jinja2.
"""

DIAS_ES = {
    "Monday": "Lunes",
    "Tuesday": "Martes",
    "Wednesday": "Miércoles",
    "Thursday": "Jueves",
    "Friday": "Viernes",
    "Saturday": "Sábado",
    "Sunday": "Domingo",
}

MESES_ES = {
    "January": "enero",
    "February": "febrero",
    "March": "marzo",
    "April": "abril",
    "May": "mayo",
    "June": "junio",
    "July": "julio",
    "August": "agosto",
    "September": "septiembre",
    "October": "octubre",
    "November": "noviembre",
    "December": "diciembre",
}

MESES_CORTOS_ES = {
    "Jan": "ene", "Feb": "feb", "Mar": "mar", "Apr": "abr",
    "May": "may", "Jun": "jun", "Jul": "jul", "Aug": "ago",
    "Sep": "sep", "Oct": "oct", "Nov": "nov", "Dec": "dic",
}


def fecha_es(date_obj) -> str:
    """Retorna 'Lunes 11 de marzo de 2026'"""
    import datetime
    if isinstance(date_obj, str):
        date_obj = datetime.datetime.strptime(date_obj, "%Y-%m-%d").date()
    dia_nombre = DIAS_ES.get(date_obj.strftime("%A"), date_obj.strftime("%A"))
    mes_nombre = MESES_ES.get(date_obj.strftime("%B"), date_obj.strftime("%B"))
    return f"{dia_nombre} {date_obj.day} de {mes_nombre} de {date_obj.year}"


def fecha_corta_es(date_obj) -> str:
    """Retorna 'Lun 11/03'"""
    import datetime
    if isinstance(date_obj, str):
        date_obj = datetime.datetime.strptime(date_obj, "%Y-%m-%d").date()
    dia_nombre = DIAS_ES.get(date_obj.strftime("%A"), date_obj.strftime("%A"))[:3]
    return f"{dia_nombre} {date_obj.day}/{date_obj.month:02d}"
