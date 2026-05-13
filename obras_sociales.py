"""
Lista completa de obras sociales, prepagas y mutuales de Argentina.
"""

OBRAS_SOCIALES = sorted(set([
    # Prepagas
    "Accord Salud", "ACA Salud", "Aigle", "Amansalud", "Ameba",
    "Consolidar Salud", "Federada Salud", "Galeno", "Hospital Alemán (Plan de Salud)",
    "Hospital Italiano (Plan de Salud)", "Jerárquicos Salud", "Luis Pasteur",
    "Medicus", "Medifé", "NOBIS", "Omint", "OSDE", "PAMI Plus",
    "Prevención Salud", "Qualitas", "Sancor Salud", "Swiss Medical",
    # PAMI y provinciales
    "PAMI",
    "APROSS (Córdoba)", "DOSEP (San Juan)", "IOSFA", "IOMA (Pcia. Buenos Aires)",
    "IOSPER (Entre Ríos)", "IPAM (Córdoba)", "IPROSS (Río Negro)", "IPSST (Tucumán)",
    "ISSARA (La Rioja)", "ISSJ (Jujuy)", "ISSN (Neuquén)", "ISSP (Salta)",
    "OSBA", "OSEP (Mendoza)", "OSPRERA",
    # Sindicales y nacionales
    "AMFFA", "APSOT", "ASSPE", "ATLAS", "ATSA",
    "CAMI", "CIMARA", "CODEM", "COESPU", "COOPSER",
    "DACRA", "DASUTEN", "DOSUBA", "DOSUBA",
    "FATSA (Sanidad)", "FECLIBA", "FEMECA", "FEPSAL",
    "IOSE (Fuerzas Armadas)",
    "MUTUAL ATE", "MUTUAL DEL PERSONAL BANCARIO", "MUTUAL DEL PERSONAL DOCENTE",
    "MUTUAL DEL PERSONAL FERROVIARIO", "MUTUAL DEL PERSONAL DE SALUD",
    "MUTUAL SMATA", "MUTUAL CAJA FORENSE",
    "OBRA SOCIAL DEL PODER JUDICIAL", "OBRA SOCIAL DE INGENIEROS",
    "OBRA SOCIAL UNIVERSITARIOS (DOSUBA)",
    "OACH", "OAFA", "OAMPP", "OATACO",
    "OSAM (Músicos)", "OSAMPTA", "OSBAM", "OSCARD", "OSCAS",
    "OSCOEMA", "OSDIPP", "OSECAC (Empleados de Comercio)", "OSECTE",
    "OSEPC", "OSFATLYF (Luz y Fuerza)", "OSFATUN", "OSFE", "OSIM",
    "OSMECON", "OSMISS", "OSMATA", "OSMATA (Mecánicos y Afines - SMATA)",
    "OSNA (Notarios)",
    "OSPA", "OSPACA", "OSPACP", "OSPAGA", "OSPAT", "OSPAV",
    "OSPE", "OSPE (Petroquímica)", "OSPEC", "OSPEDYC", "OSPEGA",
    "OSPEGAP", "OSPEJBA", "OSPEP", "OSPES", "OSPESBA",
    "OSPF", "OSPFBA", "OSPG", "OSPHA",
    "OSPI", "OSPIB", "OSPIC", "OSPIAVE", "OSPIBAL", "OSPICM", "OSPICO",
    "OSPIE", "OSPIF", "OSPIFAR", "OSPIG", "OSPIGAS", "OSPIH", "OSPIL",
    "OSPIM", "OSPIMPE", "OSPIN", "OSPINT", "OSPIO", "OSPIP", "OSPIQ",
    "OSPIR", "OSPIRAL", "OSPIS", "OSPISA", "OSPIT", "OSPIT (Textil)",
    "OSPLADEP", "OSPLAD (Docentes Privados)", "OSPM",
    "OSPREDYC", "OSPSA", "OSPSIP",
    "OSSEG (Seguros)", "OSSSB", "OSSPROV",
    "OSTAA", "OSTEP", "OSTF", "OSTHG", "OSTIA", "OSTINDE", "OSTIP",
    "OSTML", "OSTRA", "OSTUNCOP",
    "OSUG", "OSUPSEG", "OSUTRA", "OSUTRA (Transporte)",
    "OSVARA",
    "SPESEMF",
    "UPCN (Civil Nacional)", "UNIONAGA",
    "UTHGRA (Gastronómicos)", "VADEME",
]))

OBRAS_SOCIALES = [o for o in OBRAS_SOCIALES if o.strip()]
