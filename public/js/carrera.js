/* =====================================================================
   MODO CARRERA — Lógica de la pestaña
   Módulo autocontenido: no toca variables ni funciones del simulador de
   ligas (setLiga() del index.html solo hace show/hide de #vista-carrera
   y llama a initCarrera() la primera vez que se abre la pestaña).
   ===================================================================== */

const CARRERA_STATE = {
  iniciado: false,
  jugador: {
    apellido: "",
    numero: 10,
    pierna: "derecha",
    pais: null,      // { nombre, iso2 }
    posicion: null,  // code, ej "MCD"
    club: null,      // { nombre, escudo, liga, nivel }
    clubDueño: null, // club "dueño del pase"; distinto de .club mientras está a préstamo
    enPrestamo: false,
    edad: null,
    atributos: null, // { ataque, defensa, fisico, general, potencial }
    adn: null,       // atributos ocultos (nunca se muestran en UI) — ver carreraGenerarADN
    reputacion: 0,   // 0-100, separada del OVR, la mueve el rendimiento real
    potencialEfectivo: null, // techo de crecimiento actual, puede subir/bajar (ver carreraActualizarPotencialEfectivo)
    // --- Fase 5 (§9-10): flags de hitos "primera vez" + continuidad en el club actual ---
    temporadasEnClubActual: 1, // usado para el hito de capitán (3+ temporadas seguidas en el mismo club)
    capitanEnClubActual: false,
    primerClubEuropeoHecho: false,
    continentalHecho: false,
    golHecho: false,
    tituloHecho: false,
    balonDeOroHecho: false,
  },
  ofertas: [],       // clubes ofrecidos en carrera-oferta (se fija al entrar a la pantalla)
  temporada: 0,      // temporadas jugadas
  historial: [],     // resumen de cada temporada jugada
  titulos: [],       // { temporada, edad, club, liga } — títulos ganados con el club actual
  hitos: [],         // { tipo:'seleccion', edad, pais } — debut en selección, etc.
  decision: null,    // { opciones:[{id,label,club,prestamo,dueñoNuevo}] } pendiente tras simular
  retirado: false    // true cuando el jugador llegó a CARRERA_EDAD_RETIRO
};

function carreraJugadorCompleto(){
  const j = CARRERA_STATE.jugador;
  return !!(j.apellido.trim() && j.pais && j.posicion);
}

/* ---------- Pantalla 1: inicio ---------- */
function carreraMostrarInicio(){
  document.getElementById("carrera-inicio").style.display = "";
  document.getElementById("carrera-identidad").style.display = "none";
  document.getElementById("carrera-oferta").style.display = "none";
  document.getElementById("carrera-dashboard").style.display = "none";
}

/* ---------- Pantalla 2: identidad ---------- */
function carreraMostrarIdentidad(){
  document.getElementById("carrera-inicio").style.display = "none";
  document.getElementById("carrera-identidad").style.display = "";
  document.getElementById("carrera-oferta").style.display = "none";
  document.getElementById("carrera-dashboard").style.display = "none";
  carreraRenderPaises("");
  carreraRenderPosiciones();
  carreraActualizarCamiseta();
  carreraActualizarBotonConfirmar();
}

function carreraActualizarCamiseta(){
  const j = CARRERA_STATE.jugador;
  document.getElementById("carrera-camiseta-apellido").textContent = j.apellido.trim() ? j.apellido.trim().toUpperCase() : "APELLIDO";
  document.getElementById("carrera-camiseta-numero").textContent = j.numero || "10";
}

function carreraRenderPaises(filtro){
  const cont = document.getElementById("carrera-lista-paises");
  const f = (filtro || "").trim().toLowerCase();
  const lista = CARRERA_PAISES.filter(([nombre]) => nombre.toLowerCase().includes(f));
  cont.innerHTML = lista.map(([nombre, iso2]) => {
    const activo = CARRERA_STATE.jugador.pais && CARRERA_STATE.jugador.pais.iso2 === iso2;
    return `<button type="button" class="carrera-pais-item${activo ? ' active' : ''}" data-iso2="${iso2}" data-nombre="${nombre}">
      <span class="carrera-pais-bandera">${carreraBandera(iso2)}</span><span>${nombre}</span>
    </button>`;
  }).join("");
  cont.querySelectorAll(".carrera-pais-item").forEach(btn => {
    btn.addEventListener("click", () => {
      CARRERA_STATE.jugador.pais = { nombre: btn.dataset.nombre, iso2: btn.dataset.iso2 };
      carreraRenderPaises(document.getElementById("carrera-input-pais").value);
      carreraActualizarBotonConfirmar();
    });
  });
}

function carreraRenderPosiciones(){
  const cancha = document.getElementById("carrera-cancha");
  cancha.innerHTML = CARRERA_POSICIONES.map(p => {
    const activo = CARRERA_STATE.jugador.posicion === p.code;
    return `<button type="button" class="carrera-pos-btn${activo ? ' active' : ''}" data-code="${p.code}"
      style="top:${p.top}%; left:${p.left}%;">${p.label}</button>`;
  }).join("");
  cancha.querySelectorAll(".carrera-pos-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      CARRERA_STATE.jugador.posicion = btn.dataset.code;
      carreraRenderPosiciones();
      carreraActualizarBotonConfirmar();
    });
  });
}

function carreraActualizarBotonConfirmar(){
  const btn = document.getElementById("btn-carrera-confirmar");
  btn.disabled = !carreraJugadorCompleto();
}

/* ---------- Pantalla 3: oferta de club (cantera) ---------- */
function carreraMostrarOferta(){
  document.getElementById("carrera-inicio").style.display = "none";
  document.getElementById("carrera-identidad").style.display = "none";
  document.getElementById("carrera-dashboard").style.display = "none";
  document.getElementById("carrera-oferta").style.display = "";
  CARRERA_STATE.ofertas = carreraObtenerOfertas(CARRERA_STATE.jugador.pais.iso2, 3);
  carreraRenderOferta();
}

function carreraRenderOferta(){
  const cont = document.getElementById("carrera-oferta-grid");
  cont.innerHTML = CARRERA_STATE.ofertas.map((club, i) => `
    <div class="carrera-oferta-card" style="animation-delay:${i * 70}ms">
      <img class="carrera-oferta-escudo" src="escudos/${club.escudo}" alt="" loading="lazy" onerror="this.style.visibility='hidden'">
      <h3>${club.nombre}</h3>
      <p class="carrera-oferta-liga">${club.liga}</p>
      <button type="button" class="btn-carrera-primary carrera-oferta-btn" data-i="${i}">Fichar</button>
    </div>`).join("");
  cont.querySelectorAll(".carrera-oferta-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const club = CARRERA_STATE.ofertas[+btn.dataset.i];
      const tarjeta = btn.closest(".carrera-oferta-card");
      // Feedback visual antes de saltar al dashboard: la tarjeta elegida
      // se agranda/ilumina y las demás se apagan, para que el fichaje se
      // sienta como una decisión en vez de un salto de pantalla seco.
      cont.querySelectorAll(".carrera-oferta-card").forEach(c => c.classList.add("carrera-oferta-card--descartada"));
      tarjeta.classList.remove("carrera-oferta-card--descartada");
      tarjeta.classList.add("carrera-oferta-card--elegida");
      setTimeout(() => carreraElegirClub(club), 420);
    });
  });
}

// Edad de arranque de la carrera: cantera, recién asomando a un club de
// ascenso (Primera C / B Metropolitana), todavía sin nada asegurado.
const CARRERA_EDAD_INICIAL = 16;
// Edad límite: la temporada jugada a esta edad es la última; después el
// jugador se retira. No hay forma de "seguir jugando hasta los 100".
const CARRERA_EDAD_RETIRO = 40;
// Edad a partir de la cual puede aparecer la oferta de "vuelta a casa": un
// regreso al fútbol del país de origen sobre el cierre de la carrera. Antes
// de esta edad no tiene sentido -- volver a casa a los 25 sería un paso
// atrás, no un cierre de ciclo. Ver carreraProbabilidadVueltaCasa.
const CARRERA_EDAD_VUELTA_CASA = 34;

function carreraElegirClub(club){
  // Copia propia del club: a partir de acá el club puede ascender/descender
  // (ver carreraAplicarAscensoDescenso) sin tocar el objeto original del
  // pool en CARRERA_CLUBES/CARRERA_STATE.ofertas, que debe quedar intacto
  // para que otras carreras futuras arranquen siempre igual.
  club = { ...club };
  CARRERA_STATE.jugador.club = club;
  CARRERA_STATE.jugador.clubDueño = club;
  CARRERA_STATE.jugador.enPrestamo = false;
  CARRERA_STATE.jugador.edad = CARRERA_EDAD_INICIAL;
  CARRERA_STATE.jugador.atributos = carreraGenerarAtributos(CARRERA_STATE.jugador.posicion);
  // ADN oculto (Fase 1 del rediseño): nunca se muestra en la UI. Define
  // techo real de potencial, edad de pico y las variables que van a
  // entrar en juego en las próximas fases (mercado, decadencia, lesiones).
  CARRERA_STATE.jugador.adn = carreraGenerarADN();
  // El techo de potencial ya no es fijo para siempre, y ahora es un sorteo
  // TOTALMENTE aleatorio entre 86 y 99 -- sin relación con el general
  // inicial. Así cualquier jugador, arranque como arranque, tiene chance
  // real de llegar a nivel elite si el rendimiento lo acompaña; lo que
  // decide si lo alcanza o no es cómo lo desarrollás, no el dado tirado
  // al crear el jugador.
  CARRERA_STATE.jugador.adn.potencialMax = 86 + Math.floor(Math.random() * 14);
  CARRERA_STATE.jugador.potencialEfectivo = CARRERA_STATE.jugador.atributos.potencial;
  // Reputación: arranca baja siempre (nadie es conocido a los 16 en cantera)
  // y desde acá la mueve el rendimiento real, no el nivel de club.
  CARRERA_STATE.jugador.reputacion = 5;
  // Edad de pico (prime): ahora sale del ADN (24-32, no un rango fijo
  // 30-32) para que la curva de carrera varíe jugador a jugador. Se deja
  // también en jugador.edadPico (alias plano) porque el motor de temporada
  // y el dashboard ya lo leen así.
  CARRERA_STATE.jugador.edadPico = CARRERA_STATE.jugador.adn.edadPico;
  CARRERA_STATE.jugador.picoGeneral = CARRERA_STATE.jugador.atributos.general;
  CARRERA_STATE.jugador.capasSeleccion = 0;
  CARRERA_STATE.jugador.golesSeleccion = 0;
  CARRERA_STATE.jugador.descartado = false;
  // Flags de hitos "primera vez" (Fase 5, §10) y contador de continuidad
  // en el club actual (usado para el hito de capitán).
  CARRERA_STATE.jugador.temporadasEnClubActual = 1;
  CARRERA_STATE.jugador.capitanEnClubActual = false;
  CARRERA_STATE.jugador.primerClubEuropeoHecho = false;
  CARRERA_STATE.jugador.continentalHecho = false;
  CARRERA_STATE.jugador.golHecho = false;
  CARRERA_STATE.jugador.tituloHecho = false;
  CARRERA_STATE.jugador.balonDeOroHecho = false;
  CARRERA_STATE.temporada = 0;
  CARRERA_STATE.historial = [];
  CARRERA_STATE.titulos = [];
  CARRERA_STATE.hitos = [];
  CARRERA_STATE.decision = null;
  CARRERA_STATE.retirado = false;
  carreraSimularTemporada();
}

// Ascenso/descenso real del club del jugador dentro de la pirámide
// argentina (Primera C/B Metropolitana -> Primera Nacional -> Liga
// Profesional). Hasta acá "Campeón"/"Descendió" eran solo texto narrativo:
// el club nunca cambiaba de división de verdad, por eso nunca se sentía
// un ascenso o un descenso real en la carrera. Se aplica sobre el objeto
// club del jugador (ya copiado aparte del pool, ver carreraElegirClub) y
// solo corre para clubes argentinos, que son los únicos con 3 escalones
// modelados -- los clubes del exterior no tienen ese dato y quedan igual.
const CARRERA_DIVISION_TIER = {
  "Primera C": 1, "B Metropolitana": 1,
  "Primera Nacional": 2,
  "Liga Profesional": 3,
};
const CARRERA_SIGUIENTE_LIGA = { 1: "Primera Nacional", 2: "Liga Profesional" };

// Copa Argentina: torneo de eliminación directa abierto a las 4 divisiones
// modeladas, así que a diferencia del campeonato de liga un club chico
// SÍ tiene chance real de dar la sorpresa (como pasa en la vida real). La
// probabilidad depende un poco del nivel pero mucho menos que el título
// de liga -- son pocos partidos de eliminación directa, no una temporada
// completa demostrando quién es mejor.
function carreraTirarCopaArgentina(club){
  if (!CARRERA_DIVISION_TIER[club.liga]) return false; // solo clubes argentinos
  const factorNivel = Math.max(0, club.nivel - 30) / 70; // ~0 a ~1
  const probabilidad = 0.015 + factorNivel * 0.045; // 1.5% a ~6%
  return Math.random() < probabilidad;
}

// Nivel "promedio esperado" de cada división: un club de nivel exactamente
// igual a esto es un candidato típico de mitad de tabla en su liga, uno
// bastante por encima pelea el título/ascenso, uno bastante por debajo
// pelea el descenso. Los clubes del exterior (sin entrada acá) usan su
// propio nivel como centro -- no tienen pirámide modelada, así que el
// resultado queda centrado en "mitad de tabla" siempre, sin sesgo.
//
// BUG que reportó Gonza: estos valores estaban puestos muy por encima del
// nivel real de los clubes que existen en el pool de cada división (ver
// CARRERA_CLUBES) -- el club MÁS FUERTE de Primera C tiene nivel 25, pero
// el centro estaba en 40; el de B Metro tiene nivel 28 contra un centro
// de 43; el de Nacional tiene nivel 43 contra un centro de 55. Como el
// resultado sale de (nivel_club - centro) + ruido(±20), y "Campeón"
// necesita ese total >= 18, NINGÚN club real de esas 3 divisiones podía
// llegar a "Campeón" ni con la mejor suerte posible -- y como el ascenso
// de división solo se dispara con "Campeón", esas divisiones quedaban
// con el ascenso prácticamente inalcanzable, y toda la trayectoria caía
// siempre entre "Mitad de tabla" y "Descendió" sin importar el nivel real
// del club. Ahora el centro es la media real de nivel de cada división
// (Liga Profesional ya estaba bien calibrada -- su rango real 44-92 sí
// deja "Campeón" alcanzable con el centro anterior, así que no se toca).
const CARRERA_CENTRO_DIVISION = {
  "Primera C": 22, "B Metropolitana": 26,
  "Primera Nacional": 36,
  "Liga Profesional": 72,
};

function carreraAplicarAscensoDescenso(club, resultadoClub){
  const tier = CARRERA_DIVISION_TIER[club.liga];
  if (!tier) return null; // club del exterior, sin pirámide modelada
  if (resultadoClub === "Campeón" && tier < 3) {
    const ligaNueva = CARRERA_SIGUIENTE_LIGA[tier];
    // El piso de nivel al ascender no puede superar el nivel real máximo
    // de la división de destino (ver CARRERA_CLUBES) -- antes tier 1
    // (Primera C/B Metro) tenía piso 52 contra un máximo real de 43 en
    // Primera Nacional, así que un recién ascendido arrancaba siendo
    // automáticamente el mejor equipo de toda la división. Ahora entra
    // cerca del piso de la nueva división, como corresponde a un recién
    // llegado, en vez de por encima de su techo.
    club.nivel = tier === 1 ? Math.max(club.nivel + 10, 30) : Math.max(club.nivel + 16, 62);
    club.liga = ligaNueva;
    return "ascenso";
  }
  if (resultadoClub === "Descendió" && tier > 1) {
    const ligaNueva = tier === 3 ? "Primera Nacional" : "Primera C";
    club.nivel = tier === 3 ? Math.min(club.nivel - 16, 58) : Math.min(club.nivel - 14, 46);
    club.liga = ligaNueva;
    return "descenso";
  }
  return null;
}

// Probabilidad de lesión por período (2 años) y su severidad. Una lesión
// leve casi no se nota; una grave te come casi todo el período y además
// atrasa el desarrollo (penalizacionCrecimiento), no solo los partidos.
const CARRERA_PROB_LESION = 0.07;
function carreraTirarLesion(){
  if (Math.random() >= CARRERA_PROB_LESION) return null;
  const roll = Math.random();
  if (roll < 0.50) {
    return { tipo: "leve", fraccionPerdida: 0.15 + Math.random() * 0.15, penalizacionCrecimiento: 0 };
  } else if (roll < 0.85) {
    return { tipo: "moderada", fraccionPerdida: 0.35 + Math.random() * 0.20, penalizacionCrecimiento: 1 };
  } else {
    return { tipo: "grave", fraccionPerdida: 0.65 + Math.random() * 0.25, penalizacionCrecimiento: 3 };
  }
}

// Selección nacional: por debajo de CARRERA_UMBRAL_SELECCION no hay chance
// (todavía no rinde para eso); por encima, la probabilidad de convocatoria
// ese período crece con el nivel general. Si es convocado, las presencias
// y goles con la selección son un extra sobre las stats de club, no las
// reemplazan -- se acumulan en j.capasSeleccion / j.golesSeleccion.
const CARRERA_UMBRAL_SELECCION = 66;
function carreraTirarConvocatoria(general, factorGol, ataque){
  if (general < CARRERA_UMBRAL_SELECCION) return null;
  const probabilidad = Math.min(0.75, (general - CARRERA_UMBRAL_SELECCION) * 0.035 + 0.08);
  if (Math.random() >= probabilidad) return null;
  const presencias = 2 + Math.floor(Math.random() * 9); // 2-10 partidos en el período
  const goles = Math.max(0, Math.round(presencias * factorGol * 0.6 * (ataque / 60) * (0.6 + Math.random() * 0.7)));
  return { presencias, goles };
}

/* ---------- Motor de temporada (resumen directo, simulación aparte) ---------- */
// La carrera avanza de a 2 años por click (edad +2 cada vez, como pediste),
// así que "temporada" acá es en realidad un bienio: el doble de partidos,
// y la curva de crecimiento/declive escalada a ese mismo período.
const CARRERA_PASO_EDAD = 2;

function carreraSimularTemporada(){
  const j = CARRERA_STATE.jugador;
  const club = j.club;
  const edadDeLaTemporada = j.edad;

  // Oportunidades: cuánto juega según la brecha entre su nivel y el del club.
  const diff = j.atributos.general - (club.nivel || 45);
  let chance = 45 + diff * 1.6;
  chance = Math.max(5, Math.min(95, chance));
  const PARTIDOS_TEMPORADA = 30 * CARRERA_PASO_EDAD;
  const ruidoMinutos = 0.7 + Math.random() * 0.5;
  let partidos = Math.round(PARTIDOS_TEMPORADA * (chance / 100) * ruidoMinutos);
  partidos = Math.max(0, Math.min(PARTIDOS_TEMPORADA, partidos));

  // Lesiones: cada período hay una chance de que una lesión le recorte
  // partidos (y, si es fuerte, también el desarrollo -- perder meses de
  // competencia/entrenamiento pesa más que solo los partidos perdidos).
  // No se modela para el período de retiro para abajo porque a esa altura
  // ya no hay curva de crecimiento que penalizar.
  const lesion = carreraTirarLesion();
  let penalizacionCrecimiento = 0;
  if (lesion) {
    partidos = Math.round(partidos * (1 - lesion.fraccionPerdida));
    penalizacionCrecimiento = lesion.penalizacionCrecimiento;
  }

  // Producción ofensiva según grupo de posición.
  let factorGol, factorAsist, grupoPosicion;
  if (CARRERA_GRUPOS_POSICION.delantero.includes(j.posicion)) { factorGol = 0.55; factorAsist = 0.18; grupoPosicion = "delantero"; }
  else if (CARRERA_GRUPOS_POSICION.medio.includes(j.posicion)) { factorGol = 0.22; factorAsist = 0.30; grupoPosicion = "medio"; }
  else if (CARRERA_GRUPOS_POSICION.defensor.includes(j.posicion)) { factorGol = 0.06; factorAsist = 0.10; grupoPosicion = "defensor"; }
  else { factorGol = 0.01; factorAsist = 0.02; grupoPosicion = "arquero"; }
  const ruidoGol = () => 0.6 + Math.random() * 0.7;
  const goles = Math.max(0, Math.round(partidos * factorGol * (j.atributos.ataque / 60) * ruidoGol()));
  const asistencias = Math.max(0, Math.round(partidos * factorAsist * (j.atributos.ataque / 60) * ruidoGol()));

  // Selección nacional: a partir de cierto nivel general empieza a haber
  // chance de convocatoria, creciente con el nivel. Las presencias/goles
  // de ese período se acumulan aparte de las del club (no las reemplazan).
  const convocatoria = carreraTirarConvocatoria(j.atributos.general, factorGol, j.atributos.ataque);
  const debutSeleccion = convocatoria && j.capasSeleccion === 0;
  if (convocatoria) {
    j.capasSeleccion += convocatoria.presencias;
    j.golesSeleccion += convocatoria.goles;
  }

  // Resultado del club (simulación aparte, sin fixture real).
  // OJO: el umbral tiene que ser RELATIVO al nivel esperado de la propia
  // división del club, no absoluto -- con umbrales absolutos (rollClub>=80
  // para "Campeón") un club de nivel 55 con variación máxima ±15 nunca
  // podía llegar a 80 aunque tuviera la mejor suerte posible, así que el
  // ascenso/descenso quedaba matemáticamente inalcanzable para casi
  // cualquier club fuera de los más fuertes de la Liga Profesional.
  const ligaDeLaTemporada = club.liga;
  const centroDivision = CARRERA_CENTRO_DIVISION[club.liga] ?? club.nivel;
  const rendimiento = (club.nivel - centroDivision) + (Math.random() * 40 - 20);
  let resultadoClub;
  if (rendimiento >= 18) resultadoClub = "Campeón";
  else if (rendimiento >= 8) resultadoClub = "Clasificó a copas internacionales";
  else if (rendimiento >= -8) resultadoClub = "Mitad de tabla";
  else if (rendimiento >= -18) resultadoClub = "Peleó el descenso";
  else resultadoClub = "Descendió";

  // Tier de la temporada (Fase 5, §9): se calcula ACÁ, antes de aplicar
  // ascenso/descenso más abajo, porque ese cambio muta club.liga para la
  // PRÓXIMA temporada -- los premios de esta temporada tienen que usar la
  // liga en la que de verdad se jugó.
  const tierTemporada = carreraObtenerTier(ligaDeLaTemporada);

  // Ascenso/descenso real de división (solo clubes argentinos, ver arriba).
  // Se aplica DESPUÉS de tirar el resultado de esta temporada -- el nivel
  // nuevo del club rige recién a partir de la próxima, no retroactivo.
  const cambioDivision = carreraAplicarAscensoDescenso(club, resultadoClub);

  // Progresión: antes del pico (edadPico, 30-32) crece si juega y todavía no
  // llegó al potencial. Desde el pico en adelante, declina en vez de crecer;
  // cuánto puede bajar depende de qué tan alto fue el pico -- un jugador
  // que llegó a 90 de general se mantiene arriba de piso más alto (~75-80)
  // que uno que llegó a 50 (~37-38), en proporción al pico, no en valor fijo.
  // Los rangos de crecimiento/declive están escalados x2 porque cada click
  // representa 2 años, no 1.
  const generalAntes = j.atributos.general;
  let generalDespues;
  if (edadDeLaTemporada < j.edadPico) {
    let crecimiento;
    if (partidos >= 36) crecimiento = Math.round(Math.random() * 6) + 2;
    else if (partidos >= 16) crecimiento = Math.round(Math.random() * 4) + 1;
    // Con pocos minutos igual entrena y crece un poco si es joven -- antes
    // esta rama podía dar crecimiento negativo, y como un juvenil recién
    // llegado a un club de nivel más alto casi no juega al principio
    // (ver "chance" arriba), la carrera quedaba prácticamente trabada sin
    // crecer nunca. Con muy pocos minutos y ya mayor sí puede estancarse.
    else crecimiento = edadDeLaTemporada <= 22 ? Math.round(Math.random() * 3) : Math.round(Math.random() * 2) - 1;
    crecimiento -= penalizacionCrecimiento;
    generalDespues = Math.max(1, Math.min(j.atributos.potencial, generalAntes + crecimiento));
    j.picoGeneral = Math.max(j.picoGeneral, generalDespues);
  } else {
    // Fase 3 del rediseño: la retención y la velocidad de caída ya no son
    // un rango fijo para todos -- salen de adn.velocidadDecadencia (0-100).
    // Un jugador con velocidadDecadencia baja retiene hasta 90% de su pico
    // y cae ~1 punto por bienio; uno con velocidadDecadencia alta retiene
    // solo 55% y cae hasta 4 puntos por bienio, antes incluso de sumar el
    // agravante de los bienios ya pasados desde el pico. El profesionalismo
    // amortigua la caída (cuida mejor el físico), igual que ya hace con el
    // potencial dinámico (ver carreraActualizarPotencialEfectivo).
    const retencion = 0.55 + (1 - j.adn.velocidadDecadencia / 100) * 0.35; // 55%-90% del pico
    const piso = Math.round(j.picoGeneral * retencion);
    const bieniosPasadoElPico = (edadDeLaTemporada - j.edadPico) / CARRERA_PASO_EDAD;
    let declive = 1 + (j.adn.velocidadDecadencia / 100) * 3 + Math.random() * 2 + bieniosPasadoElPico * 0.4;
    declive *= (1 - (j.adn.profesionalismo / 100) * 0.25);
    generalDespues = Math.max(piso, generalAntes - Math.round(declive));
  }
  j.atributos.general = generalDespues;

  // Nota de la temporada, estilo Sofascore. La versión anterior tenía un
  // problema de fondo: comparaba la producción contra una "expectativa"
  // calculada con la MISMA fórmula que los goles/asistencias (con el
  // mismo factor de ataque del jugador), así que en la práctica se
  // comparaba contra sí misma más ruido -- un jugador que casi no jugó
  // igual podía sacar una nota alta si el equipo salió campeón o si
  // progresó ese período, cosas que no tienen nada que ver con cómo jugó
  // él en cancha. Ahora: si jugó muy poco, la nota queda neutra (no hay
  // temporada real que calificar); si jugó, se mide gol+asistencia POR
  // PARTIDO contra un piso fijo por posición (independiente de su propio
  // ataque, para que mida de verdad sobre/bajo rendimiento del rol), y el
  // resultado del equipo pesa poco al lado de eso -- la progresión
  // personal no entra acá, es una cosa aparte del desarrollo del jugador.
  // Piso de producción "esperada" por posición: derivado de la MISMA
  // fórmula que genera goles/asistencias reales (factorGol/factorAsist a
  // ataque=60, con el ruido promedio de ruidoGol), no un número puesto a
  // ojo -- si no, un delantero "promedio para su rol" siempre puntuaba
  // mejor que un defensor "promedio para su rol" aunque los dos estén
  // rindiendo exactamente como se espera de su posición.
  const CARRERA_BASELINE_PRODUCCION = {
    delantero: (0.55 + 0.18 * 0.6) * 0.95,
    medio: (0.22 + 0.30 * 0.6) * 0.95,
    defensor: (0.06 + 0.10 * 0.6) * 0.95,
    arquero: (0.01 + 0.02 * 0.6) * 0.95,
  };
  // Se saca afuera del if/else para poder reusarlo también en el cálculo
  // de premios individuales (Fase 5, §9), que necesita el mismo baseline
  // "esperado por rol" que ya usa la nota de temporada.
  const baseline = CARRERA_BASELINE_PRODUCCION[grupoPosicion];
  let valoracion;
  if (partidos < 4) {
    valoracion = 5.0 + (Math.random() * 0.4 - 0.2);
  } else {
    const produccionPorPartido = (goles + asistencias * 0.6) / partidos;
    const bonoEquipo = {
      "Campeón": 0.5, "Clasificó a copas internacionales": 0.25,
      "Mitad de tabla": 0, "Peleó el descenso": -0.2, "Descendió": -0.4,
    }[resultadoClub] || 0;
    valoracion = 6.0 + (produccionPorPartido - baseline) * 4.5 + bonoEquipo
      + (partidos / PARTIDOS_TEMPORADA - 0.5) * 0.5
      + (Math.random() * 0.5 - 0.25);
  }
  valoracion = Math.round(Math.max(1, Math.min(10, valoracion)) * 10) / 10;

  // ADN: potencial dinámico y reputación (Fase 1 del rediseño). Se calculan
  // acá porque ya están disponibles todos los datos de la temporada
  // (valoración, partidos, resultado del club, lesión, convocatoria). La
  // lista de premios va vacía hasta que se implemente la Fase 5.
  carreraActualizarPotencialEfectivo(j, { valoracion, partidos, resultadoClub, lesion });
  j.atributos.potencial = j.potencialEfectivo;

  // Premios individuales de la temporada (Fase 5, §9): calculados por
  // tier, decisión confirmada. Se calculan antes de actualizar reputación
  // porque cada premio ganado alimenta un salto fuerte de reputación.
  const premiosTemporada = carreraCalcularPremios(
    j, { valoracion, goles, asistencias, partidos, resultadoClub }, tierTemporada, grupoPosicion, baseline
  );

  carreraActualizarReputacion(j, { valoracion, goles, asistencias, resultadoClub, convocatoria, cambioDivision, lesion }, premiosTemporada);

  j.edad = edadDeLaTemporada + CARRERA_PASO_EDAD;
  CARRERA_STATE.temporada += 1;

  // Copa Argentina: torneo aparte del campeonato de liga, se puede ganar
  // en la misma temporada que se sale campeón de liga o descendido, no
  // son excluyentes entre sí.
  const ganoCopaArgentina = carreraTirarCopaArgentina(club);

  CARRERA_STATE.historial.unshift({
    temporada: CARRERA_STATE.temporada, edad: edadDeLaTemporada, club: club.nombre,
    escudo: club.escudo, liga: ligaDeLaTemporada, cambioDivision, resultadoClub, partidos, goles, asistencias,
    valoracion, generalAntes, generalDespues, lesion, convocatoria, debutSeleccion, ganoCopaArgentina,
    premios: premiosTemporada
  });

  const huboTitulo = resultadoClub === "Campeón" || ganoCopaArgentina;
  if (resultadoClub === "Campeón") {
    CARRERA_STATE.titulos.unshift({
      temporada: CARRERA_STATE.temporada, edad: j.edad, club: club.nombre, liga: club.liga
    });
  }
  if (ganoCopaArgentina) {
    CARRERA_STATE.titulos.unshift({
      temporada: CARRERA_STATE.temporada, edad: j.edad, club: club.nombre, liga: "Copa Argentina"
    });
  }
  if (debutSeleccion) {
    CARRERA_STATE.hitos.unshift({ tipo: "seleccion", edad: j.edad, pais: j.pais.nombre });
  }

  // Hitos de carrera (Fase 5, §10): la mayoría se derivan directamente de
  // datos que ya se calcularon arriba -- acá solo se detecta la PRIMERA
  // vez que pasa cada uno (salvo lesión grave, que se registra cada vez
  // que ocurre, y ascenso/descenso, que se registra cada vez que se
  // asciende o desciende de verdad).
  if (CARRERA_STATE.temporada === 1) {
    CARRERA_STATE.hitos.unshift({ tipo: "debut_profesional", edad: edadDeLaTemporada, club: club.nombre });
  }
  if (goles > 0 && !j.golHecho) {
    j.golHecho = true;
    CARRERA_STATE.hitos.unshift({ tipo: "primer_gol", edad: edadDeLaTemporada, club: club.nombre });
  }
  if (huboTitulo && !j.tituloHecho) {
    j.tituloHecho = true;
    CARRERA_STATE.hitos.unshift({ tipo: "primer_titulo", edad: j.edad, club: club.nombre });
  }
  if (cambioDivision === "ascenso") {
    CARRERA_STATE.hitos.unshift({ tipo: "ascenso", edad: j.edad, club: club.nombre });
  } else if (cambioDivision === "descenso") {
    CARRERA_STATE.hitos.unshift({ tipo: "descenso", edad: j.edad, club: club.nombre });
  }
  if (resultadoClub === "Clasificó a copas internacionales" && !j.continentalHecho) {
    j.continentalHecho = true;
    CARRERA_STATE.hitos.unshift({ tipo: "debut_continental", edad: j.edad, club: club.nombre });
  }
  if (lesion && lesion.tipo === "grave") {
    CARRERA_STATE.hitos.unshift({ tipo: "lesion_grave", edad: j.edad, club: club.nombre });
  }
  if (premiosTemporada.some(p => p.tipo === "balon_de_oro") && !j.balonDeOroHecho) {
    j.balonDeOroHecho = true;
    CARRERA_STATE.hitos.unshift({ tipo: "balon_de_oro", edad: j.edad, club: club.nombre });
  }

  if (j.edad >= CARRERA_EDAD_RETIRO) {
    CARRERA_STATE.retirado = true;
    CARRERA_STATE.decision = null;
    CARRERA_STATE.hitos.unshift({ tipo: "retiro", edad: j.edad });
  } else {
    carreraGenerarDecision();
  }
  carreraMostrarDashboard();
}

/* ---------- Préstamos / fichajes / continuidad: decisión post-temporada ---------- */
// Arma las opciones que se muestran en el panel de decisión del dashboard
// después de simular una temporada. Si el jugador está a préstamo, puede
// volver a su club dueño, firmar ficha definitiva con el club prestador,
// o extender el préstamo un año más. Si no está a préstamo, puede
// quedarse en su club o recibir ofertas de otros clubes -- mezclando
// fichajes definitivos (transferencia real, dueño nuevo) y préstamos, no
// solo préstamos: un jugador que ya se afianzó recibe más ofertas de
// compra que de préstamo, y uno joven que todavía necesita rodaje recibe
// más préstamos que fichajes.
// Probabilidad de que aparezca la oferta de "vuelta a casa" esta
// temporada, una vez que el jugador ya está en la ventana de edad (ver
// CARRERA_EDAD_VUELTA_CASA): sube a medida que se acerca el retiro -- a
// los 34 recién empieza a ser una posibilidad real (15%), a los 39 es
// casi segura (75%, nunca 100% porque no todas las temporadas coincide
// con que el club de casa lo llame).
function carreraProbabilidadVueltaCasa(edad){
  return Math.min(0.75, Math.max(0.15, (edad - CARRERA_EDAD_VUELTA_CASA + 1) * 0.11));
}

function carreraGenerarDecision(){
  const j = CARRERA_STATE.jugador;
  const ultima = CARRERA_STATE.historial[0]; // la temporada recién jugada
  const opciones = [];
  if (j.enPrestamo) {
    opciones.push({ id:"volver", label:`Volver a ${j.clubDueño.nombre}`, club:j.clubDueño, prestamo:false });
    opciones.push({ id:"definitiva", label:`Ficha definitiva con ${j.club.nombre}`, club:j.club, prestamo:false, dueñoNuevo:true });
    opciones.push({ id:"extender", label:`Extender préstamo en ${j.club.nombre}`, club:j.club, prestamo:true });
    j.descartado = false;
  } else {
    // El club no siempre te renueva: si la temporada fue floja (nota baja
    // o casi no jugaste, típico de una lesión larga) hay bastante chance
    // de que directamente te dejen libre en vez de ofrecerte seguir. En
    // ese caso no hay opción "seguir", y las ofertas que aparecen son de
    // nivel más bajo -- nadie grande sale a buscar a alguien que recién
    // tuvo una mala temporada.
    const rindioMal = ultima && (ultima.valoracion < 5.5 || ultima.partidos <= 6);
    const probDescarte = rindioMal ? 0.4 : 0.05;
    const descartado = Math.random() < probDescarte;
    j.descartado = descartado;

    if (!descartado) {
      opciones.push({ id:"seguir", label:`Quedarte en ${j.club.nombre}`, club:j.club, prestamo:false });
    }
    // Cuántas de las ofertas restantes son fichaje vs préstamo. Menor a
    // 21 años: casi siempre préstamo (necesita rodaje). De ahí en más, la
    // mezcla se inclina a fichaje a medida que el nivel general es más
    // alto -- salvo que te hayan dejado libre, ahí casi todo es préstamo
    // o prueba, porque no hay margen para negociar un fichaje grande.
    let fichajes;
    if (descartado) fichajes = j.atributos.general >= 60 && Math.random() < 0.3 ? 1 : 0;
    else if (j.edad <= 20) fichajes = Math.random() < 0.15 ? 1 : 0;
    else if (j.atributos.general >= 65) fichajes = Math.random() < 0.7 ? 2 : 1;
    else fichajes = Math.random() < 0.55 ? 1 : 2;
    const cantidadOfertas = descartado ? 3 : 2;
    const prestamos = cantidadOfertas - fichajes;

    // El nivel de club al que aspirás no depende solo del OVR: una
    // temporada de nota muy alta (buen rendimiento, no solo buen OVR de
    // base) te pone en el radar de clubes más ambiciosos de lo que tu
    // nivel general solo ameritaría -- así "cuantos más goles metas y
    // mejor rindas, mejores equipos te llaman" pesa de verdad, no solo
    // el número de OVR.
    const bonoForma = ultima && !descartado ? Math.max(0, (ultima.valoracion - 6.5) * 4) : 0;
    const nivelBusqueda = descartado ? j.atributos.general - 10 : j.atributos.general + bonoForma;
    // Si te acaban de dejar libre, no tiene sentido que ese mismo club (o
    // el anterior inmediato) te vuelva a ofrecer algo la temporada
    // siguiente -- se excluyen los últimos clubes en los que estuvo,
    // no solo el actual, para evitar el "te corto y al toque me ofrece
    // volver" que reportó Pablo.
    const clubesRecientes = descartado
      ? CARRERA_STATE.historial.slice(0, 2).map(h => h.club)
      : [];
    const candidatos = carreraObtenerOfertasPrestamo(j, CARRERA_STATE.temporada, j.club.nombre, nivelBusqueda, fichajes + prestamos, clubesRecientes);
    candidatos.forEach((c, i) => {
      if (i < fichajes) {
        opciones.push({ id:"fichaje"+i, label:`Fichaje de ${c.nombre}`, club:c, prestamo:false, dueñoNuevo:true });
      } else {
        opciones.push({ id:(descartado ? "prueba" : "prestamo")+i, label:`${descartado ? "Prueba" : "Préstamo"} en ${c.nombre}`, club:c, prestamo:true });
      }
    });

    // "Vuelta a casa" (§ pedido por Gonzalo): sobre el final de la carrera,
    // si el jugador está jugando fuera de su país de origen, puede
    // aparecer una oferta EXTRA de un club de ESE país -- cierre
    // sentimental de la carrera. Se suma a las ofertas normales, no las
    // reemplaza, y solo si hay clubes cargados para ese país en el dataset
    // (si no hay, no se puede armar la oferta y se omite sin romper nada).
    if (!descartado && j.edad >= CARRERA_EDAD_VUELTA_CASA && j.club.iso2 !== j.pais.iso2) {
      const poolOrigen = CARRERA_CLUBES[j.pais.iso2];
      if (poolOrigen && poolOrigen.length && Math.random() < carreraProbabilidadVueltaCasa(j.edad)) {
        const candidatosOrigen = poolOrigen
          .filter(c => c.nombre !== j.club.nombre)
          .map(c => ({ ...c, iso2: j.pais.iso2 }));
        candidatosOrigen.forEach(c => { c._score = carreraScoreClub(c, j, nivelBusqueda, CARRERA_STATE.temporada); });
        candidatosOrigen.sort((a, b) => b._score - a._score);
        const elegido = candidatosOrigen[0];
        if (elegido) {
          opciones.push({ id:"vueltacasa", label:`Vuelta a casa: ${elegido.nombre} (${j.pais.nombre})`, club: elegido, prestamo:false, dueñoNuevo:true, vueltaCasa:true });
        }
      }
    }
  }
  CARRERA_STATE.decision = { opciones };
}

// Aplica la opción elegida en el panel de decisión y arranca directo la
// temporada en el club nuevo (o el mismo, si eligió "seguir"/"volver"),
// sin necesitar un click extra en "Jugar Temporada" -- elegir club Y
// jugar esa temporada son, en los hechos, la misma decisión.
function carreraResolverDecision(id){
  const dec = CARRERA_STATE.decision;
  if (!dec) return;
  const op = dec.opciones.find(o => o.id === id);
  if (!op) return;
  const j = CARRERA_STATE.jugador;
  // "volver"/"extender"/"definitiva" reusan el club en el que ya está (con
  // sus ascensos/descensos ya aplicados) tal cual; el resto son clubes
  // nuevos del pool -- se copian para no mutar el pool compartido.
  const sigueEnMismoClub = op.id === "volver" || op.id === "extender" || op.id === "definitiva";
  j.club = sigueEnMismoClub ? op.club : { ...op.club };
  j.enPrestamo = !!op.prestamo;
  if (op.dueñoNuevo) j.clubDueño = j.club;

  // Continuidad en el club actual (Fase 5, §10): el contador solo sigue
  // subiendo si es genuinamente el mismo club (incluye volver de préstamo
  // al dueño y extender el préstamo); un club nuevo de verdad lo resetea.
  // Cambio de club de verdad: se detectan acá los hitos de "primer club
  // europeo" y "vuelve a un club en el que ya jugó antes" (retorno), que
  // solo tienen sentido en el momento del cambio, no cada temporada.
  if (sigueEnMismoClub) {
    j.temporadasEnClubActual += 1;
  } else {
    const yaJugoEnEseClub = CARRERA_STATE.historial.some(h => h.club === j.club.nombre);
    if (op.vueltaCasa) {
      CARRERA_STATE.hitos.unshift({ tipo: "vuelta_pais_origen", edad: j.edad, club: j.club.nombre, pais: j.pais.nombre });
    } else if (yaJugoEnEseClub) {
      CARRERA_STATE.hitos.unshift({ tipo: "retorno_club_origen", edad: j.edad, club: j.club.nombre });
    }
    if (carreraObtenerTier(j.club.liga) >= 3 && !j.primerClubEuropeoHecho) {
      j.primerClubEuropeoHecho = true;
      CARRERA_STATE.hitos.unshift({ tipo: "primer_club_europeo", edad: j.edad, club: j.club.nombre });
    }
    j.temporadasEnClubActual = 1;
    j.capitanEnClubActual = false;
  }
  // Capitán: heurística simple, 3+ temporadas seguidas en el mismo club
  // (una sola vez por estadía, no se repite temporada a temporada).
  if (!j.capitanEnClubActual && j.temporadasEnClubActual >= 3) {
    j.capitanEnClubActual = true;
    CARRERA_STATE.hitos.unshift({ tipo: "capitan", edad: j.edad, club: j.club.nombre });
  }

  CARRERA_STATE.decision = null;
  carreraSimularTemporada();
}

/* ---------- Pantalla 4: dashboard ---------- */
function carreraMostrarDashboard(){
  document.getElementById("carrera-inicio").style.display = "none";
  document.getElementById("carrera-identidad").style.display = "none";
  document.getElementById("carrera-oferta").style.display = "none";
  const dash = document.getElementById("carrera-dashboard");
  dash.style.display = "";
  const j = CARRERA_STATE.jugador;
  const a = j.atributos;
  const valor = carreraFormatoValor(carreraValorMercado(a, j.edad));
  const claseOVR = carreraClaseOVR(a.general);

  // Agregados de carrera (todas las temporadas jugadas).
  const totales = CARRERA_STATE.historial.reduce((acc, h) => {
    acc.pj += h.partidos; acc.goles += h.goles; acc.asist += h.asistencias; return acc;
  }, { pj:0, goles:0, asist:0 });

  // Timeline de carrera (Fase 5, §10): reemplaza la vitrina plana de
  // títulos por una línea de tiempo ordenada por edad que mezcla títulos
  // y todos los tipos de hito, cada uno con ícono + texto. Reusa la
  // misma clase CSS que ya existía (carrera-vitrina-item) para no
  // depender de estilos nuevos en index.html.
  const timelineItems = [
    ...CARRERA_STATE.titulos.map(t => ({ edad: t.edad, icono: "🏆", texto: `${t.liga} con ${t.club}` })),
    ...CARRERA_STATE.hitos.map(h => {
      if (h.tipo === "seleccion") {
        return { edad: h.edad, icono: carreraBandera(j.pais.iso2), texto: `Debut en la Selección de ${h.pais}` };
      }
      const info = CARRERA_HITO_INFO[h.tipo];
      return { edad: h.edad, icono: info ? info.icono : "•", texto: info ? info.texto(h) : h.tipo };
    }),
  ].sort((a, b) => a.edad - b.edad);
  const vitrinaHTML = timelineItems.length ? `
    <div class="carrera-vitrina-lista">${timelineItems.map(it =>
      `<span class="carrera-vitrina-item carrera-vitrina-item--hito">${it.icono} ${it.texto} · ${it.edad} años</span>`
    ).join("")}</div>` : `<p class="carrera-vitrina-vacia">Vitrina vacía</p>`;

  const seleccionHTML = j.capasSeleccion > 0 ? `
    <div class="carrera-seleccion">
      <h4>${carreraBandera(j.pais.iso2)} Selección de ${j.pais.nombre}</h4>
      <div class="carrera-seleccion-stats">
        <div><b>${j.capasSeleccion}</b><span>Presencias</span></div>
        <div><b>${j.golesSeleccion}</b><span>Goles</span></div>
      </div>
    </div>` : "";

  const decisionHTML = CARRERA_STATE.retirado ? `
    <div class="carrera-decision carrera-retiro">
      <h3>🏁 Fin de la carrera</h3>
      <p class="carrera-oferta-sub">${j.apellido.trim().toUpperCase()} se retira a los ${j.edad} años, tras ${CARRERA_STATE.temporada} temporada${CARRERA_STATE.temporada === 1 ? "" : "s"} y ${CARRERA_STATE.titulos.length} título${CARRERA_STATE.titulos.length === 1 ? "" : "s"}. Pico de nivel: ${j.picoGeneral} OVR.</p>
      <button type="button" class="btn-carrera-primary" id="btn-carrera-nueva">Empezar una nueva carrera</button>
    </div>` : CARRERA_STATE.decision ? `
    <div class="carrera-decision${j.descartado ? " carrera-decision--descarte" : ""}">
      <h3>${j.enPrestamo ? "Regreso a tu club" : j.descartado ? "No te renovaron" : "¿Qué hacés esta temporada?"}</h3>
      <p class="carrera-decision-desc">${j.enPrestamo
        ? `Volvés a ${j.clubDueño.nombre} y vas a ser tenido en cuenta. Si igual querés salir, tenés ${CARRERA_STATE.decision.opciones.length - 1} oferta${CARRERA_STATE.decision.opciones.length - 1 === 1 ? "" : "s"} para cambiar de aire.`
        : j.descartado
        ? `${j.club.nombre} decidió no seguir contando con vos. Tenés que buscar equipo nuevo -- por ahora, solo aparecen pruebas y préstamos.`
        : `Podés quedarte en ${j.club.nombre} o escuchar otras ofertas.`}</p>
      <div class="carrera-decision-grid">
        ${CARRERA_STATE.decision.opciones.map((op, i) => {
          const ultimaImpar = i === CARRERA_STATE.decision.opciones.length - 1 && CARRERA_STATE.decision.opciones.length % 2 === 1;
          const tipo = op.id === "seguir" || op.id === "volver" ? "Quedarte en" : op.id === "extender" ? "Extender en" : op.id === "definitiva" ? "Ficha fija con" : op.id.startsWith("prueba") ? "Prueba en" : op.id.startsWith("prestamo") ? "Préstamo en" : "Fichar por";
          const esClubNuevo = op.id.startsWith("fichaje") || op.id.startsWith("prestamo") || op.id.startsWith("prueba");
          const salto = esClubNuevo ? carreraClaseSalto(op.club.nivel, j.club.nivel) : null;
          return `
          <button type="button" class="carrera-decision-card${ultimaImpar ? " carrera-decision-card--centrada" : ""}" data-id="${op.id}" style="animation-delay:${i * 60}ms">
            <span class="carrera-decision-tipo">${tipo}</span>
            <strong>${op.club.nombre}</strong>
            <img class="carrera-decision-escudo" src="escudos/${op.club.escudo}" alt="" onerror="this.style.visibility='hidden'">
            <span class="carrera-decision-liga">${carreraLogoLigaHTML(op.club.liga)}${op.club.liga}</span>
            ${salto ? `<span class="carrera-decision-salto ${salto.clase}">${salto.texto}</span>` : ""}
          </button>`;
        }).join("")}
      </div>
    </div>` : `
    <button type="button" class="btn-carrera-primary carrera-btn-temporada" id="btn-carrera-jugar-temporada">Jugar Temporada ${CARRERA_STATE.temporada + 1}</button>`;

  const tablaHTML = carreraTablaEdadesHTML();

  dash.innerHTML = `
    <div class="carrera-dash-grid">
      <div class="carrera-tarjeta">
        <div class="carrera-tarjeta-top">
          <div class="carrera-ovr-badge ${claseOVR}">${a.general}<span>OVR</span></div>
          <div class="carrera-tarjeta-id">
            <div class="carrera-tarjeta-id-top">
              <span class="carrera-tarjeta-chip">${carreraBandera(j.pais.iso2)}</span>
              <span class="carrera-tarjeta-chip">#${j.numero}</span>
              <span class="carrera-tarjeta-chip carrera-tarjeta-chip-pos">${j.posicion}</span>
              <span class="carrera-tarjeta-edad">EDAD<b>${j.edad}</b></span>
            </div>
            <h2>${carreraLogoLigaHTML(j.club.liga)}${j.apellido.trim().toUpperCase()}</h2>
            <div class="carrera-tarjeta-valor">VALOR <b>${valor}</b></div>
          </div>
        </div>
        <div class="carrera-tarjeta-stats">
          <div><span class="carrera-stat-icono">🎽</span><b>${totales.pj}</b><span>PJ</span></div>
          <div><span class="carrera-stat-icono">⚽</span><b>${totales.goles}</b><span>GLS</span></div>
          <div><span class="carrera-stat-icono">🅰️</span><b>${totales.asist}</b><span>AST</span></div>
        </div>
        <div class="carrera-vitrina">
          <h4>🏆 Vitrina</h4>
          ${vitrinaHTML}
        </div>
        ${seleccionHTML}
        <div class="carrera-atributo carrera-atributo-reputacion" title="Cómo te ve el mundo del fútbol: la mueven tu rendimiento real, tus títulos y tu continuidad -- no solo tu nivel general">
          <span>Reputación</span><b>${Math.round(j.reputacion)}</b>
          <div class="carrera-atributo-barra"><div style="width:${Math.round(j.reputacion)}%"></div></div>
        </div>
        <div class="carrera-atributos">
          <div class="carrera-atributo"><span>Ataque</span><b>${a.ataque}</b><div class="carrera-atributo-barra"><div style="width:${a.ataque}%"></div></div></div>
          <div class="carrera-atributo"><span>Defensa</span><b>${a.defensa}</b><div class="carrera-atributo-barra"><div style="width:${a.defensa}%"></div></div></div>
          <div class="carrera-atributo"><span>Físico</span><b>${a.fisico}</b><div class="carrera-atributo-barra"><div style="width:${a.fisico}%"></div></div></div>
        </div>
        ${decisionHTML}
        <button type="button" class="btn-carrera-secondary" id="btn-carrera-editar">Editar identidad</button>
      </div>
      <div class="carrera-dash-derecha">
        ${tablaHTML}
      </div>
    </div>`;

  const btnTemporada = document.getElementById("btn-carrera-jugar-temporada");
  if (btnTemporada) btnTemporada.addEventListener("click", carreraSimularTemporada);

  dash.querySelectorAll(".carrera-decision-card").forEach(btn => {
    btn.addEventListener("click", () => {
      const id = btn.dataset.id;
      dash.querySelectorAll(".carrera-decision-card").forEach(c => c.classList.add("carrera-decision-card--descartada"));
      btn.classList.remove("carrera-decision-card--descartada");
      btn.classList.add("carrera-decision-card--elegida");
      setTimeout(() => carreraResolverDecision(id), 380);
    });
  });

  const btnNuevaCarrera = document.getElementById("btn-carrera-nueva");
  if (btnNuevaCarrera) btnNuevaCarrera.addEventListener("click", carreraReiniciarEstado);

  document.getElementById("btn-carrera-editar").addEventListener("click", carreraReiniciarEstado);

  // Reengancha la animación de entrada de la tarjeta en cada temporada
  // jugada -- por default una animación CSS solo corre la primera vez que
  // el elemento aparece, así que sin este truco (forzar un reflow entre
  // sacar y volver a poner la clase) el dashboard se sentía "estático"
  // después del primer render, aunque el contenido cambiara.
  const tarjeta = dash.querySelector(".carrera-tarjeta");
  if (tarjeta) {
    tarjeta.style.animation = "none";
    void tarjeta.offsetWidth;
    tarjeta.style.animation = "";
  }
}

// Arma la tabla de la derecha: una fila por cada bienio posible entre los
// 16 y los 38 años (el último bienio jugable antes del retiro a los 40).
// Cada fila puede estar en 3 estados: ya jugada (datos reales, con escudo,
// logo de liga y color según cómo le fue esa temporada al club), en curso
// (todavía no se eligió club para esa edad -- fila "Eligiendo club...") o
// futura (apagada, solo muestra la edad).
function carreraTablaEdadesHTML(){
  const j = CARRERA_STATE.jugador;
  const porEdad = new Map(CARRERA_STATE.historial.map(h => [h.edad, h]));
  const filas = [];
  for (let edad = CARRERA_EDAD_INICIAL; edad < CARRERA_EDAD_RETIRO; edad += CARRERA_PASO_EDAD) {
    const h = porEdad.get(edad);
    if (h) {
      // Los eventos del período (ascenso/descenso, lesión, convocatoria)
      // se muestran como un ícono chico con tooltip en vez de badges de
      // texto completo -- así la fila queda de una sola línea, sin pisar
      // el nombre del club ni desbordar en pantallas angostas.
      let iconos = "";
      if (h.cambioDivision === "ascenso") iconos += `<span class="carrera-fila-icono carrera-fila-icono--ascenso" title="Ascenso de división">▲</span>`;
      else if (h.cambioDivision === "descenso") iconos += `<span class="carrera-fila-icono carrera-fila-icono--descenso" title="Descenso de división">▼</span>`;
      if (h.lesion) iconos += `<span class="carrera-fila-icono carrera-fila-icono--lesion" title="Lesión ${h.lesion.tipo}: ${h.partidos} PJ jugados">🩹</span>`;
      if (h.convocatoria) iconos += `<span class="carrera-fila-icono carrera-fila-icono--seleccion" title="Convocado a la selección: +${h.convocatoria.presencias} presencias">🌐</span>`;
      if (h.ganoCopaArgentina) iconos += `<span class="carrera-fila-icono" title="Ganó la Copa Argentina">🏆</span>`;
      if (h.premios && h.premios.length) {
        iconos += h.premios.map(p => `<span class="carrera-fila-icono" title="${p.nombre}">${CARRERA_PREMIO_ICONO[p.tipo] || "🎖️"}</span>`).join("");
      }
      filas.push(`
        <div class="carrera-fila carrera-fila-jugada ${carreraClaseResultado(h.resultadoClub)}" style="animation-delay:${Math.min(filas.length, 10) * 40}ms; --club-color:${carreraColorClub(h.club)}" title="${h.club} — ${h.liga} — ${h.resultadoClub}">
          <div class="carrera-fila-edad">${h.edad}</div>
          <div class="carrera-fila-club">
            <img class="carrera-fila-escudo" src="escudos/${h.escudo}" alt="" onerror="this.style.visibility='hidden'">
            <span>${h.club}</span>
            ${iconos}
          </div>
          <div class="carrera-fila-ovr ${carreraClaseOVR(h.generalDespues)}">${h.generalDespues}</div>
          <div class="carrera-fila-num">${h.partidos}</div>
          <div class="carrera-fila-num">⚽ ${h.goles}</div>
          <div class="carrera-fila-num">🅰️ ${h.asistencias}</div>
          <div class="carrera-fila-nota ${carreraClaseNota(h.valoracion)}" title="Nota de la temporada">${h.valoracion.toFixed(1)}</div>
        </div>`);
    } else if (edad === j.edad && !CARRERA_STATE.retirado) {
      filas.push(`
        <div class="carrera-fila carrera-fila-pendiente">
          <div class="carrera-fila-edad carrera-fila-edad-pendiente">${edad}</div>
          <div class="carrera-fila-club carrera-fila-eligiendo">Eligiendo club...</div>
        </div>`);
    } else {
      filas.push(`
        <div class="carrera-fila carrera-fila-futura">
          <div class="carrera-fila-edad">${edad}</div>
        </div>`);
    }
  }
  return `
    <div class="carrera-tabla">
      <div class="carrera-tabla-header">
        <div>EDAD</div><div>CLUB</div><div>OVR</div><div>PJ</div><div>GLS</div><div>AST</div><div>NOTA</div>
      </div>
      <div class="carrera-tabla-body">${filas.join("")}</div>
    </div>`;
}

// Vuelve a la pantalla de identidad y limpia todo el estado de la carrera
// anterior (club, edad, atributos, curva de pico/declive, historial,
// títulos y el flag de retiro), para arrancar una carrera nueva de cero.
function carreraReiniciarEstado(){
  CARRERA_STATE.jugador.club = null;
  CARRERA_STATE.jugador.clubDueño = null;
  CARRERA_STATE.jugador.enPrestamo = false;
  CARRERA_STATE.jugador.edad = null;
  CARRERA_STATE.jugador.edadPico = null;
  CARRERA_STATE.jugador.picoGeneral = null;
  CARRERA_STATE.jugador.adn = null;
  CARRERA_STATE.jugador.reputacion = 0;
  CARRERA_STATE.jugador.potencialEfectivo = null;
  CARRERA_STATE.jugador.capasSeleccion = 0;
  CARRERA_STATE.jugador.golesSeleccion = 0;
  CARRERA_STATE.jugador.atributos = null;
  CARRERA_STATE.jugador.temporadasEnClubActual = 1;
  CARRERA_STATE.jugador.capitanEnClubActual = false;
  CARRERA_STATE.jugador.primerClubEuropeoHecho = false;
  CARRERA_STATE.jugador.continentalHecho = false;
  CARRERA_STATE.jugador.golHecho = false;
  CARRERA_STATE.jugador.tituloHecho = false;
  CARRERA_STATE.jugador.balonDeOroHecho = false;
  CARRERA_STATE.temporada = 0;
  CARRERA_STATE.historial = [];
  CARRERA_STATE.titulos = [];
  CARRERA_STATE.hitos = [];
  CARRERA_STATE.decision = null;
  CARRERA_STATE.retirado = false;
  carreraMostrarIdentidad();
}

/* ---------- Inicialización (una sola vez) ---------- */
function initCarrera(){
  if (CARRERA_STATE.iniciado) return;
  CARRERA_STATE.iniciado = true;

  document.getElementById("btn-carrera-comenzar").addEventListener("click", carreraMostrarIdentidad);
  document.getElementById("btn-carrera-volver").addEventListener("click", carreraMostrarInicio);

  document.getElementById("carrera-input-apellido").addEventListener("input", (ev) => {
    CARRERA_STATE.jugador.apellido = ev.target.value.slice(0, 20);
    carreraActualizarCamiseta();
    carreraActualizarBotonConfirmar();
  });

  document.getElementById("carrera-input-numero").addEventListener("input", (ev) => {
    let n = parseInt(ev.target.value, 10);
    n = isNaN(n) ? 10 : Math.max(1, Math.min(99, n));
    CARRERA_STATE.jugador.numero = n;
    carreraActualizarCamiseta();
  });

  document.querySelectorAll(".carrera-toggle-pierna button").forEach(btn => {
    btn.addEventListener("click", () => {
      CARRERA_STATE.jugador.pierna = btn.dataset.pierna;
      document.querySelectorAll(".carrera-toggle-pierna button").forEach(b => b.classList.toggle("active", b === btn));
    });
  });

  document.getElementById("carrera-input-pais").addEventListener("input", (ev) => {
    carreraRenderPaises(ev.target.value);
  });

  document.getElementById("btn-carrera-confirmar").addEventListener("click", () => {
    if (!carreraJugadorCompleto()) return;
    carreraMostrarOferta();
  });

  carreraMostrarInicio();
}
