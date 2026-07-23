# Plan de implementación — Modo DT (Director Técnico)

Estado al 23/07/2026. Arranque del proyecto: todavía no hay nada en
producción, esto define el orden de construcción del MVP.

## Idea central

El usuario no controla un jugador (eso ya existe en Modo Carrera): controla
un **club**, toma decisiones de entrenador y construye una carrera como DT.
Presentación cinematográfica (portadas, eventos, resúmenes) en vez de
tablas — mismo lenguaje visual que ya usa Modo Carrera para las noticias
de fin de temporada.

## Decisión de arquitectura

Módulo nuevo y aislado: `manager_mode/` (backend) + página propia en el
frontend (sin tocar `index.html`/`template.html` hasta que esté listo para
integrarse). Se **reutiliza** el motor de simulación de partidos existente
(`modelos/motor_vectorizado.simular_partido_simple`, Dixon-Coles + shock
Gamma) en vez de reimplementarlo — la identidad táctica del DT actúa como
modificador sobre los ratings de ataque/defensa del club, no como un motor
nuevo.

Capas (Clean Architecture):
- **Dominio** (`manager_mode/domain.py`): entidades puras sin IO —
  `Entrenador`, `IdentidadTactica`, `ObjetivoTemporada`, `Contrato`.
- **Servicios** (`manager_mode/match_service.py`, próximos:
  `events_service.py`, `dirigencia_service.py`): orquestan el dominio y
  el motor de simulación. Un servicio, una responsabilidad (SRP).
- **Persistencia**: se define en una fase posterior — arrancamos con
  estado en memoria/JSON viajando browser↔servidor, igual que el modo
  shadow de Modo Temporada, para no acoplar a Supabase antes de validar
  el diseño.

## Fase 0 — Núcleo (MVP actual)

1. `IdentidadTactica`: enum con las 4 filosofías (Pragmático, Ofensivo,
   Formador, Motivador), cada una con modificadores sobre
   ataque/defensa/juveniles/moral.
2. `Entrenador`: entidad con reputación, contrato actual, historial de
   clubes, récord (PJ/PG/PE/PP), títulos.
3. `PartidoDTService.simular_partido(...)`: aplica los modificadores de
   `IdentidadTactica` sobre los ratings de ataque/defensa del club y
   delega en el motor vectorizado existente para el resultado.
4. Tests unitarios de dominio + servicio (happy path + edge cases:
   identidad sin modificador, contrato vencido, etc.).

## Fase 1 — Sistema de eventos y noticias

- Máquina de estados simple: evento → opciones → efectos sobre
  variables (confianza, hinchada, vestuario, presupuesto).
- Generador de noticias de fin de temporada, mismo patrón que las
  portadas de Modo Carrera.

## Fase 2 — Dirigencia y ofertas

- Objetivos por club (ej. River: salir campeón / semifinal Libertadores;
  Quilmes: ascender / reducir deuda) y evaluación de continuidad.
- Pool de 4 ofertas de club al finalizar cada temporada, ponderado por
  reputación del DT (igual criterio que el pool de fichajes de Modo
  Carrera, pero del lado club→DT en vez de club→jugador).

## Fase 3 — Frontend cinematográfico

- Pantallas: intro (país/división/nombre/identidad), hub principal
  (tarjeta de DT), previa de partido, resumen de partido, fin de
  temporada, ofertas.
- Reutiliza componentes visuales existentes (glow, tarjetas con
  profundidad) donde aplique, sin copiar contenido de otros juegos.

## Fase 4 — Integración

- Endpoints `/api/dt/...` en `api/index.py`, sin tocar los existentes.
- Link desde el menú principal hacia la nueva sección.
- Recién acá se evalúa persistencia real en Supabase (tabla separada,
  sin mezclar con `club_ratings` ni con el ELO de Montilla pendiente de
  reconciliar).

## Orden sugerido

Fase 0 (este mensaje) → validar con Pablo → Fase 1 → Fase 2 → Fase 3 en
paralelo con 1/2 si el diseño visual está definido → Fase 4 al final.
