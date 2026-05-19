# MediPortal

Sistema SaaS de gestión médica orientado a clínicas y centros de salud.

Permite:
- gestión de pacientes,
- administración de turnos,
- carga de resultados,
- portal de autogestión para pacientes.

Stack principal:
- FastAPI
- SQLAlchemy
- PostgreSQL / Supabase
- Jinja2
- JWT Auth

---

# Instalación local

## 1. Crear entorno virtual

```bash
python -m venv venv
```

### Windows

```bash
venv\Scripts\activate
```

### Linux / Mac

```bash
source venv/bin/activate
```

---

## 2. Instalar dependencias

```bash
pip install -r requirements.txt
```

---

## 3. Configurar variables de entorno

```env
DATABASE_URL=postgresql+psycopg2://postgres.<project-ref>:<password>@aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require

SUPABASE_URL=https://<project-ref>.supabase.co

SUPABASE_KEY=<service-role-key>

SECRET_KEY=<secret>
```

---

## 4. Inicializar base de datos

```bash
python init_db.py
```

---

## 5. Provisionar clínica

```bash
python setup_cliente.py \
  --clinica "Centro Medico Norte" \
  --slug centro-norte \
  --admin-email admin@centronorte.com \
  --admin-password "una-clave-segura"
```

---

## 6. Ejecutar servidor

```bash
uvicorn main:app --reload
```

Abrir:

```txt
http://localhost:8000
```

---

# Estructura

```txt
mediportal/
├── routers/
├── templates/
├── static/
├── uploads/
├── main.py
├── models.py
├── auth.py
└── database.py
```

---

# Convenciones

- Mantener routers livianos
- Evitar lógica compleja en templates
- No modificar auth sin revisar flujo JWT
- No hardcodear clientes
- Todo cambio de schema debe tener migration

---

# Producción

Recomendaciones:
- PostgreSQL/Supabase
- HTTPS
- SECRET_KEY única por cliente
- Storage persistente para PDFs
- Backups automáticos

Actualmente los PDFs se almacenan localmente.
Para producción se recomienda Supabase Storage.