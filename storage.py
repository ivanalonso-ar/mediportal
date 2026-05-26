"""
Servicio de almacenamiento de archivos.
Si SUPABASE_URL y SUPABASE_KEY están configurados, usa Supabase Storage.
Si no, guarda en filesystem local (solo para desarrollo).
"""
import os
import uuid
import logging
import mimetypes
from pathlib import Path
from config import settings

logger = logging.getLogger("mediportal.storage")

BUCKET = "resultados"
LOCAL_UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads/resultados")
SIGNED_URL_TTL_SECONDS = int(os.getenv("SIGNED_URL_TTL_SECONDS", "60"))


def _usar_supabase() -> bool:
    return bool(settings.SUPABASE_URL and settings.SUPABASE_KEY)


def subir_archivo(contenido: bytes, nombre_original: str, ext: str) -> tuple[str, str]:
    """
    Sube un archivo al storage.
    Retorna (archivo_path, archivo_nombre).
    - En Supabase: archivo_path es el path privado dentro del bucket.
    - En local: archivo_path es el path en disco.
    """
    nombre_unico = f"{uuid.uuid4().hex}{ext}"

    if _usar_supabase():
        try:
            from supabase import create_client
            client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
            client.storage.from_(BUCKET).upload(
                path=nombre_unico,
                file=contenido,
                file_options={"content-type": _mime(ext)}
            )
            logger.info(f"[storage] Archivo subido a Supabase: {nombre_unico}")
            return nombre_unico, nombre_original
        except Exception as e:
            logger.error(f"[storage] Error subiendo a Supabase: {e}")
            raise

    # Fallback: filesystem local
    os.makedirs(LOCAL_UPLOAD_DIR, exist_ok=True)
    path = os.path.join(LOCAL_UPLOAD_DIR, nombre_unico)
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
        from supabase import create_client
        client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        contenido = client.storage.from_(BUCKET).download(archivo_path)
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
            from supabase import create_client
            nombre = archivo_path.split("/")[-1] if archivo_path.startswith("http") else archivo_path
            client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
            client.storage.from_(BUCKET).remove([nombre])
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

    from supabase import create_client
    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    signed = client.storage.from_(BUCKET).create_signed_url(archivo_path, expires_in)
    return signed.get("signedURL") or signed.get("signedUrl") or signed.get("signed_url")


def _mime(ext: str) -> str:
    mt, _ = mimetypes.guess_type(f"file{ext}")
    return mt or "application/octet-stream"
