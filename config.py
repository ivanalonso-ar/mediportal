"""
Configuración central de la aplicación.
Lee variables desde el archivo .env en la raíz del proyecto.
"""
import os
from pathlib import Path

# Cargar .env manualmente (sin dependencia de python-dotenv)
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


class Settings:
    # Seguridad
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-insecure-key-cambiar")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 horas

    # App
    APP_NAME: str = os.getenv("APP_NAME", "MediPortal")
    APP_URL: str = os.getenv("APP_URL", "http://localhost:8000")

    # Email
    MAIL_ENABLED: bool = os.getenv("MAIL_ENABLED", "false").lower() == "true"
    MAIL_FROM: str = os.getenv("MAIL_FROM", "noreply@mediportal.com")
    MAIL_FROM_NAME: str = os.getenv("MAIL_FROM_NAME", "MediPortal")
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")


settings = Settings()
