"""Constantes compartidas entre routers."""
import os

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads/resultados")

ALLOWED_EXTENSIONS = {
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp",
    ".tiff", ".tif", ".doc", ".docx", ".xls", ".xlsx", ".txt",
    ".zip", ".rar", ".dcm",
}
