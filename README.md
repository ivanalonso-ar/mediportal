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

### Probar dos clínicas en una misma instancia

Cada clínica usa una fila de `configuracion_clinica`; los registros operativos quedan asociados por `clinica_id`. Para probar una segunda clínica en Supabase, primero inicializá el esquema con `python init_db.py` y luego provisioná SegundoPortal:

```bash
python setup_cliente.py \
  --clinica "SegundoPortal" \
  --slug segundoportal \
  --color-primario "#16a34a" \
  --admin-email admin@segundoportal.example \
  --admin-password "<clave-segura-de-12-o-mas-caracteres>" \
  --paciente-dni 30111222 \
  --paciente-password "<clave-de-prueba>" \
  --paciente-nombre Ana \
  --paciente-apellido Verde \
  --paciente-email paciente@segundoportal.example
```

La inicialización carga catálogos y profesionales de ejemplo dentro de esa clínica. El DNI de muestra puede repetirse en MediPortal porque la unicidad se aplica dentro de cada clínica.

En desarrollo, abrí `/login?clinica=mediportal` o `/login?clinica=segundoportal`. Para cambiar un matiz desde el SQL Editor de Supabase, alcanza con actualizar el color principal; la paleta de acentos se deriva automáticamente:

```sql
update configuracion_clinica
set color_primario = '#22c55e'
where slug = 'segundoportal';
```

Las migraciones agregan `clinica_id`, asignan los datos actuales a MediPortal y activan políticas RLS usando el contexto transaccional `app.clinica_id`. La aplicación también filtra las consultas ORM por clínica. Para que PostgreSQL aplique además RLS a la conexión de la app, el rol de `DATABASE_URL` no debe tener `BYPASSRLS`; verificá el rol configurado en Supabase antes de usarlo en producción.

En una base local nueva de SQLite: `python init_db.py` crea MediPortal y `setup_cliente.py` provisiona la segunda clínica sin conectarse a Supabase.

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

# Producción (Render)

Deploy como **Web Service** en Render:

- **Build:** `pip install -r requirements.txt`  
  (Opcional si cambiás estilos: `npm ci && npm run build:css` — el CSS compilado va en `static/css/app.css`)
- **Start:** `uvicorn main:app --host 0.0.0.0 --port $PORT`

Variables de entorno: `DATABASE_URL`, `SECRET_KEY`, `APP_URL` (URL pública de Render), y opcionalmente `SUPABASE_URL` / `SUPABASE_KEY` para Storage.

**Rendimiento DB:** con el **transaction pooler** (puerto `6543`, habitual en Render) cada clic abre una conexión a Supabase; la app usa **Turbo Frame** para no recargar CSS/JS en cada navegación y reduce consultas por página.

Recomendaciones:
- PostgreSQL/Supabase (migraciones en `migrations/`)
- HTTPS (Render lo provee)
- SECRET_KEY única por cliente
- Supabase Storage para PDFs/informes (el disco local en Render no es persistente)
- Backups automáticos en Supabase
