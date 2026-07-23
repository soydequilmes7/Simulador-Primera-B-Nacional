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
- `manager_mode/eventos.py`: catálogo de 45 eventos en 16 categorías
  (viajes, vestuario, mercado, dirigencia, prensa, lesiones, juveniles,
  sponsors, infraestructura, clásicos, crisis, selecciones, copas,
  rumores, árbitros/hinchada, y **Vida de Plantel** -- el costado
  humano/gracioso pedido por Pablo: peleas de pareja cruzadas, salidas
  de joda, cargadas, cábalas grupales). Cada evento tiene 2-3 opciones
  con efectos sobre `EstadoClub` (moral, confianza, hinchada, vestuario,
  presupuesto, reputación).
- `manager_mode/evento_service.py`: `EventoService` conecta el catálogo
  con `NarrativaService` -- elige un evento (opcionalmente por
  categoría), aplica los efectos de la opción elegida y devuelve la
  frase narrativa correspondiente (o None si la opción no dispara
  reacción pública).

Falta (siguiente incremento):
- Reputación/objetivo de temporada todavía no consumen los eventos --
  falta `EvaluadorDirigenciaService` (Fase 2) para que el estado del
  club influya en continuidad y ofertas.
- Ponderar también por momento de la temporada (Clásicos/Copas en
  fechas específicas, no al azar puro) -- hoy solo se pondera por
  identidad táctica.

## Fase 1 — cerrada

- Banco de frases ampliado (6-8 variantes por combinación
  tipo×intensidad en prensa/hinchada/vestuario/dirigencia).
- `PESOS_CATEGORIA_POR_IDENTIDAD` en `evento_service.py`: cada
  identidad táctica ve con más frecuencia ciertas categorías (Formador
  → Juveniles, Motivador → Vestuario/Vida de Plantel, Pragmático →
  Dirigencia, Ofensivo → Clásicos/Copas, Revolucionario →
  Rumores/Crisis/Vida de Plantel). Solo aplica cuando se elige sin
  categoría explícita.

## Fase 2 — Dirigencia y ofertas (en progreso)

Hecho:
- `manager_mode/dirigencia.py`: `CATALOGO_PERFILES_CLUB` con 7 clubes
  (River, Boca, Independiente, Quilmes, San Martín de Tucumán,
  Temperley, Instituto), cada uno con su pool de `TipoObjetivo` posibles
  y un nivel de `exigencia` (0.0-1.0).
- `generar_objetivos_temporada(perfil, rng, cantidad)`: elige objetivos
  del pool del club sin repetir.
- `EvaluadorDirigenciaService`: evalúa cada objetivo contra un
  `ResultadoTemporada` (posición final, título, ascenso/descenso,
  juveniles debutados, venta de figuras) y decide continuidad
  (`RENOVAR` / `EN_OBSERVACION` / `DESPEDIR`) combinando el % de
  objetivos cumplidos con la confianza acumulada de `EstadoClub` --
  un descenso en un club exigente (River, Boca, Independiente) es
  causal de despido automática, sin importar el resto.
- `aplicar_decision(entrenador, evaluacion)`: efectiviza la decisión
  sobre el `Entrenador` (renueva contrato / libera al DT / sin cambios).
- No todos los objetivos del brief son medibles con datos objetivos
  ("jugar con intensidad" es subjetivo) -- se modelaron solo los
  medibles; el resto queda como posible objetivo narrativo sin `tipo`
  asignado, evaluable a mano si hiciera falta más adelante.

Falta (siguiente incremento):
- Pool de 4 ofertas de club al finalizar cada temporada, ponderado por
  reputación del DT (igual criterio que el pool de fichajes de Modo
  Carrera, pero del lado club→DT en vez de club→jugador).
- Conectar `ResultadoTemporada` con datos reales de Modo Temporada
  (hoy se arma a mano para testear; en integración real debería salir
  de `season_engine`/`PromotionManager`).

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
