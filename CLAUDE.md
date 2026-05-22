# MediPortal — Instrucciones para Claude Code

## Qué es este proyecto
SaaS de gestión médica para clínicas y centros de salud.
Módulos principales: gestión de pacientes, turnos, carga de resultados, portal de autogestión para pacientes.

## Stack
- **Backend:** Python con FastAPI
- **Templates:** Jinja2 (HTML server-side rendering)
- **Base de datos:** Supabase (PostgreSQL)
- **Auth:** Manejo propio en `auth.py`
- **Assets:** `/static/` para CSS/JS, `/uploads/` para archivos subidos por usuarios

## Estructura del proyecto
```
mediportal/
├── routers/        # Un archivo por módulo (pacientes, turnos, resultados, etc.)
├── templates/      # HTML con Jinja2
├── static/         # CSS, JS, imágenes
├── uploads/        # Archivos subidos (resultados, documentos)
├── main.py         # Entry point, registro de routers
├── models.py       # Modelos Pydantic y estructuras de datos
├── auth.py         # Lógica de autenticación y sesiones
└── database.py     # Conexión y helpers de Supabase
```

## Comandos
- **Correr local:** `uvicorn main:app --reload`
- **Puerto por defecto:** 8000

## Credenciales y entorno
- Todas las credenciales van en `.env`, nunca hardcodeadas
- Variables de Supabase: `SUPABASE_URL`, `SUPABASE_KEY`
- El archivo `.env` nunca se toca ni se muestra en respuestas

## Convenciones de código

### General
- Código y comentarios en español (es un proyecto local argentino)
- Sin over-engineering: soluciones simples y directas
- No crear archivos nuevos sin pedirlo explícitamente
- No refactorizar código que no está relacionado con el fix pedido

### FastAPI / Routers
- Cada módulo tiene su propio archivo en `/routers/`
- Los routers se registran en `main.py`
- Usar `HTTPException` para errores HTTP con códigos correctos (400, 401, 403, 404, 500)
- Dependencias de autenticación se importan desde `auth.py`

### Base de datos (Supabase)
- Toda interacción con la base de datos pasa por `database.py`
- Antes de modificar una query SQL, explicar por qué el cambio es necesario
- Los errores de Supabase siempre se loguean antes de retornar una respuesta de error
- No hacer queries directas fuera de `database.py` salvo casos excepcionales justificados
- Datos sensibles de pacientes (DNI, historial, resultados) nunca se loguean en consola

### Templates Jinja2
- Los templates están en `/templates/`
- Usar bloques `{% block %}` para herencia de templates base
- Variables del contexto siempre documentadas arriba del render en el router

### Seguridad (crítico — es un sistema médico)
- Siempre verificar que el usuario autenticado tiene permiso para ver/editar el recurso solicitado
- No exponer IDs internos de pacientes en URLs sin validación previa
- Los archivos en `/uploads/` solo accesibles por usuarios autorizados
- Nunca devolver datos de un paciente a un usuario de otra clínica

### Archivos subidos
- Uploads en `/uploads/`, organizados por paciente o por tipo
- Validar tipo y tamaño de archivo antes de guardar
- No eliminar archivos de `/uploads/` sin pedirlo explícitamente

## Comportamiento esperado al hacer cambios
1. Leer el archivo afectado antes de modificarlo
2. Hacer solo el cambio pedido, sin tocar lógica no relacionada
3. Si el fix puede romper otra parte del sistema, advertirlo antes de aplicarlo
4. Pedir confirmación antes de modificar `database.py`, `auth.py` o `models.py`
5. Los tests los hace el desarrollador manualmente — no generar tests automáticos salvo que se pidan

## Contexto del dominio médico
- **Paciente:** persona registrada con DNI, datos personales, historial
- **Turno:** cita agendada entre paciente y profesional, con fecha/hora/estado
- **Resultado:** archivo o dato cargado por el profesional asociado a un paciente
- **Portal de autogestión:** vista del paciente para ver sus turnos y resultados sin intervención del staff
- **Clínica:** entidad que agrupa profesionales y pacientes (multitenancy)
