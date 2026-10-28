-- Aísla los datos operativos por clínica y conserva todo lo existente en MediPortal.
insert into configuracion_clinica (nombre, slug, color_primario)
values ('MediPortal', 'mediportal', '#2563eb')
on conflict (slug) do nothing;

do $$
declare
    v_clinica_id integer;
    v_tabla text;
    v_tablas text[] := array[
        'pacientes', 'usuarios_staff', 'especialidades', 'obras_sociales',
        'profesionales_especialidades', 'turnos', 'turno_logs', 'resultados',
        'avisos', 'notificaciones', 'grupos_familiares', 'solicitudes_grupo', 'bonos'
    ];
begin
    select id into v_clinica_id
    from configuracion_clinica
    where slug = 'mediportal';

    foreach v_tabla in array v_tablas loop
        execute format('alter table %I add column if not exists clinica_id integer', v_tabla);
        execute format('update %I set clinica_id = $1 where clinica_id is null', v_tabla)
            using v_clinica_id;
        execute format('alter table %I alter column clinica_id set not null', v_tabla);

        if not exists (
            select 1 from pg_constraint
            where conname = v_tabla || '_clinica_id_fkey'
        ) then
            execute format(
                'alter table %I add constraint %I foreign key (clinica_id) references configuracion_clinica(id) on delete restrict',
                v_tabla, v_tabla || '_clinica_id_fkey'
            );
        end if;

        execute format('create index if not exists %I on %I (clinica_id)',
            'idx_' || v_tabla || '_clinica', v_tabla);

        execute format('alter table %I enable row level security', v_tabla);
        execute format('alter table %I force row level security', v_tabla);
        execute format('drop policy if exists mediportal_tenant_isolation on %I', v_tabla);
        execute format(
            'create policy mediportal_tenant_isolation on %I using (clinica_id = nullif(current_setting(''app.clinica_id'', true), '''')::integer) with check (clinica_id = nullif(current_setting(''app.clinica_id'', true), '''')::integer)',
            v_tabla
        );
    end loop;
end $$;

-- Los identificadores que deben ser únicos se vuelven únicos dentro de cada clínica.
alter table pacientes drop constraint if exists pacientes_dni_key;
create unique index if not exists uq_paciente_clinica_dni on pacientes (clinica_id, dni);

alter table usuarios_staff drop constraint if exists usuarios_staff_email_key;
create unique index if not exists uq_staff_clinica_email on usuarios_staff (clinica_id, email);

alter table especialidades drop constraint if exists especialidades_nombre_key;
create unique index if not exists uq_especialidad_clinica_nombre on especialidades (clinica_id, nombre);

alter table obras_sociales drop constraint if exists obras_sociales_nombre_key;
create unique index if not exists uq_obra_social_clinica_nombre on obras_sociales (clinica_id, nombre);

-- Un mismo profesional/horario puede existir en clínicas distintas.
drop index if exists uq_turno_profesional_activo;
drop index if exists idx_turno_slot_profesional;
create unique index idx_turno_slot_profesional
on turnos (clinica_id, fecha, hora, profesional)
where profesional is not null and profesional <> '' and estado in ('pendiente', 'confirmado');

-- Índices compuestos para las búsquedas más frecuentes dentro del tenant.
create index if not exists idx_turnos_clinica_fecha on turnos (clinica_id, fecha, hora);
create index if not exists idx_resultados_clinica_paciente on resultados (clinica_id, paciente_id);
create index if not exists idx_notificaciones_clinica_paciente on notificaciones (clinica_id, paciente_id);
