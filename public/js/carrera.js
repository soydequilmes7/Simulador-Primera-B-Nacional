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
  decision: null     // { opciones:[{id,label,club,prestamo,dueñoNuevo}] } pendiente tras simular
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
    <div class="carrera-oferta-card">
      <img class="carrera-oferta-escudo" src="escudos/${club.escudo}" alt="" loading="lazy" onerror="this.style.visibility='hidden'">
      <h3>${club.nombre}</h3>
      <p class="carrera-oferta-liga">${club.liga}</p>
      <button type="button" class="btn-carrera-primary carrera-oferta-btn" data-i="${i}">Fichar</button>
    </div>`).join("");
  cont.querySelectorAll(".carrera-oferta-btn").forEach(btn => {
    btn.addEventListener("click", () => carreraElegirClub(CARRERA_STATE.ofertas[+btn.dataset.i]));
  });
}

function carreraElegirClub(club){
  CARRERA_STATE.jugador.club = club;
  CARRERA_STATE.jugador.clubDueño = club;
  CARRERA_STATE.jugador.enPrestamo = false;
  CARRERA_STATE.jugador.edad = 17;
  CARRERA_STATE.jugador.atributos = carreraGenerarAtributos(CARRERA_STATE.jugador.posicion);
  CARRERA_STATE.temporada = 0;
  CARRERA_STATE.historial = [];
  CARRERA_STATE.titulos = [];
  CARRERA_STATE.decision = null;
  carreraMostrarDashboard();
}

/* ---------- Motor de temporada (resumen directo, simulación aparte) ---------- */
function carreraSimularTemporada(){
  const j = CARRERA_STATE.jugador;
  const club = j.club;
  const edadDeLaTemporada = j.edad;

  // Oportunidades: cuánto juega según la brecha entre su nivel y el del club.
  const diff = j.atributos.general - (club.nivel || 45);
  let chance = 45 + diff * 1.6;
  chance = Math.max(5, Math.min(95, chance));
  const PARTIDOS_TEMPORADA = 30;
  const ruidoMinutos = 0.7 + Math.random() * 0.5;
  let partidos = Math.round(PARTIDOS_TEMPORADA * (chance / 100) * ruidoMinutos);
  partidos = Math.max(0, Math.min(PARTIDOS_TEMPORADA, partidos));

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

  // Resultado del club (simulación aparte, sin fixture real).
  const rollClub = (club.nivel || 45) + (Math.random() * 30 - 15);
  let resultadoClub;
  if (rollClub >= 80) resultadoClub = "Campeón";
  else if (rollClub >= 65) resultadoClub = "Clasificó a copas internacionales";
  else if (rollClub >= 45) resultadoClub = "Mitad de tabla";
  else if (rollClub >= 30) resultadoClub = "Peleó el descenso";
  else resultadoClub = "Descendió";

  // Progresión: crece si juega y todavía no llegó al potencial; declina con la edad.
  const generalAntes = j.atributos.general;
  let crecimiento;
  if (partidos >= 18) crecimiento = Math.round(Math.random() * 3) + 1;
  else if (partidos >= 8) crecimiento = Math.round(Math.random() * 2);
  else crecimiento = Math.round(Math.random() * 2) - 1;
  if (edadDeLaTemporada >= 30) crecimiento -= 1;
  const generalDespues = Math.max(1, Math.min(j.atributos.potencial, generalAntes + crecimiento));
  j.atributos.general = generalDespues;
  j.edad = edadDeLaTemporada + 1;
  CARRERA_STATE.temporada += 1;

  CARRERA_STATE.historial.unshift({
    temporada: CARRERA_STATE.temporada, edad: edadDeLaTemporada, club: club.nombre, resultadoClub,
    partidos, goles, asistencias, valoracion, generalAntes, generalDespues
  });

  if (resultadoClub === "Campeón") {
    CARRERA_STATE.titulos.unshift({
      temporada: CARRERA_STATE.temporada, edad: j.edad, club: club.nombre, liga: club.liga
    });
  }

  carreraGenerarDecision();
  carreraMostrarDashboard();
}

/* ---------- Préstamos / continuidad: decisión post-temporada ---------- */
// Arma las opciones que se muestran en el panel de decisión del dashboard
// después de simular una temporada. Si el jugador está a préstamo, puede
// volver a su club dueño, firmar ficha definitiva con el club prestador,
// o extender el préstamo un año más. Si no está a préstamo, puede
// quedarse en su club o aceptar una de dos ofertas de préstamo.
function carreraGenerarDecision(){
  const j = CARRERA_STATE.jugador;
  const opciones = [];
  if (j.enPrestamo) {
    opciones.push({ id:"volver", label:`Volver a ${j.clubDueño.nombre}`, club:j.clubDueño, prestamo:false });
    opciones.push({ id:"definitiva", label:`Ficha definitiva con ${j.club.nombre}`, club:j.club, prestamo:false, dueñoNuevo:true });
    opciones.push({ id:"extender", label:`Extender préstamo en ${j.club.nombre}`, club:j.club, prestamo:true });
  } else {
    opciones.push({ id:"seguir", label:`Quedarte en ${j.club.nombre}`, club:j.club, prestamo:false });
    const ofertas = carreraObtenerOfertasPrestamo(j.club.nombre, j.atributos.general, 2);
    ofertas.forEach((c, i) => {
      opciones.push({ id:"prestamo"+i, label:`Préstamo a ${c.nombre}`, club:c, prestamo:true });
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
  j.club = op.club;
  j.enPrestamo = !!op.prestamo;
  if (op.dueñoNuevo) j.clubDueño = op.club;
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

  const vitrinaHTML = CARRERA_STATE.titulos.length ? `
    <div class="carrera-vitrina">
      <h4>Vitrina</h4>
      <div class="carrera-vitrina-lista">
        ${CARRERA_STATE.titulos.map(t => `<span class="carrera-vitrina-item">🏆 ${t.liga} · ${t.edad} años</span>`).join("")}
      </div>
    </div>` : "";

  const decisionHTML = CARRERA_STATE.decision ? `
    <div class="carrera-decision">
      <h3>${j.enPrestamo ? "Fin del préstamo — ¿qué hacés?" : "¿Seguís en el club o probás un préstamo?"}</h3>
      <div class="carrera-decision-grid">
        ${CARRERA_STATE.decision.opciones.map(op => `
          <button type="button" class="carrera-decision-card" data-id="${op.id}">
            <img class="carrera-decision-escudo" src="escudos/${op.club.escudo}" alt="" onerror="this.style.visibility='hidden'">
            <strong>${op.club.nombre}</strong>
            <span>${op.club.liga}</span>
            <em>${op.label}</em>
          </button>`).join("")}
      </div>
    </div>` : `
    <button type="button" class="btn-carrera-primary carrera-btn-temporada" id="btn-carrera-jugar-temporada">Jugar Temporada ${CARRERA_STATE.temporada + 1}</button>`;

  const timelineHTML = CARRERA_STATE.historial.length ? `
    <div class="carrera-timeline">
      <h3>Trayectoria</h3>
      ${CARRERA_STATE.historial.slice().reverse().map(h => `
        <div class="carrera-timeline-item">
          <div class="carrera-timeline-edad">${h.edad}<span>años</span></div>
          <div class="carrera-timeline-col carrera-timeline-club"><b>${h.club}</b><span>${h.resultadoClub}</span></div>
          <div class="carrera-timeline-col">${h.partidos} PJ · ${h.goles} G · ${h.asistencias} A</div>
          <div class="carrera-timeline-col carrera-timeline-rating">${h.valoracion}</div>
          <div class="carrera-timeline-ovr ${carreraClaseOVR(h.generalDespues)}">${h.generalDespues}</div>
        </div>`).join("")}
    </div>` : `<p class="carrera-oferta-sub">Todavía no jugaste ninguna temporada.</p>`;

  dash.innerHTML = `
    <div class="carrera-dash-grid">
      <div class="carrera-tarjeta">
        <div class="carrera-tarjeta-top">
          <div class="carrera-ovr-badge ${claseOVR}">${a.general}<span>OVR</span></div>
          <div class="carrera-tarjeta-id">
            <h2>${j.apellido.trim().toUpperCase()} <span class="carrera-resumen-num">#${j.numero}</span></h2>
            <p class="carrera-tarjeta-meta">${carreraBandera(j.pais.iso2)} ${j.pais.nombre} · ${j.posicion} · ${j.edad} años</p>
          </div>
        </div>
        <div class="carrera-tarjeta-valor">Valor de mercado <b>${valor}</b></div>
        <div class="carrera-resumen-club">
          <img class="carrera-resumen-club-escudo" src="escudos/${j.club.escudo}" alt="" onerror="this.style.visibility='hidden'">
          <div>
            <strong>${j.club.nombre}${j.enPrestamo ? " (préstamo)" : ""}</strong>
            <span>${j.club.liga}${j.enPrestamo ? " · Dueño: " + j.clubDueño.nombre : ""}</span>
          </div>
        </div>
        <div class="carrera-tarjeta-stats">
          <div><b>${totales.pj}</b><span>PJ</span></div>
          <div><b>${totales.goles}</b><span>Goles</span></div>
          <div><b>${totales.asist}</b><span>Asist.</span></div>
        </div>
        <div class="carrera-atributos">
          <div class="carrera-atributo"><span>Potencial</span><b>${a.potencial}</b><div class="carrera-atributo-barra"><div style="width:${a.potencial}%"></div></div></div>
          <div class="carrera-atributo"><span>Ataque</span><b>${a.ataque}</b><div class="carrera-atributo-barra"><div style="width:${a.ataque}%"></div></div></div>
          <div class="carrera-atributo"><span>Defensa</span><b>${a.defensa}</b><div class="carrera-atributo-barra"><div style="width:${a.defensa}%"></div></div></div>
          <div class="carrera-atributo"><span>Físico</span><b>${a.fisico}</b><div class="carrera-atributo-barra"><div style="width:${a.fisico}%"></div></div></div>
        </div>
        ${vitrinaHTML}
        <button type="button" class="btn-carrera-secondary" id="btn-carrera-editar">Editar identidad</button>
      </div>
      <div class="carrera-dash-derecha">
        ${decisionHTML}
        ${timelineHTML}
      </div>
    </div>`;

  const btnTemporada = document.getElementById("btn-carrera-jugar-temporada");
  if (btnTemporada) btnTemporada.addEventListener("click", carreraSimularTemporada);

  dash.querySelectorAll(".carrera-decision-card").forEach(btn => {
    btn.addEventListener("click", () => carreraResolverDecision(btn.dataset.id));
  });

  document.getElementById("btn-carrera-editar").addEventListener("click", () => {
    CARRERA_STATE.jugador.club = null;
    CARRERA_STATE.jugador.clubDueño = null;
    CARRERA_STATE.jugador.enPrestamo = false;
    CARRERA_STATE.jugador.edad = null;
    CARRERA_STATE.jugador.atributos = null;
    CARRERA_STATE.temporada = 0;
    CARRERA_STATE.historial = [];
    CARRERA_STATE.titulos = [];
    CARRERA_STATE.decision = null;
    carreraMostrarIdentidad();
  });
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
    if (isNaN(n)) n = "";
    else n = Math.max(1, Math.min(99, n));
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
