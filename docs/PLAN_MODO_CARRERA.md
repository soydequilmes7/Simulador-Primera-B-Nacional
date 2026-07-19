# Plan de mejora — Modo Carrera

Estado al 19/07/2026, después de la tanda de fixes de ascenso/descenso,
"quedar libre" y nota estilo Sofascore.

## Dónde estamos parados

Lo que ya funciona:
- Progresión de división real (Primera C/B Metro → Nacional → Liga
  Profesional) con ascenso/descenso matemáticamente alcanzable.
- Curva de edad con pico 30-32 y declive proporcional al pico, retiro a
  los 40.
- Lesiones, convocatorias a selección, fichaje/préstamo con mezcla
  realista, y la posibilidad de quedar libre.
- Cadencia de 2 años, tabla de trayectoria con logos de torneo, nota de
  temporada.

Lo que todavía es limitado:
- Todo el fútbol sudamericano/argentino está cubierto; **no hay clubes
  europeos**.
- No hay historial visual (gráfico de evolución de OVR/nota a lo largo
  de la carrera) — solo la tabla fila por fila.
- Los clubes del exterior (fuera de Argentina) no tienen pirámide de
  ascenso/descenso modelada — quedan "planos" en su nivel inicial toda
  la carrera.
- No hay lesiones de largo plazo que crucen un período (una lesión grave
  a los 24 años no repercute en el período de los 26).
- Vocabulario de logros limitado: solo títulos de liga y debut en
  selección. No hay "Bota de Oro", "Mejor jugador de la liga", etc.

## Fase 1 — Pulido de lo que ya existe (corto plazo)

Prioridad alta, bajo esfuerzo relativo:

1. **Historial de ascensos/descensos en el resumen del jugador**, no solo
   como badge puntual en la fila (ej. "3 ascensos, 1 descenso en la
   carrera" en algún lado visible de la tarjeta).
2. **Gráfico de evolución de OVR** a lo largo de la carrera (línea simple,
   un punto por período) — hoy solo se puede inferir mirando la columna
   OVR de la tabla fila por fila.
3. **Lesiones de arrastre**: una lesión grave debería dejar una secuela
   liviana (ej. -2 al crecimiento) en el período siguiente, no solo en el
   que ocurrió — hoy el impacto es puntual y desaparece completamente al
   período siguiente.
4. **Más variedad de logros** en la vitrina: goleador de la liga, mejor
   jugador de la temporada (nota más alta del año en su categoría), 100/200
   partidos con un club, etc. — hoy solo hay títulos de liga y debut en
   selección.
5. **Sonido/vibración de feedback** en fichajes y decisiones (Vibration
   API en mobile, algún sonido corto) — lo que mencioné como idea menor.

## Fase 2 — Clubes europeos (lo que pediste para el futuro)

Esto es más laborioso porque no es solo agregar entradas a
`CARRERA_CLUBES` — hay que decidir alcance:

**Qué necesito de tu lado:**
- **Escudos**: hoy todo sale de `public/escudos/`, que solo tiene clubes
  sudamericanos (para Libertadores/Sudamericana). Para Europa hace falta
  cargar escudos nuevos (LaLiga, Premier, Serie A, Bundesliga, Ligue 1
  como mínimo, o las 5 grandes si querés arrancar ahí) y decidir la
  convención de nombres de archivo (mismo criterio `slugifyEquipo` que ya
  usa el resto del simulador, para no repetir el problema de nombres
  duplicados que ya arreglamos una vez).
- **Logos de torneo**: `public/logos-torneos/` no tiene ninguna liga
  europea todavía. Sin logo, el club se muestra sin badge de liga (como
  ya pasa con Bolivia/Chile/Paraguay/Perú/Uruguay/Venezuela ahora).
- **Niveles de club**: voy a necesitar armar una tabla de niveles
  realista por liga (similar a como hice con Argentina: River 92, Boca
  90, etc.) — puedo estimarlos por posición en tabla/prestigio histórico
  si me confirmás qué ligas cubrir primero.

**Decisiones de diseño a tomar:**
- ¿Europa es solo destino de fichaje/préstamo a mitad de carrera (como
  hoy Brasil/Colombia/Ecuador), o también querés que un jugador pueda
  *empezar* la cantera en Europa? Si es lo segundo, hay que pensar el
  paso adicional de "visa/adaptación" que hoy no existe para nadie.
- ¿Modelo la pirámide europea (segunda división, ascenso/descenso) como
  hice con Argentina, o la dejo plana como el resto del exterior por
  ahora? Modelarla bien implica repetir el trabajo de
  `CARRERA_CENTRO_DIVISION` por cada liga.
- Con más ligas, el pool de ofertas (`carreraObtenerOfertasPrestamo`) va
  a necesitar pesos por región/idioma (hoy es puramente por cercanía de
  nivel) para que no te aparezcan ofertas de Bolivia y Alemania mezcladas
  sin ningún criterio.

Sugerencia de alcance inicial: arrancar con **LaLiga + Serie A** (las dos
ligas con más quilombo entre potencia/quiebre de club, buen contraste de
niveles) antes de las 5 grandes completas, para probar el modelo con
menos volumen de datos que cargar.

## Fase 3 — Profundidad de simulación (mediano plazo)

- **Comparativas**: cómo termina un jugador comparado con la media
  histórica de todas las carreras jugadas (esto ya necesitaría guardar
  carreras completadas en algún lado — hoy todo es en memoria del
  navegador, se pierde al cerrar).
- **Historial de carreras guardadas**: poder ver carreras anteriores sin
  perderlas al empezar una nueva (hoy `carreraReiniciarEstado()` las
  borra sin dejar rastro).
- **Reputación/prestigio del jugador** afectando ofertas: hoy las ofertas
  solo miran nivel actual; un jugador con muchos títulos debería tener
  mejores ofertas a nivel general similar que uno sin nada en la vitrina.

## Fase 4 — Base técnica (si Modo Carrera crece)

- Si sumás guardado de carreras (Fase 3), va a necesitar tocar
  `db/repository.py`/Supabase igual que el resto del simulador — separado
  del resto de las tablas de liga, sin mezclarse con `club_ratings` ni el
  ELO de Montilla que dejamos pendiente de reconciliar.
- Repo cleanup pendiente (los ~32 archivos candidatos a borrar que
  quedaron de sesiones anteriores) — no bloquea nada de Carrera, pero
  conviene no seguir postergándolo indefinidamente.

## Orden sugerido

1. Fase 1 completa (pulido) — rápido, mejora la sensación general sin
   arriesgar nada de lo que ya armamos.
2. Fase 2 arrancando con 1-2 ligas europeas como prueba de concepto.
3. Fase 3 solo si el modo empieza a tener uso real y vale la pena
   invertir en persistencia.
4. Fase 4 en paralelo, sin apuro, cuando toques Supabase por otra razón.

¿Arranco por la Fase 1, o preferís saltar directo a probar Europa con
LaLiga como piloto?
