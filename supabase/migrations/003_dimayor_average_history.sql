-- Tabla de promedios de Liga BetPlay Dimayor (Colombia): puntos y
-- partidos de los últimos ~3 años (2024 + 2025 completos, el año en
-- curso se suma aparte desde matches/standings), usados para calcular
-- el promedio puntos/partido que decide el descenso. Mismo patrón que
-- lpf_average_history (001_initial_schema.sql), pero SIN el sistema
-- doble de descenso de Argentina: en Colombia descienden directo los
-- 2 equipos con peor promedio, no hay "peor de la tabla anual" aparte.
create table if not exists dimayor_average_history (
    id bigserial primary key,
    season_id bigint not null references seasons(id) on delete cascade,
    team_id bigint not null references teams(id),
    puntos_historicos integer not null,
    partidos_historicos integer not null,
    unique (season_id, team_id)
);
