# Hardcoded audit para SaaS/Supabase

Elementos detectados que no deben vivir fijos en codigo para un deploy por cliente:

- Base de datos: `database.py` tenia `sqlite:///./mediportal.db`.
- Catalogo medico: `horarios.py` tenia especialidades, profesionales por especialidad, turnos manana/tarde y slots.
- Obras sociales: `obras_sociales.py` tenia la lista completa en una constante.
- Configuracion clinica: nombre de app, URL publica, remitente visible, horarios, duracion de turno, politica de sobreturnos/particulares, aprobacion de pacientes y carpeta de resultados.
- Estados y tipos: estados de turno, tipo de turno, tipo de consulta, tipos de avisos y roles de staff. Quedaron como constraints/checks en SQL y defaults en codigo para validacion.
- Datos demo: `seed.py`, `debug_seed.py` y el viejo `init_db.py` creaban usuarios/pacientes/turnos con emails y passwords fijos.
- Archivos locales: uploads de resultados siguen en filesystem (`uploads/resultados`). Para SaaS multi-deploy conviene moverlos luego a Supabase Storage.
- Templates: labels y mensajes de UI siguen en codigo/templates. Si se necesita marca blanca completa, esos textos deberian pasar a una tabla de contenido o configuracion.

Tablas nuevas para reemplazar los hardcodes operativos:

- `configuracion_clinica`
- `especialidades`
- `obras_sociales`
- `profesionales_especialidades`

Los defaults actuales quedan solo como semilla inicial/fallback para poder crear una instancia nueva y luego administrarla desde DB.
