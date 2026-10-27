-- Asocia un hostname propio a cada clínica para resolver el tenant desde la URL.
alter table public.configuracion_clinica
    add column if not exists dominio varchar(253);

create unique index if not exists uq_configuracion_clinica_dominio
    on public.configuracion_clinica (lower(dominio))
    where dominio is not null;
