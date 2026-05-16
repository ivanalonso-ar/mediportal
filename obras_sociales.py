"""
Catalogo de obras sociales/prepagas.

DEFAULT_OBRAS_SOCIALES se usa para inicializar clientes nuevos y como fallback
si la base todavia no tiene catalogo cargado.
"""

DEFAULT_OBRAS_SOCIALES = sorted(set([
    "Accord Salud", "ACA Salud", "Aigle", "Amansalud", "Ameba",
    "Consolidar Salud", "Federada Salud", "Galeno", "Hospital Aleman (Plan de Salud)",
    "Hospital Italiano (Plan de Salud)", "Jerarquicos Salud", "Luis Pasteur",
    "Medicus", "Medife", "NOBIS", "Omint", "OSDE", "PAMI Plus",
    "Prevencion Salud", "Qualitas", "Sancor Salud", "Swiss Medical",
    "PAMI", "APROSS (Cordoba)", "DOSEP (San Juan)", "IOSFA", "IOMA (Pcia. Buenos Aires)",
    "IOSPER (Entre Rios)", "IPAM (Cordoba)", "IPROSS (Rio Negro)", "IPSST (Tucuman)",
    "ISSARA (La Rioja)", "ISSJ (Jujuy)", "ISSN (Neuquen)", "ISSP (Salta)",
    "OSBA", "OSEP (Mendoza)", "OSPRERA",
    "AMFFA", "APSOT", "ASSPE", "ATLAS", "ATSA", "CAMI", "CIMARA", "CODEM",
    "COESPU", "COOPSER", "DACRA", "DASUTEN", "DOSUBA", "FATSA (Sanidad)",
    "FECLIBA", "FEMECA", "FEPSAL", "IOSE (Fuerzas Armadas)",
    "MUTUAL ATE", "MUTUAL DEL PERSONAL BANCARIO", "MUTUAL DEL PERSONAL DOCENTE",
    "MUTUAL DEL PERSONAL FERROVIARIO", "MUTUAL DEL PERSONAL DE SALUD",
    "MUTUAL SMATA", "MUTUAL CAJA FORENSE", "OBRA SOCIAL DEL PODER JUDICIAL",
    "OBRA SOCIAL DE INGENIEROS", "OBRA SOCIAL UNIVERSITARIOS (DOSUBA)",
    "OACH", "OAFA", "OAMPP", "OATACO", "OSAM (Musicos)", "OSAMPTA", "OSBAM",
    "OSCARD", "OSCAS", "OSCOEMA", "OSDIPP", "OSECAC (Empleados de Comercio)",
    "OSECTE", "OSEPC", "OSFATLYF (Luz y Fuerza)", "OSFATUN", "OSFE", "OSIM",
    "OSMECON", "OSMISS", "OSMATA", "OSMATA (Mecanicos y Afines - SMATA)",
    "OSNA (Notarios)", "OSPA", "OSPACA", "OSPACP", "OSPAGA", "OSPAT", "OSPAV",
    "OSPE", "OSPE (Petroquimica)", "OSPEC", "OSPEDYC", "OSPEGA", "OSPEGAP",
    "OSPEJBA", "OSPEP", "OSPES", "OSPESBA", "OSPF", "OSPFBA", "OSPG", "OSPHA",
    "OSPI", "OSPIB", "OSPIC", "OSPIAVE", "OSPIBAL", "OSPICM", "OSPICO",
    "OSPIE", "OSPIF", "OSPIFAR", "OSPIG", "OSPIGAS", "OSPIH", "OSPIL",
    "OSPIM", "OSPIMPE", "OSPIN", "OSPINT", "OSPIO", "OSPIP", "OSPIQ",
    "OSPIR", "OSPIRAL", "OSPIS", "OSPISA", "OSPIT", "OSPIT (Textil)",
    "OSPLADEP", "OSPLAD (Docentes Privados)", "OSPM", "OSPREDYC", "OSPSA",
    "OSPSIP", "OSSEG (Seguros)", "OSSSB", "OSSPROV", "OSTAA", "OSTEP",
    "OSTF", "OSTHG", "OSTIA", "OSTINDE", "OSTIP", "OSTML", "OSTRA",
    "OSTUNCOP", "OSUG", "OSUPSEG", "OSUTRA", "OSUTRA (Transporte)",
    "OSVARA", "SPESEMF", "UPCN (Civil Nacional)", "UNIONAGA",
    "UTHGRA (Gastronomicos)", "VADEME",
]))

OBRAS_SOCIALES = [o for o in DEFAULT_OBRAS_SOCIALES if o.strip()]


def listar_obras_sociales(db=None) -> list[str]:
    if db is None:
        return OBRAS_SOCIALES
    try:
        from models import ObraSocial

        rows = db.query(ObraSocial).filter(ObraSocial.activa == True).order_by(ObraSocial.nombre.asc()).all()
        return [r.nombre for r in rows] or OBRAS_SOCIALES
    except Exception:
        return OBRAS_SOCIALES
