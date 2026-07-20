// public/js/dt.js
//
// Modo Carrera DT -- diseño nuevo de punta a punta, no reutiliza nada
// del viejo Modo Carrera de jugador. Todo el estado vive en memoria en
// DT_STATE (se pierde al recargar la página, mismo criterio que
// ESTADO_TEMPORADA_LOCAL de Modo Temporada) -- no hay nada que
// persistir en Supabase acá, ver season/dt_carrera.py.
//
// Depende de globals ya definidos en el <script> principal de
// template.html: apiUrl(), apiFetch(), apiResponseError(), escudoHTML().
// Como este archivo solo define funciones (no ejecuta nada al cargar,
// salvo lo que dispara initDT() cuando se abre la pestaña), no importa
// que el <script src> de este archivo esté ANTES en el documento que
// esas definiciones -- para cuando el usuario interactúa, todo ya está
// cargado.

let DT_STATE = {
  reputacion: 10,
  club: null,              // {nombre, division, factor_prestigio}
  rating: null,             // {ataque_local, ataque_visitante, defensa_local, defensa_visitante}
  objetivo: null,           // slug, ej. "playoffs"
  objetivoDesc: "",
  presupuesto: 100,
  rivalesPool: [],
  rivalIndex: 0,
  rivalActual: null,
  ratingRivalActual: null,
  puntos: 0,
  partidosJugados: 0,
  partidosTotales: 10,
  temporadasFallidas: 0,
  numeroTemporada: 0,
  historial: [],
  formacionSel: "4-4-2",
  mentalidadSel: "equilibrada",
};

const DT_COSTO_FICHAJE = 25;
const DT_CATEGORIAS = ["arquero", "defensa", "mediocampo", "ataque"];

let DT_INIT_DONE = false;

function initDT() {
  actualizarBadgeReputacion();
  if (DT_INIT_DONE) return;
  DT_INIT_DONE = true;

  document.getElementById("dt-btn-buscar-club").addEventListener("click", dtCargarOfertas);
  document.getElementById("dt-btn-buscar-otro").addEventListener("click", dtCargarOfertas);
  document.getElementById("dt-btn-arrancar-temporada").addEventListener("click", dtArrancarTemporada);
  document.getElementById("dt-btn-jugar").addEventListener("click", dtJugarPartido);
  document.getElementById("dt-btn-siguiente").addEventListener("click", dtSiguientePartido);
  document.getElementById("dt-btn-seguir").addEventListener("click", dtSeguirEnElClub);

  document.getElementById("dt-formacion-row").addEventListener("click", (ev) => {
    const opt = ev.target.closest(".dt-opt");
    if (!opt) return;
    dtSeleccionar(document.getElementById("dt-formacion-row"), opt);
    DT_STATE.formacionSel = opt.dataset.formacion;
  });
  document.getElementById("dt-mentalidad-row").addEventListener("click", (ev) => {
    const opt = ev.target.closest(".dt-opt");
    if (!opt) return;
    dtSeleccionar(document.getElementById("dt-mentalidad-row"), opt);
    DT_STATE.mentalidadSel = opt.dataset.mentalidad;
  });
}

function dtSeleccionar(fila, opt) {
  fila.querySelectorAll(".dt-opt").forEach((o) => o.classList.remove("sel"));
  opt.classList.add("sel");
}

function dtMostrarPantalla(id) {
  document.querySelectorAll("#vista-dt .dt-screen").forEach((s) => (s.hidden = s.id !== id));
}

function actualizarBadgeReputacion() {
  const el = document.getElementById("dt-rep-inicio");
  if (el) el.textContent = DT_STATE.reputacion;
}

async function dtPost(path, body) {
  const respuesta = await apiFetch(apiUrl(path), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const cuerpo = await respuesta.json();
  if (!respuesta.ok) throw apiResponseError(respuesta, cuerpo);
  return cuerpo;
}

function dtSetStatus(elId, mensaje, esError) {
  const el = document.getElementById(elId);
  if (!el) return;
  el.textContent = mensaje || "";
  el.classList.toggle("error", Boolean(esError));
}

// ---------------------------------------------------------------------
// Pantalla 1 -> 2: ofertas de clubes
// ---------------------------------------------------------------------

async function dtCargarOfertas() {
  dtSetStatus("dt-status-inicio", "Golpeando puertas...");
  dtSetStatus("dt-status-ofertas", "Golpeando puertas...");
  dtMostrarPantalla("dt-ofertas");
  try {
    const cuerpo = await dtPost("/api/dt/ofertas", { reputacion: DT_STATE.reputacion, cantidad: 3 });
    const grid = document.getElementById("dt-ofertas-grid");
    if (!cuerpo.ofertas.length) {
      grid.innerHTML = "";
      dtSetStatus("dt-status-ofertas", "Nadie te llamó esta vez. Probá de nuevo en un rato.", true);
      return;
    }
    grid.innerHTML = cuerpo.ofertas.map((c, i) => `
      <div class="dt-club-card" data-idx="${i}">
        ${escudoHTML(c.nombre)}
        <h3>${c.nombre}</h3>
        <div class="dt-club-liga">${DT_NOMBRE_DIVISION[c.division] || c.division}</div>
      </div>
    `).join("");
    grid.querySelectorAll(".dt-club-card").forEach((card) => {
      card.addEventListener("click", () => dtElegirClub(cuerpo.ofertas[Number(card.dataset.idx)]));
    });
    dtSetStatus("dt-status-ofertas", "");
  } catch (e) {
    dtSetStatus("dt-status-ofertas", "No se pudo traer las ofertas: " + e.message, true);
  }
}

const DT_NOMBRE_DIVISION = {
  lpf: "Liga Profesional",
  nacional: "Primera Nacional",
  bmetro: "B Metropolitana",
  federal_a: "Federal A",
  primerac: "Primera C",
};

// ---------------------------------------------------------------------
// Pantalla 2 -> 3: firmar contrato y pretemporada
// ---------------------------------------------------------------------

async function dtElegirClub(club) {
  dtSetStatus("dt-status-ofertas", "Firmando contrato...");
  try {
    const [objetivoResp, ratingResp, poolResp] = await Promise.all([
      dtPost("/api/dt/objetivo", club),
      dtPost("/api/dt/rating-inicial", { factor_prestigio: club.factor_prestigio }),
      dtPost("/api/dt/ofertas", { reputacion: 100, divisiones: [club.division], cantidad: 8 }),
    ]);
    DT_STATE.club = club;
    DT_STATE.objetivo = objetivoResp.objetivo;
    DT_STATE.objetivoDesc = objetivoResp.descripcion;
    DT_STATE.rating = ratingResp;
    DT_STATE.rivalesPool = poolResp.ofertas.filter((c) => c.nombre !== club.nombre);
    DT_STATE.rivalIndex = 0;
    DT_STATE.presupuesto = 100;
    DT_STATE.puntos = 0;
    DT_STATE.partidosJugados = 0;
    DT_STATE.numeroTemporada += 1;
    dtRenderPretemporada();
    dtMostrarPantalla("dt-pretemporada");
  } catch (e) {
    dtSetStatus("dt-status-ofertas", "No se pudo cerrar el pase: " + e.message, true);
  }
}

function dtRenderPretemporada() {
  document.getElementById("dt-pre-club-liga").textContent = DT_NOMBRE_DIVISION[DT_STATE.club.division] || DT_STATE.club.division;
  document.getElementById("dt-pre-club-nombre").textContent = DT_STATE.club.nombre;
  document.getElementById("dt-pre-objetivo").textContent = DT_STATE.objetivoDesc;
  document.getElementById("dt-presupuesto-num").textContent = DT_STATE.presupuesto;
  document.getElementById("dt-fichaje-log").textContent = "";
  const grid = document.getElementById("dt-mercado-grid");
  grid.innerHTML = DT_CATEGORIAS.map((cat) => `
    <button class="dt-mercado-card" data-cat="${cat}">
      <div class="dt-cat">${cat}</div>
      <div class="dt-cat-costo">${DT_COSTO_FICHAJE} pts</div>
    </button>
  `).join("");
  grid.querySelectorAll(".dt-mercado-card").forEach((btn) => {
    btn.addEventListener("click", () => dtFichar(btn.dataset.cat));
  });
  dtActualizarDisabledMercado();
}

function dtActualizarDisabledMercado() {
  document.getElementById("dt-presupuesto-num").textContent = DT_STATE.presupuesto;
  document.querySelectorAll("#dt-mercado-grid .dt-mercado-card").forEach((btn) => {
    btn.disabled = DT_STATE.presupuesto < DT_COSTO_FICHAJE;
  });
}

async function dtFichar(categoria) {
  try {
    const cuerpo = await dtPost("/api/dt/mercado/fichar", { categoria });
    DT_STATE.rating[cuerpo.campo_rating] = Math.round((DT_STATE.rating[cuerpo.campo_rating] + cuerpo.delta_rating) * 10000) / 10000;
    DT_STATE.presupuesto -= cuerpo.costo;
    document.getElementById("dt-fichaje-log").innerHTML =
      `<b>${categoria}:</b> ${cuerpo.texto} (${cuerpo.resultado})`;
    dtActualizarDisabledMercado();
  } catch (e) {
    document.getElementById("dt-fichaje-log").textContent = "No se pudo fichar: " + e.message;
  }
}

// ---------------------------------------------------------------------
// Pantalla 3 -> 4: previa del partido
// ---------------------------------------------------------------------

async function dtArrancarTemporada() {
  await dtProximoPartido();
}

async function dtProximoPartido() {
  document.getElementById("dt-btn-jugar").disabled = true;
  dtSetStatus("dt-status-partido", "Buscando rival...");
  try {
    if (!DT_STATE.rivalesPool.length) {
      dtSetStatus("dt-status-partido", "No hay rivales disponibles en esta división.", true);
      return;
    }
    const rival = DT_STATE.rivalesPool[DT_STATE.rivalIndex % DT_STATE.rivalesPool.length];
    DT_STATE.rivalIndex += 1;
    DT_STATE.rivalActual = rival;
    DT_STATE.ratingRivalActual = await dtPost("/api/dt/rating-inicial", { factor_prestigio: rival.factor_prestigio });

    document.getElementById("dt-partido-contexto").textContent =
      `Fecha ${DT_STATE.partidosJugados + 1} de ${DT_STATE.partidosTotales}`;
    document.getElementById("dt-vs-local").innerHTML = `${escudoHTML(DT_STATE.club.nombre)}<div class="nombre">${DT_STATE.club.nombre}</div>`;
    document.getElementById("dt-vs-rival").innerHTML = `${escudoHTML(rival.nombre)}<div class="nombre">${rival.nombre}</div>`;
    dtSetStatus("dt-status-partido", "");
    dtMostrarPantalla("dt-partido");
  } catch (e) {
    dtSetStatus("dt-status-partido", "No se pudo armar el partido: " + e.message, true);
  } finally {
    document.getElementById("dt-btn-jugar").disabled = false;
  }
}

// ---------------------------------------------------------------------
// Pantalla 4 -> 5: jugar y ver el feed en vivo
// ---------------------------------------------------------------------

async function dtJugarPartido() {
  const boton = document.getElementById("dt-btn-jugar");
  boton.disabled = true;
  dtSetStatus("dt-status-partido", "Jugando...");
  try {
    const cuerpo = await dtPost("/api/dt/partido/jugar", {
      rating_dt: DT_STATE.rating,
      rating_rival: DT_STATE.ratingRivalActual,
      formacion: DT_STATE.formacionSel,
      mentalidad: DT_STATE.mentalidadSel,
    });
    dtSetStatus("dt-status-partido", "");
    dtMostrarFeed(cuerpo);
  } catch (e) {
    dtSetStatus("dt-status-partido", "No se pudo resolver el partido: " + e.message, true);
    boton.disabled = false;
  }
}

function dtMostrarFeed(resultado) {
  document.getElementById("dt-feed-local").textContent = DT_STATE.club.nombre;
  document.getElementById("dt-feed-visitante").textContent = DT_STATE.rivalActual.nombre;
  document.getElementById("dt-feed-goles-local").textContent = "0";
  document.getElementById("dt-feed-goles-visitante").textContent = "0";
  const lista = document.getElementById("dt-feed-lista");
  lista.innerHTML = "";
  document.getElementById("dt-btn-siguiente").hidden = true;
  dtMostrarPantalla("dt-feed");

  resultado.eventos.forEach((evento, i) => {
    setTimeout(() => {
      const fila = document.createElement("div");
      fila.className = "dt-evento" + (evento.gol ? " gol" : "");
      fila.innerHTML = `<span class="min">${evento.minuto}'</span><span class="txt">${evento.equipo === "local" ? DT_STATE.club.nombre : DT_STATE.rivalActual.nombre} -- ${evento.texto}</span>`;
      lista.appendChild(fila);
      lista.scrollTop = lista.scrollHeight;
      document.getElementById("dt-feed-goles-local").textContent = evento.marcador_local;
      document.getElementById("dt-feed-goles-visitante").textContent = evento.marcador_visitante;

      if (i === resultado.eventos.length - 1) {
        DT_STATE.puntos += resultado.goles_local > resultado.goles_visitante ? 3
          : resultado.goles_local === resultado.goles_visitante ? 1 : 0;
        DT_STATE.partidosJugados += 1;
        document.getElementById("dt-btn-jugar").disabled = false;
        document.getElementById("dt-btn-siguiente").hidden = false;
      }
    }, i * 320);
  });
}

// ---------------------------------------------------------------------
// Pantalla 5 -> 6 (o de vuelta a 4): siguiente fecha o evaluación
// ---------------------------------------------------------------------

async function dtSiguientePartido() {
  if (DT_STATE.partidosJugados < DT_STATE.partidosTotales) {
    await dtProximoPartido();
  } else {
    await dtEvaluarTemporada();
  }
}

async function dtEvaluarTemporada() {
  dtMostrarPantalla("dt-evaluacion");
  document.getElementById("dt-veredicto").textContent = "Evaluando la temporada...";
  document.getElementById("dt-veredicto").className = "veredicto";
  document.getElementById("dt-rep-delta").textContent = "";
  try {
    const cuerpo = await dtPost("/api/dt/temporada/evaluar", {
      objetivo: DT_STATE.objetivo,
      puntos: DT_STATE.puntos,
      partidos_jugados: DT_STATE.partidosTotales,
      temporadas_fallidas_previas: DT_STATE.temporadasFallidas,
    });
    DT_STATE.reputacion = Math.max(0, Math.min(100, DT_STATE.reputacion + cuerpo.delta_reputacion));
    DT_STATE.temporadasFallidas = cuerpo.cumplido ? 0 : DT_STATE.temporadasFallidas + 1;
    DT_STATE.historial.unshift({
      numero: DT_STATE.numeroTemporada,
      club: DT_STATE.club.nombre,
      cumplido: cuerpo.cumplido,
      despedido: cuerpo.despedido,
    });
    actualizarBadgeReputacion();

    const veredictoEl = document.getElementById("dt-veredicto");
    veredictoEl.textContent = cuerpo.despedido ? "Te echaron"
      : cuerpo.cumplido ? "Objetivo cumplido" : "Objetivo no cumplido";
    veredictoEl.classList.add(cuerpo.cumplido ? "ok" : "mal");
    document.getElementById("dt-rep-delta").textContent =
      `Reputación ${cuerpo.delta_reputacion >= 0 ? "+" : ""}${cuerpo.delta_reputacion} -- ahora en ${DT_STATE.reputacion}`;

    document.getElementById("dt-btn-seguir").hidden = cuerpo.despedido;
    dtRenderHistorial();
  } catch (e) {
    document.getElementById("dt-veredicto").textContent = "No se pudo evaluar la temporada.";
    document.getElementById("dt-rep-delta").textContent = e.message;
  }
}

function dtRenderHistorial() {
  const cont = document.getElementById("dt-historial");
  if (!DT_STATE.historial.length) { cont.innerHTML = ""; return; }
  cont.innerHTML = DT_STATE.historial.map((t) => `
    <div class="dt-historial-fila">
      <span class="n">T${t.numero}</span>
      <span class="club">${t.club}</span>
      <span class="res ${t.cumplido ? "ok" : "mal"}">${t.despedido ? "despedido" : t.cumplido ? "cumplido" : "fallido"}</span>
    </div>
  `).join("");
}

async function dtSeguirEnElClub() {
  try {
    const objetivoResp = await dtPost("/api/dt/objetivo", DT_STATE.club);
    DT_STATE.objetivo = objetivoResp.objetivo;
    DT_STATE.objetivoDesc = objetivoResp.descripcion;
    DT_STATE.presupuesto = 100;
    DT_STATE.puntos = 0;
    DT_STATE.partidosJugados = 0;
    DT_STATE.numeroTemporada += 1;
    dtRenderPretemporada();
    dtMostrarPantalla("dt-pretemporada");
  } catch (e) {
    dtSetStatus("dt-status-ofertas", "No se pudo arrancar la temporada siguiente: " + e.message, true);
  }
}
