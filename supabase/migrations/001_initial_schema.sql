create table if not exists competitions (
    slug text primary key,
    name text not null
);

create table if not exists seasons (
    id bigserial primary key,
    competition_slug text not null references competitions(slug) on delete cascade,
    name text not null,
    year integer,
    active boolean not null default true,
    unique (competition_slug, name)
);

create table if not exists teams (
    id bigserial primary key,
    name text not null unique
);

create table if not exists team_aliases (
    id bigserial primary key,
    team_id bigint not null references teams(id) on delete cascade,
    competition_slug text references competitions(slug) on delete cascade,
    alias text not null,
    source text not null default 'manual',
    unique (competition_slug, alias)
);

create table if not exists matches (
    id bigserial primary key,
    competition_slug text not null references competitions(slug) on delete cascade,
    season_id bigint not null references seasons(id) on delete cascade,
    fecha text,
    jornada integer,
    equipo_local_id bigint not null references teams(id),
    equipo_visitante_id bigint not null references teams(id),
    goles_local integer,
    goles_visitante integer,
    status text not null check (status in ('pending', 'played')),
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (competition_slug, season_id, jornada, equipo_local_id, equipo_visitante_id)
);

create table if not exists standings (
    id bigserial primary key,
    competition_slug text not null references competitions(slug) on delete cascade,
    season_id bigint not null references seasons(id) on delete cascade,
    zona text not null,
    posicion integer not null,
    team_id bigint not null references teams(id),
    partidos_jugados integer not null default 0,
    ganados integer not null default 0,
    empatados integer not null default 0,
    perdidos integer not null default 0,
    gf integer not null default 0,
    gc integer not null default 0,
    dg integer not null default 0,
    puntos integer not null default 0,
    updated_at timestamptz not null default now(),
    unique (competition_slug, season_id, team_id)
);

create table if not exists players (
    id bigserial primary key,
    name text not null,
    unique (name)
);

create table if not exists scorer_totals (
    id bigserial primary key,
    competition_slug text not null references competitions(slug) on delete cascade,
    season_id bigint not null references seasons(id) on delete cascade,
    player_id bigint not null references players(id) on delete cascade,
    team_id bigint not null references teams(id),
    goles integer not null default 0,
    updated_at timestamptz not null default now(),
    unique (competition_slug, season_id, player_id, team_id)
);

create table if not exists lpf_average_history (
    id bigserial primary key,
    season_id bigint not null references seasons(id) on delete cascade,
    team_id bigint not null references teams(id),
    puntos_historicos integer not null,
    partidos_historicos integer not null,
    unique (season_id, team_id)
);

create table if not exists cup_matches (
    id bigserial primary key,
    competition_slug text not null references competitions(slug) on delete cascade,
    season_id bigint not null references seasons(id) on delete cascade,
    ronda text not null,
    llave integer not null,
    equipo_local_id bigint references teams(id),
    equipo_visitante_id bigint references teams(id),
    goles_local integer,
    goles_visitante integer,
    ganador_id bigint references teams(id),
    updated_at timestamptz not null default now(),
    unique (competition_slug, season_id, ronda, llave)
);

create table if not exists update_runs (
    id bigserial primary key,
    competition_slug text not null references competitions(slug) on delete cascade,
    season_id bigint references seasons(id) on delete set null,
    started_at timestamptz not null default now(),
    partidos_cargados jsonb not null default '[]'::jsonb,
    sin_matchear jsonb not null default '[]'::jsonb,
    simulacion_corrida boolean not null default false,
    metadata jsonb not null default '{}'::jsonb
);

create table if not exists simulation_outputs (
    key text primary key,
    competition_slug text references competitions(slug) on delete cascade,
    season_id bigint references seasons(id) on delete set null,
    n_simulaciones integer,
    payload jsonb not null,
    generated_at timestamptz not null default now()
);

create index if not exists idx_matches_comp_status
    on matches (competition_slug, season_id, status, jornada);

create index if not exists idx_standings_comp_zone
    on standings (competition_slug, season_id, zona, posicion);
