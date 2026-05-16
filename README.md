# MediPortal

Portal de autogestión médica. Permite a pacientes gestionar turnos y ver resultados, y al staff administrar todo desde un panel dedicado.

---

## Instalación local

### 1. Clonar/descomprimir el proyecto

```bash
cd mediportal
```

### 2. Crear entorno virtual e instalar dependencias

```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Configurar base de datos

Para produccion por cliente, crear un proyecto Supabase y configurar:

```bash
DATABASE_URL=postgresql+psycopg2://postgres.<project-ref>:<password>@aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_KEY=<service-role-o-anon-key-segun-uso>
```

### 4. Inicializar schema/catalogos

```bash
python init_db.py
```

Esto corre las migrations SQL y carga configuracion/catalogos base.

### 5. Provisionar un cliente nuevo

```bash
python setup_cliente.py --clinica "Centro Medico Norte" --slug centro-norte --admin-email admin@centronorte.com --admin-password "una-clave-segura-123"
```

### 6. Correr el servidor

```bash
uvicorn main:app --reload
```

Abrí el navegador en: **http://localhost:8000**

---

## Credenciales de acceso

El admin inicial se define por cliente con `setup_cliente.py` usando `--admin-email` y `--admin-password`.
No hay pacientes demo en el flujo de provisioning de Supabase.

---

## Estructura del proyecto

```
mediportal/
├── main.py                  # App FastAPI, rutas montadas
├── database.py              # Configuración SQLite + SQLAlchemy
├── models.py                # Modelos ORM
├── auth.py                  # JWT + hashing de contraseñas
├── init_db.py               # Script de inicialización con datos demo
├── requirements.txt
├── routers/
│   ├── auth_router.py       # Login, logout, cambiar contraseña
│   ├── paciente_router.py   # Portal del paciente
│   └── admin_router.py      # Panel administrativo
├── templates/
│   ├── base.html            # Shell HTML base (tema, scripts)
│   ├── base_paciente.html   # Layout portal paciente (navbar top)
│   ├── base_admin.html      # Layout admin (sidebar)
│   ├── login.html
│   ├── cambiar_password.html
│   ├── paciente/
│   │   ├── turnos.html
│   │   └── resultados.html
│   └── admin/
│       ├── dashboard.html
│       ├── pacientes.html
│       ├── turnos.html
│       └── resultados.html
├── static/
└── uploads/
    └── resultados/          # PDFs subidos por el staff
```

---

## Funcionalidades actuales

**Portal paciente:**
- Login con DNI + contraseña
- Cambio forzado de contraseña en primer ingreso
- Ver, solicitar y cancelar turnos
- Ver y descargar resultados (PDFs)
- Light/Dark mode con persistencia

**Panel admin:**
- Dashboard con estadísticas
- Alta, baja y búsqueda de pacientes
- Gestión de turnos (crear, filtrar, cambiar estado)
- Subir resultados en PDF por paciente
- Light/Dark mode

---

## Para produccion
- Cambiar `SECRET_KEY` por cliente en `.env`
- Usar `DATABASE_URL` de Supabase/PostgreSQL por cliente
- Ejecutar `setup_cliente.py` una vez por deploy/cliente
- Mover resultados PDF a Supabase Storage si el filesystem del host no es persistente
