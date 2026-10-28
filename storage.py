"""
Servicio de almacenamiento de archivos.
Si SUPABASE_URL y SUPABASE_KEY están configurados, usa Supabase Storage.
Si no, guarda en filesystem local (solo para desarrollo).
"""
import os
import uuid
import logging
import mimetypes
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen
from config import settings

logger = logging.getLogger("mediportal.storage")

BUCKET = "resultados"
LOCAL_UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads/resultados")
SIGNED_URL_TTL_SECONDS = int(os.getenv("SIGNED_URL_TTL_SECONDS", "60"))


def _usar_supabase() -> bool:
    return bool(settings.SUPABASE_URL and settings.SUPABASE_KEY)


def _solicitar_storage(metodo: str, ruta: str, contenido: bytes | dict | None = None, tipo: str | None = None) -> bytes:
    """Llama a Storage usando la clave secreta solo en el encabezado apikey."""
    base = settings.SUPABASE_URL.rstrip("/")
    url = f"{base}/storage/v1/{ruta.lstrip('/')}"
    headers = {"apikey": settings.SUPABASE_KEY}
    cuerpo = contenido
    if isinstance(contenido, dict):
        cuerpo = json.dumps(contenido).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif tipo:
        headers["Content-Type"] = tipo

    solicitud = Request(url, data=cuerpo, headers=headers, method=metodo)
    try:
        with urlopen(solicitud, timeout=30) as respuesta:
            return respuesta.read()
    except HTTPError as error:
        # No incluir headers ni cuerpo para evitar filtrar credenciales o datos del archivo.
        raise RuntimeError(f"Supabase Storage devolvió HTTP {error.code}.") from error
    except URLError as error:
        raise RuntimeError("No se pudo conectar con Supabase Storage.") from error


def subir_archivo(contenido: bytes, nombre_original: str, ext: str, clinica_slug: str = "mediportal") -> tuple[str, str]:
    """
    Sube un archivo al storage.
    Retorna (archivo_path, archivo_nombre).
    - En Supabase: archivo_path es el path privado dentro del bucket.
    - En local: archivo_path es el path en disco.
    """
    nombre_unico = f"{uuid.uuid4().hex}{ext}"
    ruta_relativa = f"{clinica_slug}/resultados/{nombre_unico}"

    if _usar_supabase():
        try:
            ruta_api = f"object/{BUCKET}/{quote(ruta_relativa, safe='/')}"
            _solicitar_storage("POST", ruta_api, contenido, _mime(ext))
            logger.info(f"[storage] Archivo subido a Supabase para clínica {clinica_slug}")
            return ruta_relativa, nombre_original
        except Exception as e:
            logger.error(f"[storage] Error subiendo a Supabase: {e}")
            raise

    # Fallback: filesystem local
    directorio_clinica = os.path.join(LOCAL_UPLOAD_DIR, clinica_slug)
    os.makedirs(directorio_clinica, exist_ok=True)
    path = os.path.join(directorio_clinica, nombre_unico)
    with open(path, "wb") as f:
        f.write(contenido)
    logger.info(f"[storage] Archivo guardado localmente: {path}")
    return path, nombre_original


def leer_archivo(archivo_path: str) -> tuple[bytes, str]:
    """
    Lee un archivo del storage.
    Retorna (contenido, media_type).
    """
    if archivo_path.startswith("http"):
        # Compatibilidad con resultados viejos guardados como URL pública.
        import urllib.request
        with urllib.request.urlopen(archivo_path, timeout=10) as resp:
            contenido = resp.read()
        ext = archivo_path.split(".")[-1].lower()
        media_type = _mime(f".{ext}")
        return contenido, media_type

    if _usar_supabase() and not os.path.exists(archivo_path):
        ruta_api = f"object/authenticated/{BUCKET}/{quote(archivo_path, safe='/')}"
        contenido = _solicitar_storage("GET", ruta_api)
        return contenido, _mime(Path(archivo_path).suffix)

    # Local
    if not os.path.exists(archivo_path):
        raise FileNotFoundError(f"Archivo no encontrado: {archivo_path}")
    with open(archivo_path, "rb") as f:
        contenido = f.read()
    media_type, _ = mimetypes.guess_type(archivo_path)
    return contenido, media_type or "application/octet-stream"


def eliminar_archivo(archivo_path: str) -> bool:
    """Elimina un archivo del storage."""
    if not archivo_path:
        return False
    if _usar_supabase():
        try:
            if archivo_path.startswith("http"):
                ruta_url = urlparse(archivo_path).path
                marcador = f"/{BUCKET}/"
                nombre = ruta_url.split(marcador, 1)[1] if marcador in ruta_url else ruta_url.rsplit("/", 1)[-1]
            else:
                nombre = archivo_path
            _solicitar_storage("DELETE", f"object/{BUCKET}", {"prefixes": [nombre]})
            logger.info(f"[storage] Archivo eliminado de Supabase: {nombre}")
            return True
        except Exception as e:
            logger.error(f"[storage] Error eliminando de Supabase: {e}")
            return False
    # Local
    try:
        os.remove(archivo_path)
        return True
    except OSError:
        return False


def generar_url_firmada(archivo_path: str, expires_in: int = SIGNED_URL_TTL_SECONDS) -> str:
    """
    Genera una URL temporal para descargar archivos privados de Supabase.
    Para archivos locales o URLs públicas legacy, retorna el mismo path/URL.
    """
    if not archivo_path or archivo_path.startswith("http") or not _usar_supabase():
        return archivo_path

    ruta_api = f"object/sign/{BUCKET}/{quote(archivo_path, safe='/')}"
    respuesta = _solicitar_storage("POST", ruta_api, {"expiresIn": expires_in})
    signed = json.loads(respuesta.decode("utf-8"))
    url = signed.get("signedURL") or signed.get("signedUrl") or signed.get("signed_url")
    if url and not url.startswith("http"):
        base = settings.SUPABASE_URL.rstrip("/")
        if url.startswith("/storage/v1/"):
            url = base + url
        else:
            url = f"{base}/storage/v1/{url.lstrip('/')}"
    return url


def _mime(ext: str) -> str:
    mt, _ = mimetypes.guess_type(f"file{ext}")
    return mt or "application/octet-stream"
