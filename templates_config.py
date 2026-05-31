from fastapi.templating import Jinja2Templates
from fecha_utils import fecha_es, fecha_corta_es

templates = Jinja2Templates(directory="templates")
templates.env.filters["fecha_es"] = fecha_es
templates.env.filters["fecha_corta_es"] = fecha_corta_es
