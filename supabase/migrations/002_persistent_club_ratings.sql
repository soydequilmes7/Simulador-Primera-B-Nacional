create table if not exists club_ratings (
    team_id bigint primary key references teams(id) on delete cascade,
    ataque_local double precision not null default 1.0,
    ataque_visitante double precision not null default 1.0,
    defensa_local double precision not null default 1.0,
    defensa_visitante double precision not null default 1.0,
    partidos_computados integer not null default 0,
    updated_at timestamptz not null default now(),
    constraint club_ratings_non_negative_partidos check (partidos_computados >= 0),
    constraint club_ratings_rangos_validos check (
        ataque_local > 0 and ataque_visitante > 0 and
        defensa_local > 0 and defensa_visitante > 0
    )
);

create table if not exists club_rating_events (
    id bigserial primary key,
    competition_slug text not null references competitions(slug) on delete cascade,
    season_id bigint not null references seasons(id) on delete cascade,
    event_key text not null,
    source text not null,
    jornada integer,
    equipo_local_id bigint not null references teams(id),
    equipo_visitante_id bigint not null references teams(id),
    goles_local integer not null,
    goles_visitante integer not null,
    expected_local double precision not null,
    expected_visitante double precision not null,
    rating_local_pre jsonb not null,
    rating_visitante_pre jsonb not null,
    rating_local_post jsonb not null,
    rating_visitante_post jsonb not null,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    unique (source, event_key)
);

create index if not exists idx_club_rating_events_comp_season
    on club_rating_events (competition_slug, season_id, created_at);
