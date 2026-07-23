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

## Fase 0 — Núcleo (COMPLETA)

1. `IdentidadTactica`: enum con 5 filosofías (Pragmático, Ofensivo,
   Formador, Motivador, Revolucionario), cada una con modificadores
   sobre ataque/defensa/juveniles/moral.
2. `Entrenador`: entidad con reputación, contrato actual, historial de
   clubes, récord (PJ/PG/PE/PP), títulos, logros desbloqueados.
3. `PartidoDTService.simular_partido(...)`: aplica los modificadores de
   `IdentidadTactica` sobre los ratings de ataque/defensa del club y
   delega en el motor vectorizado existente para el resultado.
4. `CATALOGO_LOGROS`: catálogo estático de logros de carrera (Rey del
   Ascenso, Invicto, Leyenda, etc.), desbloqueo idempotente vía
   `Entrenador.desbloquear_logro(codigo)`.
5. Tests unitarios de dominio + servicio (happy path + edge cases).

## Fase 1 — Narrativa y eventos (en progreso)

**Decisión de diseño confirmada:** los textos (reacciones de prensa,
hinchada, vestuario, dirigencia; portadas) se generan con un banco de
frases fijas por categoría/intensidad **más** interpolación de
variables (`{club}`, `{rival}`, `{entrenador}`, `{racha}`) — sin
llamadas a la API de Claude en runtime. Sin costo ni latencia; la
variedad sale de combinar plantilla × contexto, no de generar texto
nuevo cada vez.

Hecho:
- `manager_mode/narrativa.py`: `NarrativaService` con `reaccion(tipo,
  intensidad, contexto)` y `portada(intensidad, contexto)`. Banco
  cubre las 4×3 combinaciones de `TipoReaccion` × `Intensidad`.

Falta (siguiente incremento):
- Ampliar el banco de frases (hoy 2-3 por combinación; para que no se
  note la repetición en una carrera larga conviene 8-10 por
  combinación antes de integrar al frontend).
- Motor de eventos: catálogo de eventos (viajes, vestuario, mercado,
  dirigencia, prensa, lesiones, promesas, sponsors, infraestructura,
  juveniles, clásicos, crisis, conflictos, selecciones, rumores,
  escándalos, clima, árbitros, hinchada) con 2-3 opciones cada uno y
  efectos sobre variables internas (moral, confianza, presupuesto).
- Conectar `NarrativaService` a los efectos del evento: cada opción
  elegida dispara una reacción de uno o más `TipoReaccion` según
  corresponda.

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
