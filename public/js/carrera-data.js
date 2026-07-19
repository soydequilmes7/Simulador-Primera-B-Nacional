/* =====================================================================
   MODO CARRERA — Datos estáticos
   Países (nombre ES + ISO2, para banderas via emoji) y posiciones de
   cancha. Archivo independiente del resto del simulador de ligas: no
   importa ni depende de public/data*.json.
   ===================================================================== */

// [nombre en español, código ISO 3166-1 alpha-2]
const CARRERA_PAISES = [
  ["Afganistán","AF"],["Albania","AL"],["Alemania","DE"],["Andorra","AD"],["Angola","AO"],
  ["Anguila","AI"],["Antigua y Barbuda","AG"],["Arabia Saudita","SA"],["Argelia","DZ"],["Argentina","AR"],
  ["Armenia","AM"],["Aruba","AW"],["Australia","AU"],["Austria","AT"],["Azerbaiyán","AZ"],
  ["Bahamas","BS"],["Baréin","BH"],["Bangladés","BD"],["Barbados","BB"],["Bélgica","BE"],
  ["Belice","BZ"],["Benín","BJ"],["Bielorrusia","BY"],["Birmania","MM"],["Bolivia","BO"],
  ["Bosnia y Herzegovina","BA"],["Botsuana","BW"],["Brasil","BR"],["Brunéi","BN"],["Bulgaria","BG"],
  ["Burkina Faso","BF"],["Burundi","BI"],["Bután","BT"],["Cabo Verde","CV"],["Camboya","KH"],
  ["Camerún","CM"],["Canadá","CA"],["Catar","QA"],["Chad","TD"],["Chile","CL"],
  ["China","CN"],["Chipre","CY"],["Colombia","CO"],["Comoras","KM"],["Corea del Norte","KP"],
  ["Corea del Sur","KR"],["Costa de Marfil","CI"],["Costa Rica","CR"],["Croacia","HR"],["Cuba","CU"],
  ["Dinamarca","DK"],["Dominica","DM"],["Ecuador","EC"],["Egipto","EG"],["El Salvador","SV"],
  ["Emiratos Árabes Unidos","AE"],["Eritrea","ER"],["Eslovaquia","SK"],["Eslovenia","SI"],["España","ES"],
  ["Estados Unidos","US"],["Estonia","EE"],["Esuatini","SZ"],["Etiopía","ET"],["Filipinas","PH"],
  ["Finlandia","FI"],["Fiyi","FJ"],["Francia","FR"],["Gabón","GA"],["Gambia","GM"],
  ["Georgia","GE"],["Ghana","GH"],["Granada","GD"],["Grecia","GR"],["Guatemala","GT"],
  ["Guinea","GN"],["Guinea-Bisáu","GW"],["Guinea Ecuatorial","GQ"],["Guyana","GY"],["Haití","HT"],
  ["Honduras","HN"],["Hungría","HU"],["India","IN"],["Indonesia","ID"],["Irak","IQ"],
  ["Irán","IR"],["Irlanda","IE"],["Islandia","IS"],["Islas Malvinas","FK"],["Islas Salomón","SB"],
  ["Israel","IL"],["Italia","IT"],["Jamaica","JM"],["Japón","JP"],["Jordania","JO"],
  ["Kazajistán","KZ"],["Kenia","KE"],["Kirguistán","KG"],["Kiribati","KI"],["Kuwait","KW"],
  ["Laos","LA"],["Lesoto","LS"],["Letonia","LV"],["Líbano","LB"],["Liberia","LR"],
  ["Libia","LY"],["Liechtenstein","LI"],["Lituania","LT"],["Luxemburgo","LU"],["Macedonia del Norte","MK"],
  ["Madagascar","MG"],["Malasia","MY"],["Malaui","MW"],["Maldivas","MV"],["Malí","ML"],
  ["Malta","MT"],["Marruecos","MA"],["Mauricio","MU"],["Mauritania","MR"],["México","MX"],
  ["Moldavia","MD"],["Mónaco","MC"],["Mongolia","MN"],["Montenegro","ME"],["Mozambique","MZ"],
  ["Namibia","NA"],["Nauru","NR"],["Nepal","NP"],["Nicaragua","NI"],["Níger","NE"],
  ["Nigeria","NG"],["Noruega","NO"],["Nueva Zelanda","NZ"],["Omán","OM"],["Países Bajos","NL"],
  ["Pakistán","PK"],["Palaos","PW"],["Palestina","PS"],["Panamá","PA"],["Papúa Nueva Guinea","PG"],
  ["Paraguay","PY"],["Perú","PE"],["Polonia","PL"],["Portugal","PT"],["Puerto Rico","PR"],
  ["Reino Unido","GB"],["República Centroafricana","CF"],["República Checa","CZ"],["República Democrática del Congo","CD"],["República Dominicana","DO"],
  ["República del Congo","CG"],["Ruanda","RW"],["Rumanía","RO"],["Rusia","RU"],["Samoa","WS"],
  ["San Marino","SM"],["Santa Lucía","LC"],["Senegal","SN"],["Serbia","RS"],["Seychelles","SC"],
  ["Sierra Leona","SL"],["Singapur","SG"],["Siria","SY"],["Somalia","SO"],["Sri Lanka","LK"],
  ["Sudáfrica","ZA"],["Sudán","SD"],["Sudán del Sur","SS"],["Suecia","SE"],["Suiza","CH"],
  ["Surinam","SR"],["Tailandia","TH"],["Taiwán","TW"],["Tanzania","TZ"],["Tayikistán","TJ"],
  ["Timor Oriental","TL"],["Togo","TG"],["Tonga","TO"],["Trinidad y Tobago","TT"],["Túnez","TN"],
  ["Turkmenistán","TM"],["Turquía","TR"],["Tuvalu","TV"],["Ucrania","UA"],["Uganda","UG"],
  ["Uruguay","UY"],["Uzbekistán","UZ"],["Vanuatu","VU"],["Venezuela","VE"],["Vietnam","VN"],
  ["Yemen","YE"],["Yibuti","DJ"],["Zambia","ZM"],["Zimbabue","ZW"]
];

// Devuelve el <img> de la bandera para un código ISO2 ("AR"), usando
// imágenes reales en vez de emoji: el emoji de bandera no se renderiza
// en Windows (Chrome/Edge ahí muestran solo las dos letras del código).
function carreraBandera(iso2, alt){
  const code = iso2.toLowerCase();
  return `<img class="carrera-bandera-img" src="https://flagcdn.com/w40/${code}.png" srcset="https://flagcdn.com/w80/${code}.png 2x" alt="${alt || ''}" loading="lazy">`;
}

/* =====================================================================
   OFERTAS DE CLUB (cantera) — pool de clubes por país (ISO2), para la
   pantalla que aparece después de confirmar identidad. Argentina usa
   clubes reales de ascenso (Primera C / B Metropolitana) porque un
   juvenil arranca en cantera, no directo en Primera; el resto de los
   países sudamericanos usa clubes de su propia liga (mismos escudos
   que ya tiene el simulador para Libertadores/Sudamericana). Los
   países sin pool propio caen al fallback de Argentina.
   ===================================================================== */
const CARRERA_CLUBES = {
  AR: [
    { nombre:"Berazategui", escudo:"berazategui.png", liga:"Primera C", nivel:38 },
    { nombre:"Cañuelas", escudo:"canuelas.png", liga:"Primera C", nivel:39 },
    { nombre:"Central Ballester", escudo:"centralballester.png", liga:"Primera C", nivel:41 },
    { nombre:"Claypole", escudo:"claypole.png", liga:"Primera C", nivel:30 },
    { nombre:"El Porvenir", escudo:"elporvenir.png", liga:"Primera C", nivel:42 },
    { nombre:"Sacachispas", escudo:"sacachispas.png", liga:"Primera C", nivel:35 },
    { nombre:"Fénix", escudo:"fenix.png", liga:"Primera C", nivel:41 },
    { nombre:"Lugano", escudo:"lugano.png", liga:"Primera C", nivel:37 },
    { nombre:"Atlas", escudo:"atlas.png", liga:"Primera C", nivel:34 },
    { nombre:"Argentino de Merlo", escudo:"argentinomerlo.png", liga:"B Metropolitana", nivel:37 },
    { nombre:"Argentino de Quilmes", escudo:"argquilmes.png", liga:"B Metropolitana", nivel:48 },
    { nombre:"Arsenal de Sarandí", escudo:"arsenal.png", liga:"B Metropolitana", nivel:38 },
    { nombre:"Brown de Adrogué", escudo:"brownadrogue.png", liga:"B Metropolitana", nivel:40 },
    { nombre:"Camioneros", escudo:"camioneros.png", liga:"B Metropolitana", nivel:47 },
    { nombre:"Comunicaciones", escudo:"comunicaciones.png", liga:"B Metropolitana", nivel:45 },
    { nombre:"Deportivo Armenio", escudo:"armenio.png", liga:"B Metropolitana", nivel:42 },
    { nombre:"Laferrere", escudo:"laferrere.png", liga:"B Metropolitana", nivel:45 },
    { nombre:"Deportivo Merlo", escudo:"depmerlo.png", liga:"B Metropolitana", nivel:45 },
    { nombre:"Excursionistas", escudo:"excursionistas.png", liga:"B Metropolitana", nivel:46 },
    { nombre:"Flandria", escudo:"flandria.png", liga:"B Metropolitana", nivel:43 },
    { nombre:"Ituzaingó", escudo:"ituzaingo.png", liga:"B Metropolitana", nivel:43 },
    { nombre:"Liniers", escudo:"liniers.png", liga:"B Metropolitana", nivel:42 },
    { nombre:"Sportivo Italiano", escudo:"spitaliano.png", liga:"B Metropolitana", nivel:48 },
    { nombre:"UAI Urquiza", escudo:"uaiurquiza.png", liga:"B Metropolitana", nivel:48 },
    { nombre:"Villa Dálmine", escudo:"villadalmine.png", liga:"B Metropolitana", nivel:48 },
    { nombre:"Villa San Carlos", escudo:"villasancarlos.png", liga:"B Metropolitana", nivel:39 },
  ],
  BO: [
    { nombre:"Always Ready", escudo:"alwaysready.png", liga:"Liga boliviana", nivel:54 },
    { nombre:"Blooming", escudo:"blooming.png", liga:"Liga boliviana", nivel:50 },
    { nombre:"Bolívar", escudo:"bolivar.png", liga:"Liga boliviana", nivel:54 },
    { nombre:"The Strongest", escudo:"thestrongest.png", liga:"Liga boliviana", nivel:49 },
    { nombre:"Oriente Petrolero", escudo:"orientepetrolero.png", liga:"Liga boliviana", nivel:54 },
    { nombre:"Nacional Potosí", escudo:"nacionalpotosi.png", liga:"Liga boliviana", nivel:56 },
  ],
  BR: [
    { nombre:"Flamengo", escudo:"flamengo.png", liga:"Brasileirão", nivel:72 },
    { nombre:"Palmeiras", escudo:"palmeiras.png", liga:"Brasileirão", nivel:72 },
    { nombre:"Fluminense", escudo:"fluminense.png", liga:"Brasileirão", nivel:70 },
    { nombre:"Cruzeiro", escudo:"cruzeiro.png", liga:"Brasileirão", nivel:74 },
    { nombre:"Corinthians", escudo:"corinthians.png", liga:"Brasileirão", nivel:71 },
    { nombre:"Botafogo", escudo:"botafogo.png", liga:"Brasileirão", nivel:64 },
    { nombre:"Grêmio", escudo:"gremio.png", liga:"Brasileirão", nivel:73 },
    { nombre:"Internacional", escudo:"internacional.png", liga:"Brasileirão", nivel:71 },
    { nombre:"São Paulo", escudo:"saopaulo.png", liga:"Brasileirão", nivel:75 },
    { nombre:"Santos", escudo:"santos.png", liga:"Brasileirão", nivel:69 },
    { nombre:"Bahia", escudo:"bahia.png", liga:"Brasileirão", nivel:73 },
    { nombre:"Mirassol", escudo:"mirassol.png", liga:"Brasileirão", nivel:67 },
    { nombre:"Athletico Paranaense", escudo:"athleticoparanaense.png", liga:"Brasileirão", nivel:58 },
    { nombre:"Atlético Mineiro", escudo:"atleticomineiro.png", liga:"Brasileirão", nivel:74 },
    { nombre:"Chapecoense", escudo:"chapecoense.png", liga:"Brasileirão", nivel:48 },
    { nombre:"Coritiba", escudo:"coritiba.png", liga:"Brasileirão", nivel:46 },
    { nombre:"Red Bull Bragantino", escudo:"redbullbragantino.png", liga:"Brasileirão", nivel:62 },
    { nombre:"Remo", escudo:"remo.png", liga:"Brasileirão", nivel:44 },
    { nombre:"Vasco da Gama", escudo:"vascodagama.png", liga:"Brasileirão", nivel:60 },
    { nombre:"Vitória", escudo:"vitoria.png", liga:"Brasileirão", nivel:50 },
  ],
  CL: [
    { nombre:"Colo-Colo", escudo:"colocolo.png", liga:"Liga chilena", nivel:64 },
    { nombre:"Universidad de Chile", escudo:"universidaddechile.png", liga:"Liga chilena", nivel:60 },
    { nombre:"Universidad Católica", escudo:"universidadcatolica.png", liga:"Liga chilena", nivel:65 },
    { nombre:"Cobresal", escudo:"cobresal.png", liga:"Liga chilena", nivel:57 },
    { nombre:"Huachipato", escudo:"huachipato.png", liga:"Liga chilena", nivel:66 },
    { nombre:"Ñublense", escudo:"nublense.png", liga:"Liga chilena", nivel:59 },
    { nombre:"Unión Española", escudo:"unionespanola.png", liga:"Liga chilena", nivel:64 },
    { nombre:"Coquimbo Unido", escudo:"coquimbo.png", liga:"Liga chilena", nivel:59 },
    { nombre:"O'Higgins", escudo:"ohiggins.png", liga:"Liga chilena", nivel:59 },
  ],
  CO: [
    { nombre:"Millonarios", escudo:"millonarios.png", liga:"Liga colombiana", nivel:63 },
    { nombre:"Atlético Nacional", escudo:"atleticonacional.png", liga:"Liga colombiana", nivel:55 },
    { nombre:"América de Cali", escudo:"americadecali.png", liga:"Liga colombiana", nivel:64 },
    { nombre:"Junior", escudo:"juniorfc.png", liga:"Liga colombiana", nivel:60 },
    { nombre:"Deportivo Cali", escudo:"deportivocali.png", liga:"Liga colombiana", nivel:55 },
    { nombre:"Once Caldas", escudo:"oncecaldas.png", liga:"Liga colombiana", nivel:54 },
    { nombre:"Deportes Tolima", escudo:"tolima.png", liga:"Liga colombiana", nivel:58 },
    { nombre:"Independiente Santa Fe", escudo:"independientesantafe.png", liga:"Liga colombiana", nivel:65 },
    { nombre:"Independiente Medellín", escudo:"independientemedellin.png", liga:"Liga colombiana", nivel:59 },
    { nombre:"Alianza FC", escudo:"alianzafc.png", liga:"Liga colombiana", nivel:45 },
    { nombre:"Atlético Bucaramanga", escudo:"atleticobucaramanga.png", liga:"Liga colombiana", nivel:54 },
    { nombre:"Boyacá Chicó", escudo:"boyacachico.png", liga:"Liga colombiana", nivel:44 },
    { nombre:"Cúcuta Deportivo", escudo:"cucutadeportivo.png", liga:"Liga colombiana", nivel:42 },
    { nombre:"Deportivo Pasto", escudo:"deportivopasto.png", liga:"Liga colombiana", nivel:50 },
    { nombre:"Deportivo Pereira", escudo:"deportivopereira.png", liga:"Liga colombiana", nivel:53 },
    { nombre:"Fortaleza FC", escudo:"fortalezafc.png", liga:"Liga colombiana", nivel:46 },
    { nombre:"Internacional de Bogotá", escudo:"internacionaldebogota.png", liga:"Liga colombiana", nivel:43 },
    { nombre:"Jaguares de Córdoba", escudo:"jaguaresdecordoba.png", liga:"Liga colombiana", nivel:44 },
    { nombre:"Llaneros FC", escudo:"llanerosfc.png", liga:"Liga colombiana", nivel:42 },
    { nombre:"Águilas Doradas", escudo:"aguilasdoradas.png", liga:"Liga colombiana", nivel:48 },
  ],
  EC: [
    { nombre:"Barcelona SC", escudo:"barcelonasc.png", liga:"Liga ecuatoriana", nivel:57 },
    { nombre:"Emelec", escudo:"emelec.png", liga:"Liga ecuatoriana", nivel:62 },
    { nombre:"LDU de Quito", escudo:"ldu.png", liga:"Liga ecuatoriana", nivel:63 },
    { nombre:"Independiente del Valle", escudo:"idv.png", liga:"Liga ecuatoriana", nivel:52 },
    { nombre:"Aucas", escudo:"aucas.png", liga:"Liga ecuatoriana", nivel:59 },
    { nombre:"Deportivo Cuenca", escudo:"deportivocuenca.png", liga:"Liga ecuatoriana", nivel:56 },
    { nombre:"Delfín", escudo:"delfin.png", liga:"Liga ecuatoriana", nivel:55 },
    { nombre:"Guayaquil City", escudo:"guayaquilcity.png", liga:"Liga ecuatoriana", nivel:45 },
    { nombre:"Leones", escudo:"leones_ecu.png", liga:"Liga ecuatoriana", nivel:42 },
    { nombre:"Macará", escudo:"macara.png", liga:"Liga ecuatoriana", nivel:48 },
    { nombre:"Manta", escudo:"manta.png", liga:"Liga ecuatoriana", nivel:43 },
    { nombre:"Mushuc Runa", escudo:"mushucruna.png", liga:"Liga ecuatoriana", nivel:47 },
    { nombre:"Orense", escudo:"orense.png", liga:"Liga ecuatoriana", nivel:46 },
    { nombre:"Técnico Universitario", escudo:"tecnicouniversitario.png", liga:"Liga ecuatoriana", nivel:44 },
    { nombre:"Universidad Católica", escudo:"unversidadcatolicaecu.png", liga:"Liga ecuatoriana", nivel:50 },
  ],
  PY: [
    { nombre:"Cerro Porteño", escudo:"cerroporteno.png", liga:"Liga paraguaya", nivel:56 },
    { nombre:"Olimpia", escudo:"olimpia.png", liga:"Liga paraguaya", nivel:49 },
    { nombre:"Libertad", escudo:"libertad.png", liga:"Liga paraguaya", nivel:49 },
    { nombre:"Guaraní", escudo:"guarani.png", liga:"Liga paraguaya", nivel:49 },
    { nombre:"Nacional", escudo:"nacionalparaguay.png", liga:"Liga paraguaya", nivel:51 },
    { nombre:"Sportivo Luqueño", escudo:"sportivoluqueno.png", liga:"Liga paraguaya", nivel:58 },
  ],
  PE: [
    { nombre:"Alianza Lima", escudo:"alianzalima.png", liga:"Liga peruana", nivel:53 },
    { nombre:"Universitario", escudo:"universitario.png", liga:"Liga peruana", nivel:48 },
    { nombre:"Sporting Cristal", escudo:"sportingcristal.png", liga:"Liga peruana", nivel:50 },
    { nombre:"Melgar", escudo:"melgar.png", liga:"Liga peruana", nivel:60 },
    { nombre:"Cusco FC", escudo:"cuscofc.png", liga:"Liga peruana", nivel:57 },
    { nombre:"Sport Huancayo", escudo:"sporthuancayo.png", liga:"Liga peruana", nivel:54 },
  ],
  UY: [
    { nombre:"Peñarol", escudo:"penarol.png", liga:"Liga uruguaya", nivel:52 },
    { nombre:"Nacional", escudo:"nacional.png", liga:"Liga uruguaya", nivel:54 },
    { nombre:"Danubio", escudo:"danubio.png", liga:"Liga uruguaya", nivel:60 },
    { nombre:"Defensor Sporting", escudo:"defensorsporting.png", liga:"Liga uruguaya", nivel:54 },
    { nombre:"Montevideo Wanderers", escudo:"montevideowanderers.png", liga:"Liga uruguaya", nivel:64 },
    { nombre:"Liverpool FC", escudo:"liverpool.png", liga:"Liga uruguaya", nivel:62 },
    { nombre:"Boston River", escudo:"bostonriver.png", liga:"Liga uruguaya", nivel:55 },
  ],
  VE: [
    { nombre:"Caracas FC", escudo:"caracasfc.png", liga:"Liga venezolana", nivel:53 },
    { nombre:"Deportivo Táchira", escudo:"deportivotachira.png", liga:"Liga venezolana", nivel:47 },
    { nombre:"Deportivo La Guaira", escudo:"deportivolaguaira.png", liga:"Liga venezolana", nivel:46 },
    { nombre:"Monagas", escudo:"monagas.png", liga:"Liga venezolana", nivel:47 },
    { nombre:"Metropolitanos", escudo:"metropolitanos.png", liga:"Liga venezolana", nivel:52 },
    { nombre:"Carabobo", escudo:"carabobo.png", liga:"Liga venezolana", nivel:46 },
  ],
};

// Genera los atributos iniciales del jugador según su posición (grupo
// ataque/mediocampo/defensa/arquero). Se usan para el motor de
// temporadas: definen cuántos minutos consigue y su rendimiento.
const CARRERA_GRUPOS_POSICION = {
  delantero: ["DC", "EI", "ED"],
  medio: ["MCO", "MI", "MD", "MC", "MCD"],
  defensor: ["LI", "LD", "DFC"],
  arquero: ["POR"],
};

function carreraGenerarAtributos(posicion){
  const rnd = (a, b) => Math.round(a + Math.random() * (b - a));
  let ataque, defensa, fisico;
  if (CARRERA_GRUPOS_POSICION.delantero.includes(posicion)) {
    ataque = rnd(55, 68); defensa = rnd(25, 38); fisico = rnd(45, 60);
  } else if (CARRERA_GRUPOS_POSICION.medio.includes(posicion)) {
    ataque = rnd(42, 56); defensa = rnd(40, 54); fisico = rnd(48, 60);
  } else if (CARRERA_GRUPOS_POSICION.defensor.includes(posicion)) {
    ataque = rnd(22, 36); defensa = rnd(55, 68); fisico = rnd(50, 64);
  } else {
    ataque = rnd(10, 20); defensa = rnd(50, 65); fisico = rnd(50, 65);
  }
  const general = Math.round((ataque + defensa + fisico) / 3);
  const potencial = Math.min(94, general + rnd(15, 30));
  return { ataque, defensa, fisico, general, potencial };
}

// Devuelve un array de `cantidad` clubes (sin repetir) para las ofertas
// de cantera, según el país del jugador. Si el país no tiene pool
// propio, cae al pool de Argentina (el simulador solo cubre ligas
// argentinas + Sudamérica, así que un origen sin liga local arranca
// probándose en el ascenso argentino).
function carreraObtenerOfertas(iso2, cantidad){
  const n = cantidad || 3;
  const pool = CARRERA_CLUBES[iso2] || CARRERA_CLUBES.AR;
  const copia = pool.slice();
  const elegidos = [];
  while (copia.length && elegidos.length < n){
    const i = Math.floor(Math.random() * copia.length);
    elegidos.push(copia.splice(i, 1)[0]);
  }
  return elegidos;
}

// ---------------------------------------------------------------------
// Valor de mercado: curva exponencial sobre el general, con bono por
// margen de crecimiento (potencial - general) que pesa más en jugadores
// jóvenes, y un multiplicador por edad (pico ~24-28, cae después de 30).
function carreraValorMercado(atributos, edad){
  const { general, potencial } = atributos;
  let factorEdad;
  if (edad <= 21) factorEdad = 0.7 + (edad - 17) * 0.06;
  else if (edad <= 29) factorEdad = 1.0;
  else factorEdad = Math.max(0.22, 1 - (edad - 29) * 0.13);
  const base = Math.pow(1.108, general) * 850;
  const margen = Math.max(0, potencial - general);
  const bonoPotencial = margen * 3800 * (edad <= 23 ? 1 : 0.35);
  let valor = (base + bonoPotencial) * factorEdad;
  valor = Math.round(valor / 5000) * 5000;
  return Math.max(5000, valor);
}

function carreraFormatoValor(valor){
  if (valor >= 1000000) return "€" + (valor / 1000000).toFixed(valor % 1000000 === 0 ? 0 : 1) + "M";
  if (valor >= 1000) return "€" + Math.round(valor / 1000) + "K";
  return "€" + valor;
}

// Clase CSS por rango de OVR, para el color del badge grande de la ficha.
function carreraClaseOVR(ovr){
  if (ovr >= 80) return "ovr-elite";
  if (ovr >= 70) return "ovr-alto";
  if (ovr >= 60) return "ovr-medio";
  if (ovr >= 45) return "ovr-bajo";
  return "ovr-juvenil";
}

// Pool completo de clubes (todas las nacionalidades) aplanado y sin
// duplicados, con su iso2 de origen. Se usa para armar ofertas de
// préstamo/transferencia a mitad de carrera, sin importar el país
// original del jugador.
function carreraTodosClubes(){
  const vistos = new Set();
  const out = [];
  Object.entries(CARRERA_CLUBES).forEach(([iso2, lista]) => {
    lista.forEach(c => {
      if (!vistos.has(c.nombre)) { vistos.add(c.nombre); out.push({ ...c, iso2 }); }
    });
  });
  return out;
}

// Ofertas de préstamo/transferencia a mitad de carrera: clubes de nivel
// parecido al del jugador (con algo de ruido para variedad), excluyendo
// el club en el que ya está.
function carreraObtenerOfertasPrestamo(nombreClubActual, nivelJugador, cantidad){
  const n = cantidad || 2;
  const candidatos = carreraTodosClubes().filter(c => c.nombre !== nombreClubActual);
  candidatos.forEach(c => { c._dist = Math.abs(c.nivel - nivelJugador) + Math.random() * 10; });
  candidatos.sort((a, b) => a._dist - b._dist);
  const acotado = candidatos.slice(0, Math.min(n * 4, candidatos.length));
  for (let i = acotado.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [acotado[i], acotado[j]] = [acotado[j], acotado[i]];
  }
  return acotado.slice(0, n);
}

// Posiciones de cancha: código, etiqueta y ubicación porcentual (top/left)
// sobre el rectángulo de la cancha, arqueros abajo y delanteros arriba.
const CARRERA_POSICIONES = [
  { code:"DC",  label:"DC",  top:8,  left:50 },
  { code:"EI",  label:"EI",  top:16, left:16 },
  { code:"ED",  label:"ED",  top:16, left:84 },
  { code:"MCO", label:"MCO", top:32, left:50 },
  { code:"MI",  label:"MI",  top:46, left:18 },
  { code:"MD",  label:"MD",  top:46, left:82 },
  { code:"MC",  label:"MC",  top:46, left:50 },
  { code:"MCD", label:"MCD", top:60, left:50 },
  { code:"LI",  label:"LI",  top:74, left:16 },
  { code:"LD",  label:"LD",  top:74, left:84 },
  { code:"DFC", label:"DFC", top:78, left:50 },
  { code:"POR", label:"POR", top:93, left:50 }
];
