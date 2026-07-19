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
  // Edad de pico (prime): entre 30 y 32, sorteada una sola vez por carrera.
  // A partir de ahí el rendimiento empieza a bajar en vez de crecer.
  CARRERA_STATE.jugador.edadPico = 30 + Math.floor(Math.random() * 3);
  CARRERA_STATE.jugador.picoGeneral = CARRERA_STATE.jugador.atributos.general;
  CARRERA_STATE.jugador.capasSeleccion = 0;
  CARRERA_STATE.jugador.golesSeleccion = 0;
  CARRERA_STATE.temporada = 0;
  CARRERA_STATE.historial = [];
  CARRERA_STATE.titulos = [];
  CARRERA_STATE.hitos = [];
  CARRERA_STATE.decision = null;
  CARRERA_STATE.retirado = false;
  carreraMostrarDashboard();
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

function carreraAplicarAscensoDescenso(club, resultadoClub){
  const tier = CARRERA_DIVISION_TIER[club.liga];
  if (!tier) return null; // club del exterior, sin pirámide modelada
  if (resultadoClub === "Campeón" && tier < 3) {
    const ligaNueva = CARRERA_SIGUIENTE_LIGA[tier];
    club.nivel = tier === 1 ? Math.max(club.nivel + 14, 52) : Math.max(club.nivel + 16, 62);
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
const CARRERA_PROB_LESION = 0.16;
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
  let factorGol, factorAsist;
  if (CARRERA_GRUPOS_POSICION.delantero.includes(j.posicion)) { factorGol = 0.55; factorAsist = 0.18; }
  else if (CARRERA_GRUPOS_POSICION.medio.includes(j.posicion)) { factorGol = 0.22; factorAsist = 0.30; }
  else if (CARRERA_GRUPOS_POSICION.defensor.includes(j.posicion)) { factorGol = 0.06; factorAsist = 0.10; }
  else { factorGol = 0.01; factorAsist = 0.02; }
  const ruidoGol = () => 0.6 + Math.random() * 0.7;
  const goles = Math.max(0, Math.round(partidos * factorGol * (j.atributos.ataque / 60) * ruidoGol()));
  const asistencias = Math.max(0, Math.round(partidos * factorAsist * (j.atributos.ataque / 60) * ruidoGol()));

  let valoracion = 5 + (j.atributos.general / 99) * 4 + (Math.random() * 0.8 - 0.3);
  valoracion = Math.round(Math.max(1, Math.min(10, valoracion)) * 10) / 10;

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
  const ligaDeLaTemporada = club.liga;
  const rollClub = (club.nivel || 45) + (Math.random() * 30 - 15);
  let resultadoClub;
  if (rollClub >= 80) resultadoClub = "Campeón";
  else if (rollClub >= 65) resultadoClub = "Clasificó a copas internacionales";
  else if (rollClub >= 45) resultadoClub = "Mitad de tabla";
  else if (rollClub >= 30) resultadoClub = "Peleó el descenso";
  else resultadoClub = "Descendió";

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
    const retencion = 0.65 + (j.picoGeneral / 99) * 0.20; // 65%-85% del pico
    const piso = Math.round(j.picoGeneral * retencion);
    const bieniosPasadoElPico = (edadDeLaTemporada - j.edadPico) / CARRERA_PASO_EDAD;
    const declive = 2 + Math.floor(Math.random() * 3) + Math.floor(bieniosPasadoElPico / 1.5);
    generalDespues = Math.max(piso, generalAntes - declive);
  }
  j.atributos.general = generalDespues;
  j.edad = edadDeLaTemporada + CARRERA_PASO_EDAD;
  CARRERA_STATE.temporada += 1;

  CARRERA_STATE.historial.unshift({
    temporada: CARRERA_STATE.temporada, edad: edadDeLaTemporada, club: club.nombre,
    escudo: club.escudo, liga: ligaDeLaTemporada, cambioDivision, resultadoClub, partidos, goles, asistencias,
    valoracion, generalAntes, generalDespues, lesion, convocatoria, debutSeleccion
  });

  if (resultadoClub === "Campeón") {
    CARRERA_STATE.titulos.unshift({
      temporada: CARRERA_STATE.temporada, edad: j.edad, club: club.nombre, liga: club.liga
    });
  }
  if (debutSeleccion) {
    CARRERA_STATE.hitos.unshift({ tipo: "seleccion", edad: j.edad, pais: j.pais.nombre });
  }

  if (j.edad >= CARRERA_EDAD_RETIRO) {
    CARRERA_STATE.retirado = true;
    CARRERA_STATE.decision = null;
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
function carreraGenerarDecision(){
  const j = CARRERA_STATE.jugador;
  const opciones = [];
  if (j.enPrestamo) {
    opciones.push({ id:"volver", label:`Volver a ${j.clubDueño.nombre}`, club:j.clubDueño, prestamo:false });
    opciones.push({ id:"definitiva", label:`Ficha definitiva con ${j.club.nombre}`, club:j.club, prestamo:false, dueñoNuevo:true });
    opciones.push({ id:"extender", label:`Extender préstamo en ${j.club.nombre}`, club:j.club, prestamo:true });
  } else {
    opciones.push({ id:"seguir", label:`Quedarte en ${j.club.nombre}`, club:j.club, prestamo:false });
    // Cuántas de las 2 ofertas restantes son fichaje vs préstamo. Menor a
    // 21 años: casi siempre préstamo (necesita rodaje). De ahí en más, la
    // mezcla se inclina a fichaje a medida que el nivel general es más alto.
    let fichajes;
    if (j.edad <= 20) fichajes = Math.random() < 0.15 ? 1 : 0;
    else if (j.atributos.general >= 65) fichajes = Math.random() < 0.7 ? 2 : 1;
    else fichajes = Math.random() < 0.55 ? 1 : 2;
    const prestamos = 2 - fichajes;

    const candidatos = carreraObtenerOfertasPrestamo(j.club.nombre, j.atributos.general, fichajes + prestamos);
    candidatos.forEach((c, i) => {
      if (i < fichajes) {
        opciones.push({ id:"fichaje"+i, label:`Fichaje de ${c.nombre}`, club:c, prestamo:false, dueñoNuevo:true });
      } else {
        opciones.push({ id:"prestamo"+i, label:`Préstamo a ${c.nombre}`, club:c, prestamo:true });
      }
    });
  }
  CARRERA_STATE.decision = { opciones };
}

// Aplica la opción elegida en el panel de decisión y vuelve a habilitar
// el botón de "Jugar Temporada".
function carreraResolverDecision(id){
  const dec = CARRERA_STATE.decision;
  if (!dec) return;
  const op = dec.opciones.find(o => o.id === id);
  if (!op) return;
  const j = CARRERA_STATE.jugador;
  // "volver"/"extender"/"definitiva" reusan el club en el que ya está (con
  // sus ascensos/descensos ya aplicados) tal cual; el resto son clubes
  // nuevos del pool -- se copian para no mutar el pool compartido.
  j.club = (op.id === "volver" || op.id === "extender" || op.id === "definitiva") ? op.club : { ...op.club };
  j.enPrestamo = !!op.prestamo;
  if (op.dueñoNuevo) j.clubDueño = j.club;
  CARRERA_STATE.decision = null;
  carreraMostrarDashboard();
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

  const vitrinaItems = [
    ...CARRERA_STATE.titulos.map(t => `<span class="carrera-vitrina-item">🏆 ${t.liga} · ${t.edad} años</span>`),
    ...CARRERA_STATE.hitos.map(h => `<span class="carrera-vitrina-item carrera-vitrina-item--hito">${carreraBandera(j.pais.iso2)} Debut en ${h.pais} · ${h.edad} años</span>`),
  ];
  const vitrinaHTML = vitrinaItems.length ? `
    <div class="carrera-vitrina-lista">${vitrinaItems.join("")}</div>` : `<p class="carrera-vitrina-vacia">Vitrina vacía</p>`;

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
    <div class="carrera-decision">
      <h3>${j.enPrestamo ? "Regreso a tu club" : "¿Qué hacés esta temporada?"}</h3>
      <p class="carrera-decision-desc">${j.enPrestamo
        ? `Volvés a ${j.clubDueño.nombre} y vas a ser tenido en cuenta. Si igual querés salir, tenés ${CARRERA_STATE.decision.opciones.length - 1} oferta${CARRERA_STATE.decision.opciones.length - 1 === 1 ? "" : "s"} para cambiar de aire.`
        : `Podés quedarte en ${j.club.nombre} o escuchar otras ofertas.`}</p>
      <div class="carrera-decision-grid">
        ${CARRERA_STATE.decision.opciones.map((op, i) => {
          const ultimaImpar = i === CARRERA_STATE.decision.opciones.length - 1 && CARRERA_STATE.decision.opciones.length % 2 === 1;
          const tipo = op.id === "seguir" || op.id === "volver" ? "Quedarte en" : op.id === "extender" ? "Extender en" : op.id === "definitiva" ? "Ficha fija con" : "Fichar por";
          return `
          <button type="button" class="carrera-decision-card${ultimaImpar ? " carrera-decision-card--centrada" : ""}" data-id="${op.id}" style="animation-delay:${i * 60}ms">
            <span class="carrera-decision-tipo">${tipo}</span>
            <strong>${op.club.nombre}</strong>
            <img class="carrera-decision-escudo" src="escudos/${op.club.escudo}" alt="" onerror="this.style.visibility='hidden'">
            <span class="carrera-decision-liga">${carreraLogoLigaHTML(op.club.liga)}${op.club.liga}</span>
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
        <div class="carrera-atributos">
          <div class="carrera-atributo"><span>Potencial</span><b>${a.potencial}</b><div class="carrera-atributo-barra"><div style="width:${a.potencial}%"></div></div></div>
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
      const badgeDivision = h.cambioDivision === "ascenso" ? `<span class="carrera-badge-ascenso">▲ Ascenso</span>`
        : h.cambioDivision === "descenso" ? `<span class="carrera-badge-descenso">▼ Descenso</span>` : "";
      const badgeLesion = h.lesion ? `<span class="carrera-badge-lesion" title="${h.partidos} PJ por la lesión">🩹 Lesión (${h.lesion.tipo})</span>` : "";
      const badgeSeleccion = h.convocatoria ? `<span class="carrera-badge-seleccion">${carreraBandera(j.pais.iso2)} +${h.convocatoria.presencias}</span>` : "";
      filas.push(`
        <div class="carrera-fila carrera-fila-jugada ${carreraClaseResultado(h.resultadoClub)}" style="animation-delay:${Math.min(filas.length, 10) * 40}ms">
          <div class="carrera-fila-edad">${h.edad}</div>
          <div class="carrera-fila-club">
            <img class="carrera-fila-escudo" src="escudos/${h.escudo}" alt="" onerror="this.style.visibility='hidden'">
            ${carreraLogoLigaHTML(h.liga)}
            <span>${h.club}</span>
            ${badgeDivision}${badgeLesion}${badgeSeleccion}
          </div>
          <div class="carrera-fila-ovr ${carreraClaseOVR(h.generalDespues)}">${h.generalDespues}</div>
          <div class="carrera-fila-num">${h.partidos}</div>
          <div class="carrera-fila-num">⚽ ${h.goles}</div>
          <div class="carrera-fila-num">🅰️ ${h.asistencias}</div>
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
        <div>EDAD</div><div>CLUB</div><div>OVR</div><div>PJ</div><div>GLS</div><div>AST</div>
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
  CARRERA_STATE.jugador.capasSeleccion = 0;
  CARRERA_STATE.jugador.golesSeleccion = 0;
  CARRERA_STATE.jugador.atributos = null;
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
