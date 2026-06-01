-- Permite el estado 'ausente' usado por el job de expiración automática y el panel admin.

alter table turnos drop constraint if exists turnos_estado_chk;

alter table turnos add constraint turnos_estado_chk
    check (estado in ('pendiente', 'confirmado', 'cancelado', 'completado', 'ausente'));
