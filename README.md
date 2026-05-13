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

### 3. Inicializar la base de datos con datos de prueba

```bash
python init_db.py
```

Esto crea `mediportal.db` con usuarios y datos de ejemplo.

### 4. Correr el servidor

```bash
uvicorn main:app --reload
```

Abrí el navegador en: **http://localhost:8000**

---

## Credenciales de acceso

### Staff / Admin (tab "Staff / Admin" en el login)
| Email                        | Contraseña  | Rol          |
|------------------------------|-------------|--------------|
| admin@mediportal.com         | admin123    | Admin        |
| recepcion@mediportal.com     | recep123    | Recepción    |
| medico@mediportal.com        | medico123   | Profesional  |

### Pacientes (tab "Paciente" en el login, ingresar DNI)
| DNI       | Contraseña   | Nota                             |
|-----------|--------------|----------------------------------|
| 30000001  | paciente123  | Acceso directo                   |
| 35000002  | paciente123  | Debe cambiar contraseña (demo)   |
| 28000003  | paciente123  | Acceso directo                   |

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

## Para producción (próximos pasos)
- Cambiar `SECRET_KEY` en `auth.py`
- Migrar de SQLite a PostgreSQL (Supabase)
- Usar variables de entorno (`.env`)
- Deploy en Render
