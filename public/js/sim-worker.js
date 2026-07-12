// sim-worker.js
//
// Web Worker que corre las simulaciones (Primera Nacional, LPF, Copa,
// B Metro, Federal A, Primera C, Copa Libertadores y Copa Sudamericana)
// adentro del navegador con Pyodide, para no pegarle al backend cada vez
// que el usuario aprieta "Correr nueva simulación". Usa exactamente el
// mismo código Python que el backend (main.py, main_lpf.py,
// main_bmetro.py, main_federal.py, main_primerac.py, main_libertadores.py,
// main_sudamericana.py, modelos/, pysim_dispatch.py): lo pide vía
// /api/pysim-source y lo escribe en el filesystem virtual de Pyodide,
// junto con los CSV actuales (/api/datos-nacional, /api/datos-lpf,
// /api/datos-copa, /api/datos-bmetro, /api/datos-federal,
// /api/datos-primerac, /api/datos-libertadores y /api/datos-sudamericana).
// No reimplementa ninguna lógica de simulación en JS.
//
// Protocolo de mensajes (postMessage):
//   main -> worker: { type: "init", apiBase: string }
//   main -> worker: { type: "run", id, tarea, payload }
//   worker -> main: { type: "status", phase, message? }
//     fases: "loading-pyodide" | "loading-packages" | "loading-code" | "ready" | "error"
//   worker -> main: { type: "result", id, ok, data? , error?, status? }

const PYODIDE_VERSION = "0.26.4";
const PYODIDE_CDN = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;

let apiBase = "";
let pyodide = null;
let pysimDispatch = null;
let readyPromise = null;

self.onmessage = async (event) => {
  const msg = event.data || {};

  if (msg.type === "init") {
    apiBase = msg.apiBase || "";
    if (!readyPromise) {
      readyPromise = inicializar().catch((err) => {
        postMessage({ type: "status", phase: "error", message: describirError(err) });
        throw err;
      });
    }
    return;
  }

  if (msg.type === "run") {
    const { id, tarea, payload } = msg;
    try {
      if (!readyPromise) throw new Error("El worker no fue inicializado (falta el mensaje 'init').");
      await readyPromise;
      const data = await ejecutar(tarea, payload || {});
      postMessage({ type: "result", id, ok: true, data });
    } catch (err) {
      postMessage({
        type: "result",
        id,
        ok: false,
        error: describirError(err),
        status: err && err.status,
      });
    }
  }
};

async function inicializar() {
  postMessage({ type: "status", phase: "loading-pyodide" });
  importScripts(PYODIDE_CDN + "pyodide.js");
  pyodide = await loadPyodide({ indexURL: PYODIDE_CDN });

  postMessage({ type: "status", phase: "loading-packages" });
  await pyodide.loadPackage(["numpy", "pandas"]);

  postMessage({ type: "status", phase: "loading-code" });
  await cargarCodigoYDatos();

  postMessage({ type: "status", phase: "ready" });
}

async function cargarCodigoYDatos() {
  const [fuente, datosNacional, datosLpf, datosCopa, datosBmetro, datosFederal, datosPrimeraC, datosLibertadores, datosSudamericana] = await Promise.all([
    fetchJson(`${apiBase}/api/pysim-source`),
    fetchJson(`${apiBase}/api/datos-nacional`),
    fetchJson(`${apiBase}/api/datos-lpf`),
    fetchJson(`${apiBase}/api/datos-copa`),
    fetchJson(`${apiBase}/api/datos-bmetro`),
    fetchJson(`${apiBase}/api/datos-federal`),
    fetchJson(`${apiBase}/api/datos-primerac`),
    fetchJson(`${apiBase}/api/datos-libertadores`),
    fetchJson(`${apiBase}/api/datos-sudamericana`),
  ]);

  escribirArchivos(fuente.files, "");
  escribirArchivos(datosNacional.files, "datos");
  escribirArchivos(datosLpf.files, "datos");
  escribirArchivos(datosCopa.files, "datos");
  escribirArchivos(datosBmetro.files, "datos");
  escribirArchivos(datosFederal.files, "datos");
  escribirArchivos(datosPrimeraC.files, "datos");
  escribirArchivos(datosLibertadores.files, "datos");
  escribirArchivos(datosSudamericana.files, "datos");

  pyodide.runPython(
    "import sys\n" +
    "if '/home/pyodide' not in sys.path:\n" +
    "    sys.path.insert(0, '/home/pyodide')\n" +
    "import pysim_dispatch\n"
  );
  pysimDispatch = pyodide.pyimport("pysim_dispatch");
}

function escribirArchivos(archivos, subdir) {
  for (const [nombreRelativo, contenido] of Object.entries(archivos || {})) {
    const relPath = subdir ? `${subdir}/${nombreRelativo}` : nombreRelativo;
    const fullPath = `/home/pyodide/${relPath}`;
    const dir = fullPath.slice(0, fullPath.lastIndexOf("/"));
    pyodide.FS.mkdirTree(dir);
    pyodide.FS.writeFile(fullPath, contenido);
  }
}

async function fetchJson(url) {
  const respuesta = await fetch(url);
  const cuerpo = await respuesta.json().catch(() => ({}));
  if (!respuesta.ok) {
    const err = new Error(cuerpo.error || `Error ${respuesta.status} pidiendo ${url}`);
    err.status = respuesta.status;
    throw err;
  }
  return cuerpo;
}

function clamp(n, min, max, porDefecto) {
  n = Number(n);
  if (!Number.isFinite(n)) n = porDefecto;
  return Math.max(min, Math.min(max, n));
}

async function ejecutar(tarea, payload) {
  let kwargs;
  switch (tarea) {
    case "simular":
      kwargs = { n_sims: clamp(payload.n_sims, 50, 5000, 500) };
      break;
    case "simular-lpf":
      kwargs = { n_sims: clamp(payload.n_sims, 50, 5000, 500) };
      break;
    case "simular-copa":
      kwargs = { n_sims: clamp(payload.n_sims, 50, 5000, 500) };
      break;
    case "simular-bmetro":
      kwargs = { n_sims: clamp(payload.n_sims, 50, 5000, 500) };
      break;
    case "simular-federal":
      kwargs = { n_sims: clamp(payload.n_sims, 50, 5000, 500) };
      break;
    case "simular-primerac":
      kwargs = { n_sims: clamp(payload.n_sims, 50, 5000, 500) };
      break;
    case "simular-libertadores":
      kwargs = { n_sims: clamp(payload.n_sims, 50, 5000, 1000) };
      break;
    case "simular-sudamericana":
      kwargs = { n_sims: clamp(payload.n_sims, 50, 5000, 1000) };
      break;
    case "simular-campeon":
    case "simular-campeon-lpf":
    case "simular-campeon-copa":
    case "simular-campeon-bmetro":
    case "simular-campeon-federal":
    case "simular-campeon-primerac":
    case "simular-campeon-libertadores":
    case "simular-campeon-sudamericana": {
      const equipo = String(payload.equipo || "").trim();
      if (!equipo) throw Object.assign(new Error("Falta indicar el equipo"), { status: 400 });
      kwargs = { equipo, max_intentos: clamp(payload.max_intentos, 100, 20000, 5000) };
      break;
    }
    default:
      throw new Error(`Tarea desconocida: ${tarea}`);
  }

  const resultadoJson = pysimDispatch.ejecutar_tarea_json(tarea, JSON.stringify(kwargs));
  const resultado = JSON.parse(resultadoJson);
  if (!resultado.ok) {
    throw Object.assign(new Error(resultado.error), { status: resultado.status });
  }
  return resultado.data;
}

function describirError(err) {
  if (!err) return "Error desconocido";
  return err.message || String(err);
}
