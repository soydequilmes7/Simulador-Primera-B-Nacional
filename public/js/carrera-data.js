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

// Continentes cubiertos por el simulador (para el pool "local" de ofertas
// de préstamo/transferencia más abajo -- ver carreraContinente). No se
// limita a los países que YA tienen clubes cargados en CARRERA_CLUBES para
// que sumar un país nuevo al dataset no requiera tocar esta lista aparte.
const CARRERA_ISO2_SUDAMERICA = ["AR","BO","BR","CL","CO","EC","GY","PY","PE","SR","UY","VE"];
const CARRERA_ISO2_EUROPA = [
  "AL","AD","AT","BY","BE","BA","BG","HR","CY","CZ","DK","EE","FI","FR","DE","GR","HU","IS","IE",
  "IT","LV","LI","LT","LU","MT","MD","MC","ME","NL","MK","NO","PL","PT","RO","RU","SM","RS","SK",
  "SI","ES","SE","CH","TR","UA","GB"
];

// Continente de un país (por ISO2), o null si no es Sudamérica ni Europa
// (el simulador solo cubre esos dos por ahora).
function carreraContinente(iso2){
  if (CARRERA_ISO2_SUDAMERICA.includes(iso2)) return "sudamerica";
  if (CARRERA_ISO2_EUROPA.includes(iso2)) return "europa";
  return null;
}

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
    { nombre:"Berazategui", escudo:"berazategui.png", liga:"Primera C", nivel:22 },
    { nombre:"Cañuelas", escudo:"canuelas.png", liga:"Primera C", nivel:23 },
    { nombre:"Central Ballester", escudo:"centralballester.png", liga:"Primera C", nivel:24 },
    { nombre:"Claypole", escudo:"claypole.png", liga:"Primera C", nivel:18 },
    { nombre:"El Porvenir", escudo:"elporvenir.png", liga:"Primera C", nivel:25 },
    { nombre:"Sacachispas", escudo:"sacachispas.png", liga:"Primera C", nivel:21 },
    { nombre:"Fénix", escudo:"fenix.png", liga:"Primera C", nivel:24 },
    { nombre:"Lugano", escudo:"lugano.png", liga:"Primera C", nivel:22 },
    { nombre:"Atlas", escudo:"atlas.png", liga:"Primera C", nivel:20 },
    { nombre:"Argentino de Merlo", escudo:"argentinomerlo.png", liga:"B Metropolitana", nivel:22 },
    { nombre:"Argentino de Quilmes", escudo:"argquilmes.png", liga:"B Metropolitana", nivel:28 },
    { nombre:"Arsenal de Sarandí", escudo:"arsenal.png", liga:"B Metropolitana", nivel:22 },
    { nombre:"Brown de Adrogué", escudo:"brownadrogue.png", liga:"B Metropolitana", nivel:24 },
    { nombre:"Camioneros", escudo:"camioneros.png", liga:"B Metropolitana", nivel:27 },
    { nombre:"Comunicaciones", escudo:"comunicaciones.png", liga:"B Metropolitana", nivel:26 },
    { nombre:"Deportivo Armenio", escudo:"armenio.png", liga:"B Metropolitana", nivel:25 },
    { nombre:"Laferrere", escudo:"laferrere.png", liga:"B Metropolitana", nivel:26 },
    { nombre:"Deportivo Merlo", escudo:"depmerlo.png", liga:"B Metropolitana", nivel:26 },
    { nombre:"Excursionistas", escudo:"excursionistas.png", liga:"B Metropolitana", nivel:27 },
    { nombre:"Flandria", escudo:"flandria.png", liga:"B Metropolitana", nivel:25 },
    { nombre:"Ituzaingó", escudo:"ituzaingo.png", liga:"B Metropolitana", nivel:25 },
    { nombre:"Liniers", escudo:"liniers.png", liga:"B Metropolitana", nivel:25 },
    { nombre:"Sportivo Italiano", escudo:"spitaliano.png", liga:"B Metropolitana", nivel:28 },
    { nombre:"UAI Urquiza", escudo:"uaiurquiza.png", liga:"B Metropolitana", nivel:28 },
    { nombre:"Villa Dálmine", escudo:"villadalmine.png", liga:"B Metropolitana", nivel:28 },
    { nombre:"Villa San Carlos", escudo:"villasancarlos.png", liga:"B Metropolitana", nivel:23 },
    // Primera Nacional (segunda división argentina) — escalón intermedio entre
    // el ascenso (Primera C / B Metropolitana) y la Liga Profesional, para que
    // la carrera pueda subir de división en división en vez de saltar directo
    // a Primera. Mismos escudos/slugs que usa el simulador de ligas.
    { nombre:"Chacarita", escudo:"chacarita.png", liga:"Primera Nacional", nivel:39 },
    { nombre:"Quilmes", escudo:"quilmes.png", liga:"Primera Nacional", nivel:41 },
    { nombre:"Almagro", escudo:"almagro.png", liga:"Primera Nacional", nivel:38 },
    { nombre:"Atlanta", escudo:"atlanta.png", liga:"Primera Nacional", nivel:37 },
    { nombre:"Chicago", escudo:"nueva_chicago.png", liga:"Primera Nacional", nivel:38 },
    { nombre:"Colón", escudo:"colon.png", liga:"Primera Nacional", nivel:43 },
    { nombre:"Agropecuario", escudo:"agropecuario.png", liga:"Primera Nacional", nivel:33 },
    { nombre:"All Boys", escudo:"allboys.png", liga:"Primera Nacional", nivel:34 },
    { nombre:"Alte. Brown", escudo:"almirante.png", liga:"Primera Nacional", nivel:35 },
    { nombre:"Atlético Rafaela", escudo:"atleticorafaela.png", liga:"Primera Nacional", nivel:39 },
    { nombre:"Estudiantes (Caseros)", escudo:"estudiantes_caseros.png", liga:"Primera Nacional", nivel:32 },
    { nombre:"Ferro", escudo:"ferro.png", liga:"Primera Nacional", nivel:38 },
    { nombre:"Gimnasia (J)", escudo:"gimnasiajujuy.png", liga:"Primera Nacional", nivel:34 },
    { nombre:"Gimnasia y Tiro", escudo:"gimnasia_y_tiro.png", liga:"Primera Nacional", nivel:33 },
    { nombre:"Godoy Cruz", escudo:"godoycruz.png", liga:"Primera Nacional", nivel:42 },
    { nombre:"Güemes", escudo:"guemes.png", liga:"Primera Nacional", nivel:35 },
    { nombre:"Los Andes", escudo:"los_andes.png", liga:"Primera Nacional", nivel:31 },
    { nombre:"Maipú", escudo:"depmaipu.png", liga:"Primera Nacional", nivel:41 },
    { nombre:"Midland", escudo:"midland.png", liga:"Primera Nacional", nivel:30 },
    { nombre:"Morón", escudo:"moron.png", liga:"Primera Nacional", nivel:36 },
    { nombre:"Patronato", escudo:"patronato.png", liga:"Primera Nacional", nivel:39 },
    { nombre:"San Martín (SJ)", escudo:"sanmartinsj.png", liga:"Primera Nacional", nivel:35 },
    { nombre:"San Martín (T)", escudo:"sanmartintuc.png", liga:"Primera Nacional", nivel:36 },
    { nombre:"San Miguel", escudo:"sanmiguel.png", liga:"Primera Nacional", nivel:32 },
    { nombre:"San Telmo", escudo:"santelmo.png", liga:"Primera Nacional", nivel:31 },
    { nombre:"Temperley", escudo:"temperley.png", liga:"Primera Nacional", nivel:35 },
    { nombre:"Tristán Suárez", escudo:"tristansuarez.png", liga:"Primera Nacional", nivel:32 },
    // Liga Profesional (primera división argentina) — techo de la carrera
    // dentro del fútbol local, antes de que empiecen a llegar ofertas del
    // exterior (ver UMBRAL_OFERTA_EXTERIOR en carreraObtenerOfertasPrestamo).
    { nombre:"River Plate", escudo:"river.png", liga:"Liga Profesional", nivel:76 },
    { nombre:"Boca Juniors", escudo:"boca.png", liga:"Liga Profesional", nivel:75 },
    { nombre:"Racing Club", escudo:"racing.png", liga:"Liga Profesional", nivel:85 },
    { nombre:"Talleres de Córdoba", escudo:"talleres.png", liga:"Liga Profesional", nivel:66 },
    { nombre:"Vélez Sarsfield", escudo:"velez.png", liga:"Liga Profesional", nivel:65 },
    { nombre:"Estudiantes de La Plata", escudo:"estudiantes.png", liga:"Liga Profesional", nivel:63 },
    { nombre:"Independiente", escudo:"independiente.png", liga:"Liga Profesional", nivel:84 },
    { nombre:"San Lorenzo", escudo:"sanlorenzo.png", liga:"Liga Profesional", nivel:48 },
    { nombre:"Rosario Central", escudo:"rosariocentral.png", liga:"Liga Profesional", nivel:62 },
    { nombre:"Argentinos Juniors", escudo:"argentinos.png", liga:"Liga Profesional", nivel:62 },
    { nombre:"Huracán", escudo:"huracan.png", liga:"Liga Profesional", nivel:61 },
    { nombre:"Defensa y Justicia", escudo:"defensa.png", liga:"Liga Profesional", nivel:61 },
    { nombre:"Newell's Old Boys", escudo:"newells.png", liga:"Liga Profesional", nivel:60 },
    { nombre:"Lanús", escudo:"lanus.png", liga:"Liga Profesional", nivel:59 },
    { nombre:"Unión de Santa Fe", escudo:"union.png", liga:"Liga Profesional", nivel:57 },
    { nombre:"Gimnasia La Plata", escudo:"gimnasia.png", liga:"Liga Profesional", nivel:55 },
    { nombre:"Belgrano", escudo:"belgrano.png", liga:"Liga Profesional", nivel:55 },
    { nombre:"Central Córdoba (SdE)", escudo:"centralcordoba3.png", liga:"Liga Profesional", nivel:55 },
    { nombre:"Atlético Tucumán", escudo:"atleticotucuman.png", liga:"Liga Profesional", nivel:54 },
    { nombre:"Instituto", escudo:"instituto.png", liga:"Liga Profesional", nivel:53 },
    { nombre:"Tigre", escudo:"tigre.png", liga:"Liga Profesional", nivel:52 },
    { nombre:"Platense", escudo:"platense.png", liga:"Liga Profesional", nivel:51 },
    { nombre:"Banfield", escudo:"banfield.png", liga:"Liga Profesional", nivel:51 },
    { nombre:"Barracas Central", escudo:"barracas.png", liga:"Liga Profesional", nivel:53 },
    { nombre:"Sarmiento (Junín)", escudo:"sarmiento.png", liga:"Liga Profesional", nivel:50 },
    { nombre:"Independiente Rivadavia", escudo:"independienteriv.png", liga:"Liga Profesional", nivel:48 },
    { nombre:"Deportivo Riestra", escudo:"riestra.png", liga:"Liga Profesional", nivel:47 },
    { nombre:"Estudiantes RC", escudo:"estudiantesrc.png", liga:"Liga Profesional", nivel:44 },
    { nombre:"Gimnasia de Mendoza", escudo:"gimnasiamendoza.png", liga:"Liga Profesional", nivel:44 },
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
  // ===== Europa (Fase 4) — 352 clubes, 22 ligas, tiers 3/4/5 =====
  AT: [
    { nombre:"Austria Viena", escudo:"austriavienna.png", liga:"Bundesliga (Austria)", nivel:62 },
    { nombre:"Blau-Weiss Linz", escudo:"fcblauweisslinz.png", liga:"Bundesliga (Austria)", nivel:66 },
    { nombre:"Grazer AK", escudo:"grazerak1902.png", liga:"Bundesliga (Austria)", nivel:63 },
    { nombre:"LASK", escudo:"lask.png", liga:"Bundesliga (Austria)", nivel:66 },
    { nombre:"Rapid Viena", escudo:"rapidvienna.png", liga:"Bundesliga (Austria)", nivel:64 },
    { nombre:"Red Bull Salzburg", escudo:"redbullsalzburg.png", liga:"Bundesliga (Austria)", nivel:64 },
    { nombre:"SCR Altach", escudo:"scraltach.png", liga:"Bundesliga (Austria)", nivel:74 },
    { nombre:"SK Sturm Graz", escudo:"sksturmgraz.png", liga:"Bundesliga (Austria)", nivel:72 },
    { nombre:"SV Ried", escudo:"svried.png", liga:"Bundesliga (Austria)", nivel:69 },
    { nombre:"TSV Hartberg", escudo:"tsvhartberg.png", liga:"Bundesliga (Austria)", nivel:64 },
    { nombre:"Wolfsberger AC", escudo:"wolfsbergerac.png", liga:"Bundesliga (Austria)", nivel:62 },
    { nombre:"WSG Tirol", escudo:"wsgtirol.png", liga:"Bundesliga (Austria)", nivel:72 },
  ],
  BE: [
    { nombre:"Cercle Brugge", escudo:"cerclebrugge.png", liga:"Jupiler Pro League", nivel:62 },
    { nombre:"Club Brugge KV", escudo:"clubbruggekv.png", liga:"Jupiler Pro League", nivel:78 },
    { nombre:"FCV Dender EH", escudo:"fcvdendereh.png", liga:"Jupiler Pro League", nivel:68 },
    { nombre:"KAA Gent", escudo:"kaagent.png", liga:"Jupiler Pro League", nivel:63 },
    { nombre:"KRC Genk", escudo:"krcgenk.png", liga:"Jupiler Pro League", nivel:67 },
    { nombre:"KVC Westerlo", escudo:"kvcwesterlo.png", liga:"Jupiler Pro League", nivel:67 },
    { nombre:"KV Mechelen", escudo:"kvmechelen.png", liga:"Jupiler Pro League", nivel:72 },
    { nombre:"OH Leuven", escudo:"oudheverleeleuven.png", liga:"Jupiler Pro League", nivel:64 },
    { nombre:"RAAL La Louvière", escudo:"raallalouviere.png", liga:"Jupiler Pro League", nivel:69 },
    { nombre:"Royal Antwerp FC", escudo:"royalantwerpfc.png", liga:"Jupiler Pro League", nivel:71 },
    { nombre:"Royal Charleroi SC", escudo:"royalcharleroisc.png", liga:"Jupiler Pro League", nivel:70 },
    { nombre:"RSC Anderlecht", escudo:"rscanderlecht.png", liga:"Jupiler Pro League", nivel:76 },
    { nombre:"Sint-Truidense VV", escudo:"sinttruidensevv.png", liga:"Jupiler Pro League", nivel:62 },
    { nombre:"Standard de Lieja", escudo:"standardliege.png", liga:"Jupiler Pro League", nivel:65 },
    { nombre:"Union Saint-Gilloise", escudo:"unionsaintgilloise.png", liga:"Jupiler Pro League", nivel:75 },
    { nombre:"Zulte Waregem", escudo:"zultewaregem.png", liga:"Jupiler Pro League", nivel:70 },
  ],
  BG: [
    { nombre:"Arda Kardzhali", escudo:"ardakardzhali.png", liga:"efbet Liga", nivel:71 },
    { nombre:"Beroe Stara Zagora", escudo:"beroestarazagora.png", liga:"efbet Liga", nivel:70 },
    { nombre:"Botev Plovdiv", escudo:"botevplovdiv.png", liga:"efbet Liga", nivel:64 },
    { nombre:"Botev Vratsa", escudo:"botevvratsa.png", liga:"efbet Liga", nivel:68 },
    { nombre:"Chernomorets Varna", escudo:"chernomorevarna.png", liga:"efbet Liga", nivel:62 },
    { nombre:"CSKA 1948", escudo:"cska1948.png", liga:"efbet Liga", nivel:67 },
    { nombre:"CSKA Sofía", escudo:"cskasofia.png", liga:"efbet Liga", nivel:66 },
    { nombre:"Dobrudzha Dobrich", escudo:"dobrudzhadobrich.png", liga:"efbet Liga", nivel:70 },
    { nombre:"Levski Sofía", escudo:"levskisofia.png", liga:"efbet Liga", nivel:70 },
    { nombre:"Lokomotiv Plovdiv", escudo:"lokomotivplovdiv.png", liga:"efbet Liga", nivel:72 },
    { nombre:"Lokomotiv Sofía", escudo:"lokomotivsofia.png", liga:"efbet Liga", nivel:68 },
    { nombre:"Ludogorets Razgrad", escudo:"ludogoretsrazgrad.png", liga:"efbet Liga", nivel:74 },
    { nombre:"Montana", escudo:"montana.png", liga:"efbet Liga", nivel:62 },
    { nombre:"Septemvri Sofía", escudo:"septemvrisofia.png", liga:"efbet Liga", nivel:65 },
    { nombre:"Slavia Sofía", escudo:"slaviasofia.png", liga:"efbet Liga", nivel:65 },
    { nombre:"Spartak Varna", escudo:"spartakvarna.png", liga:"efbet Liga", nivel:72 },
  ],
  HR: [
    { nombre:"GNK Dinamo Zagreb", escudo:"gnkdinamozagreb.png", liga:"SuperSport HNL", nivel:75 },
    { nombre:"HNK Gorica", escudo:"hnkgorica.png", liga:"SuperSport HNL", nivel:69 },
    { nombre:"HNK Hajduk Split", escudo:"hnkhajduksplit.png", liga:"SuperSport HNL", nivel:69 },
    { nombre:"HNK Rijeka", escudo:"hnkrijeka.png", liga:"SuperSport HNL", nivel:66 },
    { nombre:"NK Vukovar 1991", escudo:"hnkvukovar1991.png", liga:"SuperSport HNL", nivel:69 },
    { nombre:"NK Istra 1961", escudo:"nkistra1961.png", liga:"SuperSport HNL", nivel:73 },
    { nombre:"NK Lokomotiva Zagreb", escudo:"nklokomotivazagreb.png", liga:"SuperSport HNL", nivel:68 },
    { nombre:"NK Osijek", escudo:"nkosijek.png", liga:"SuperSport HNL", nivel:62 },
    { nombre:"NK Varaždin", escudo:"nkvarazdin.png", liga:"SuperSport HNL", nivel:67 },
    { nombre:"NK Slaven Belupo", escudo:"slavenbelupokoprivnica.png", liga:"SuperSport HNL", nivel:71 },
  ],
  CZ: [
    { nombre:"1.FC Slovácko", escudo:"1fcslovacko.png", liga:"Chance Liga", nivel:71 },
    { nombre:"AC Sparta Praga", escudo:"acspartaprague.png", liga:"Chance Liga", nivel:71 },
    { nombre:"Bohemians Praga 1905", escudo:"bohemiansprague1905.png", liga:"Chance Liga", nivel:64 },
    { nombre:"FC Baník Ostrava", escudo:"fcbanikostrava.png", liga:"Chance Liga", nivel:72 },
    { nombre:"FC Hradec Králové", escudo:"fchradeckralove.png", liga:"Chance Liga", nivel:73 },
    { nombre:"FC Slovan Liberec", escudo:"fcslovanliberec.png", liga:"Chance Liga", nivel:65 },
    { nombre:"FC Viktoria Plzeň", escudo:"fcviktoriaplzen.png", liga:"Chance Liga", nivel:65 },
    { nombre:"FC Zlín", escudo:"fczlin.png", liga:"Chance Liga", nivel:67 },
    { nombre:"FK Dukla Praga", escudo:"fkduklaprague.png", liga:"Chance Liga", nivel:70 },
    { nombre:"FK Jablonec", escudo:"fkjablonec.png", liga:"Chance Liga", nivel:72 },
    { nombre:"FK Mladá Boleslav", escudo:"fkmladaboleslav.png", liga:"Chance Liga", nivel:66 },
    { nombre:"FK Pardubice", escudo:"fkpardubice.png", liga:"Chance Liga", nivel:63 },
    { nombre:"FK Teplice", escudo:"fkteplice.png", liga:"Chance Liga", nivel:64 },
    { nombre:"MFK Karviná", escudo:"mfkkarvina.png", liga:"Chance Liga", nivel:74 },
    { nombre:"SK Sigma Olomouc", escudo:"sksigmaolomouc.png", liga:"Chance Liga", nivel:73 },
    { nombre:"SK Slavia Praga", escudo:"skslaviaprague.png", liga:"Chance Liga", nivel:72 },
  ],
  DK: [
    { nombre:"Aarhus GF", escudo:"aarhusgf.png", liga:"Superliga (Dinamarca)", nivel:64 },
    { nombre:"Brøndby IF", escudo:"brondbyif.png", liga:"Superliga (Dinamarca)", nivel:73 },
    { nombre:"FC Copenhague", escudo:"fccopenhagen.png", liga:"Superliga (Dinamarca)", nivel:76 },
    { nombre:"FC Fredericia", escudo:"fcfredericia.png", liga:"Superliga (Dinamarca)", nivel:63 },
    { nombre:"FC Midtjylland", escudo:"fcmidtjylland.png", liga:"Superliga (Dinamarca)", nivel:74 },
    { nombre:"FC Nordsjælland", escudo:"fcnordsjaelland.png", liga:"Superliga (Dinamarca)", nivel:71 },
    { nombre:"Odense Boldklub", escudo:"odenseboldklub.png", liga:"Superliga (Dinamarca)", nivel:62 },
    { nombre:"Randers FC", escudo:"randersfc.png", liga:"Superliga (Dinamarca)", nivel:64 },
    { nombre:"Silkeborg IF", escudo:"silkeborgif.png", liga:"Superliga (Dinamarca)", nivel:64 },
    { nombre:"SønderjyskE", escudo:"sonderjyske.png", liga:"Superliga (Dinamarca)", nivel:68 },
    { nombre:"Vejle Boldklub", escudo:"vejleboldklub.png", liga:"Superliga (Dinamarca)", nivel:73 },
    { nombre:"Viborg FF", escudo:"viborgff.png", liga:"Superliga (Dinamarca)", nivel:73 },
  ],
  "GB-ENG": [
    { nombre:"AFC Bournemouth", escudo:"afcbournemouth.png", liga:"Premier League", nivel:89 },
    { nombre:"Arsenal FC", escudo:"arsenalfc.png", liga:"Premier League", nivel:94 },
    { nombre:"Aston Villa", escudo:"astonvilla.png", liga:"Premier League", nivel:92 },
    { nombre:"Brentford FC", escudo:"brentfordfc.png", liga:"Premier League", nivel:94 },
    { nombre:"Brighton & Hove Albion", escudo:"brightonhovealbion.png", liga:"Premier League", nivel:90 },
    { nombre:"Burnley FC", escudo:"burnleyfc.png", liga:"Premier League", nivel:85 },
    { nombre:"Chelsea FC", escudo:"chelseafc.png", liga:"Premier League", nivel:99 },
    { nombre:"Crystal Palace", escudo:"crystalpalace.png", liga:"Premier League", nivel:91 },
    { nombre:"Everton FC", escudo:"evertonfc.png", liga:"Premier League", nivel:85 },
    { nombre:"Fulham FC", escudo:"fulhamfc.png", liga:"Premier League", nivel:88 },
    { nombre:"Leeds United", escudo:"leedsunited.png", liga:"Premier League", nivel:84 },
    { nombre:"Liverpool FC", escudo:"liverpoolfc.png", liga:"Premier League", nivel:99 },
    { nombre:"Manchester City", escudo:"manchestercity.png", liga:"Premier League", nivel:99 },
    { nombre:"Manchester United", escudo:"manchesterunited.png", liga:"Premier League", nivel:97 },
    { nombre:"Newcastle United", escudo:"newcastleunited.png", liga:"Premier League", nivel:92 },
    { nombre:"Nottingham Forest", escudo:"nottinghamforest.png", liga:"Premier League", nivel:93 },
    { nombre:"Sunderland AFC", escudo:"sunderlandafc.png", liga:"Premier League", nivel:91 },
    { nombre:"Tottenham Hotspur", escudo:"tottenhamhotspur.png", liga:"Premier League", nivel:99 },
    { nombre:"West Ham United", escudo:"westhamunited.png", liga:"Premier League", nivel:87 },
    { nombre:"Wolverhampton Wanderers", escudo:"wolverhamptonwanderers.png", liga:"Premier League", nivel:86 },
  ],
  FR: [
    { nombre:"AJ Auxerre", escudo:"ajauxerre.png", liga:"Ligue 1", nivel:83 },
    { nombre:"Angers SCO", escudo:"angerssco.png", liga:"Ligue 1", nivel:77 },
    { nombre:"AS Mónaco", escudo:"asmonaco.png", liga:"Ligue 1", nivel:81 },
    { nombre:"FC Lorient", escudo:"fclorient.png", liga:"Ligue 1", nivel:83 },
    { nombre:"FC Metz", escudo:"fcmetz.png", liga:"Ligue 1", nivel:80 },
    { nombre:"FC Nantes", escudo:"fcnantes.png", liga:"Ligue 1", nivel:77 },
    { nombre:"FC Toulouse", escudo:"fctoulouse.png", liga:"Ligue 1", nivel:76 },
    { nombre:"Le Havre AC", escudo:"lehavreac.png", liga:"Ligue 1", nivel:81 },
    { nombre:"LOSC Lille", escudo:"losclille.png", liga:"Ligue 1", nivel:74 },
    { nombre:"OGC Niza", escudo:"ogcnice.png", liga:"Ligue 1", nivel:79 },
    { nombre:"Olympique de Lyon", escudo:"olympiquelyon.png", liga:"Ligue 1", nivel:84 },
    { nombre:"Olympique de Marsella", escudo:"olympiquemarseille.png", liga:"Ligue 1", nivel:82 },
    { nombre:"Paris FC", escudo:"parisfc.png", liga:"Ligue 1", nivel:83 },
    { nombre:"Paris Saint-Germain", escudo:"parissaintgermain.png", liga:"Ligue 1", nivel:90 },
    { nombre:"RC Lens", escudo:"rclens.png", liga:"Ligue 1", nivel:77 },
    { nombre:"RC Strasbourg Alsace", escudo:"rcstrasbourgalsace.png", liga:"Ligue 1", nivel:80 },
    { nombre:"Stade Brestois 29", escudo:"stadebrestois29.png", liga:"Ligue 1", nivel:83 },
    { nombre:"Stade Rennais FC", escudo:"staderennaisfc.png", liga:"Ligue 1", nivel:73 },
  ],
  DE: [
    { nombre:"1.FC Heidenheim 1846", escudo:"1fcheidenheim1846.png", liga:"Bundesliga (Alemania)", nivel:86 },
    { nombre:"1.FC Köln", escudo:"1fckoln.png", liga:"Bundesliga (Alemania)", nivel:89 },
    { nombre:"1.FC Union Berlin", escudo:"1fcunionberlin.png", liga:"Bundesliga (Alemania)", nivel:83 },
    { nombre:"1.FSV Mainz 05", escudo:"1fsvmainz05.png", liga:"Bundesliga (Alemania)", nivel:91 },
    { nombre:"Bayer 04 Leverkusen", escudo:"bayer04leverkusen.png", liga:"Bundesliga (Alemania)", nivel:99 },
    { nombre:"Bayern Múnich", escudo:"bayernmunich.png", liga:"Bundesliga (Alemania)", nivel:99 },
    { nombre:"Borussia Dortmund", escudo:"borussiadortmund.png", liga:"Bundesliga (Alemania)", nivel:99 },
    { nombre:"Borussia Mönchengladbach", escudo:"borussiamonchengladbach.png", liga:"Bundesliga (Alemania)", nivel:89 },
    { nombre:"Eintracht Frankfurt", escudo:"eintrachtfrankfurt.png", liga:"Bundesliga (Alemania)", nivel:83 },
    { nombre:"FC Augsburgo", escudo:"fcaugsburg.png", liga:"Bundesliga (Alemania)", nivel:90 },
    { nombre:"FC St. Pauli", escudo:"fcstpauli.png", liga:"Bundesliga (Alemania)", nivel:90 },
    { nombre:"Hamburger SV", escudo:"hamburgersv.png", liga:"Bundesliga (Alemania)", nivel:91 },
    { nombre:"RB Leipzig", escudo:"rbleipzig.png", liga:"Bundesliga (Alemania)", nivel:98 },
    { nombre:"SC Friburgo", escudo:"scfreiburg.png", liga:"Bundesliga (Alemania)", nivel:91 },
    { nombre:"SV Werder Bremen", escudo:"svwerderbremen.png", liga:"Bundesliga (Alemania)", nivel:84 },
    { nombre:"TSG 1899 Hoffenheim", escudo:"tsg1899hoffenheim.png", liga:"Bundesliga (Alemania)", nivel:83 },
    { nombre:"VfB Stuttgart", escudo:"vfbstuttgart.png", liga:"Bundesliga (Alemania)", nivel:87 },
    { nombre:"VfL Wolfsburgo", escudo:"vflwolfsburg.png", liga:"Bundesliga (Alemania)", nivel:85 },
  ],
  GR: [
    { nombre:"AEK Atenas", escudo:"aekathens.png", liga:"Super League 1", nivel:75 },
    { nombre:"AE Kifisiás", escudo:"aekifisias.png", liga:"Super League 1", nivel:70 },
    { nombre:"AEL Larisa", escudo:"aelarisa.png", liga:"Super League 1", nivel:64 },
    { nombre:"Levadiakos", escudo:"apolevadiakos.png", liga:"Super League 1", nivel:68 },
    { nombre:"Aris Salónica", escudo:"aristhessaloniki.png", liga:"Super League 1", nivel:71 },
    { nombre:"Asteras Tripolis", escudo:"asterasaktor.png", liga:"Super League 1", nivel:65 },
    { nombre:"Atromitos Atenas", escudo:"atromitosathens.png", liga:"Super League 1", nivel:65 },
    { nombre:"OFI Creta FC", escudo:"oficretefc.png", liga:"Super League 1", nivel:69 },
    { nombre:"Olympiacos El Pireo", escudo:"olympiacospiraeus.png", liga:"Super League 1", nivel:80 },
    { nombre:"Panathinaikos FC", escudo:"panathinaikosfc.png", liga:"Super League 1", nivel:74 },
    { nombre:"Panetolikos GFS", escudo:"panetolikosgfs.png", liga:"Super League 1", nivel:73 },
    { nombre:"Panserraikos", escudo:"panserraikos.png", liga:"Super League 1", nivel:72 },
    { nombre:"PAOK Salónica", escudo:"paokthessaloniki.png", liga:"Super League 1", nivel:70 },
    { nombre:"Volos NPS", escudo:"volosnps.png", liga:"Super League 1", nivel:72 },
  ],
  IT: [
    { nombre:"ACF Fiorentina", escudo:"acffiorentina.png", liga:"Serie A", nivel:85 },
    { nombre:"AC Milan", escudo:"acmilan.png", liga:"Serie A", nivel:99 },
    { nombre:"AS Roma", escudo:"asroma.png", liga:"Serie A", nivel:91 },
    { nombre:"Atalanta BC", escudo:"atalantabc.png", liga:"Serie A", nivel:87 },
    { nombre:"Bologna FC 1909", escudo:"bolognafc1909.png", liga:"Serie A", nivel:90 },
    { nombre:"Cagliari Calcio", escudo:"cagliaricalcio.png", liga:"Serie A", nivel:93 },
    { nombre:"Como 1907", escudo:"como1907.png", liga:"Serie A", nivel:90 },
    { nombre:"Genoa CFC", escudo:"genoacfc.png", liga:"Serie A", nivel:87 },
    { nombre:"Hellas Verona", escudo:"hellasverona.png", liga:"Serie A", nivel:93 },
    { nombre:"Inter de Milán", escudo:"intermilan.png", liga:"Serie A", nivel:99 },
    { nombre:"Juventus FC", escudo:"juventusfc.png", liga:"Serie A", nivel:99 },
    { nombre:"Parma Calcio 1913", escudo:"parmacalcio1913.png", liga:"Serie A", nivel:89 },
    { nombre:"Pisa Sporting Club", escudo:"pisasportingclub.png", liga:"Serie A", nivel:91 },
    { nombre:"SSC Nápoles", escudo:"sscnapoli.png", liga:"Serie A", nivel:90 },
    { nombre:"SS Lazio", escudo:"sslazio.png", liga:"Serie A", nivel:92 },
    { nombre:"Torino FC", escudo:"torinofc.png", liga:"Serie A", nivel:89 },
    { nombre:"Udinese Calcio", escudo:"udinesecalcio.png", liga:"Serie A", nivel:92 },
    { nombre:"US Cremonese", escudo:"uscremonese.png", liga:"Serie A", nivel:86 },
    { nombre:"US Lecce", escudo:"uslecce.png", liga:"Serie A", nivel:92 },
    { nombre:"US Sassuolo", escudo:"ussassuolo.png", liga:"Serie A", nivel:83 },
  ],
  NL: [
    { nombre:"Ajax Ámsterdam", escudo:"ajaxamsterdam.png", liga:"Eredivisie", nivel:89 },
    { nombre:"AZ Alkmaar", escudo:"azalkmaar.png", liga:"Eredivisie", nivel:80 },
    { nombre:"Excelsior Rotterdam", escudo:"excelsiorrotterdam.png", liga:"Eredivisie", nivel:83 },
    { nombre:"FC Groningen", escudo:"fcgroningen.png", liga:"Eredivisie", nivel:80 },
    { nombre:"FC Utrecht", escudo:"fcutrecht.png", liga:"Eredivisie", nivel:82 },
    { nombre:"FC Volendam", escudo:"fcvolendam.png", liga:"Eredivisie", nivel:73 },
    { nombre:"Feyenoord Rotterdam", escudo:"feyenoordrotterdam.png", liga:"Eredivisie", nivel:87 },
    { nombre:"Fortuna Sittard", escudo:"fortunasittard.png", liga:"Eredivisie", nivel:76 },
    { nombre:"Go Ahead Eagles", escudo:"goaheadeagles.png", liga:"Eredivisie", nivel:83 },
    { nombre:"Heracles Almelo", escudo:"heraclesalmelo.png", liga:"Eredivisie", nivel:73 },
    { nombre:"NAC Breda", escudo:"nacbreda.png", liga:"Eredivisie", nivel:74 },
    { nombre:"NEC Nimega", escudo:"necnijmegen.png", liga:"Eredivisie", nivel:80 },
    { nombre:"PEC Zwolle", escudo:"peczwolle.png", liga:"Eredivisie", nivel:80 },
    { nombre:"PSV Eindhoven", escudo:"psveindhoven.png", liga:"Eredivisie", nivel:90 },
    { nombre:"SC Heerenveen", escudo:"scheerenveen.png", liga:"Eredivisie", nivel:81 },
    { nombre:"SC Telstar", escudo:"sctelstar.png", liga:"Eredivisie", nivel:82 },
    { nombre:"Sparta Rotterdam", escudo:"spartarotterdam.png", liga:"Eredivisie", nivel:82 },
    { nombre:"FC Twente Enschede", escudo:"twenteenschedefc.png", liga:"Eredivisie", nivel:78 },
  ],
  NO: [
    { nombre:"Bryne FK", escudo:"brynefk.png", liga:"Eliteserien", nivel:67 },
    { nombre:"FK Bodø/Glimt", escudo:"fkbodglimt.png", liga:"Eliteserien", nivel:75 },
    { nombre:"FK Haugesund", escudo:"fkhaugesund.png", liga:"Eliteserien", nivel:68 },
    { nombre:"Fredrikstad FK", escudo:"fredrikstadfk.png", liga:"Eliteserien", nivel:71 },
    { nombre:"Hamarkameratene", escudo:"hamarkameratene.png", liga:"Eliteserien", nivel:73 },
    { nombre:"KFUM Kameratene Oslo", escudo:"kfumkamerateneoslo.png", liga:"Eliteserien", nivel:72 },
    { nombre:"Kristiansund BK", escudo:"kristiansundbk.png", liga:"Eliteserien", nivel:69 },
    { nombre:"Molde FK", escudo:"moldefk.png", liga:"Eliteserien", nivel:68 },
    { nombre:"Rosenborg BK", escudo:"rosenborgbk.png", liga:"Eliteserien", nivel:71 },
    { nombre:"Sandefjord Fotball", escudo:"sandefjordfotball.png", liga:"Eliteserien", nivel:67 },
    { nombre:"Sarpsborg 08 FF", escudo:"sarpsborg08ff.png", liga:"Eliteserien", nivel:64 },
    { nombre:"SK Brann", escudo:"skbrann.png", liga:"Eliteserien", nivel:63 },
    { nombre:"Strømsgodset IF", escudo:"strmsgodsetif.png", liga:"Eliteserien", nivel:73 },
    { nombre:"Tromsø IL", escudo:"tromsil.png", liga:"Eliteserien", nivel:71 },
    { nombre:"Vålerenga Fotball", escudo:"valerengafotballelite.png", liga:"Eliteserien", nivel:72 },
    { nombre:"Viking FK", escudo:"vikingfk.png", liga:"Eliteserien", nivel:72 },
  ],
  PL: [
    { nombre:"Arka Gdynia", escudo:"arkagdynia.png", liga:"PKO BP Ekstraklasa", nivel:70 },
    { nombre:"Bruk-Bet Termalica Nieciecza", escudo:"brukbettermalicanieciecza.png", liga:"PKO BP Ekstraklasa", nivel:74 },
    { nombre:"Cracovia", escudo:"cracovia.png", liga:"PKO BP Ekstraklasa", nivel:70 },
    { nombre:"GKS Katowice", escudo:"gkskatowice.png", liga:"PKO BP Ekstraklasa", nivel:64 },
    { nombre:"Górnik Zabrze", escudo:"gornikzabrze.png", liga:"PKO BP Ekstraklasa", nivel:68 },
    { nombre:"Jagiellonia Białystok", escudo:"jagielloniabialystok.png", liga:"PKO BP Ekstraklasa", nivel:66 },
    { nombre:"Korona Kielce", escudo:"koronakielce.png", liga:"PKO BP Ekstraklasa", nivel:63 },
    { nombre:"Lechia Gdańsk", escudo:"lechiagdansk.png", liga:"PKO BP Ekstraklasa", nivel:68 },
    { nombre:"Lech Poznań", escudo:"lechpoznan.png", liga:"PKO BP Ekstraklasa", nivel:79 },
    { nombre:"Legia Varsovia", escudo:"legiawarszawa.png", liga:"PKO BP Ekstraklasa", nivel:78 },
    { nombre:"Motor Lublin", escudo:"motorlublin.png", liga:"PKO BP Ekstraklasa", nivel:71 },
    { nombre:"Piast Gliwice", escudo:"piastgliwice.png", liga:"PKO BP Ekstraklasa", nivel:66 },
    { nombre:"Pogoń Szczecin", escudo:"pogonszczecin.png", liga:"PKO BP Ekstraklasa", nivel:65 },
    { nombre:"Radomiak Radom", escudo:"radomiakradom.png", liga:"PKO BP Ekstraklasa", nivel:68 },
    { nombre:"Raków Częstochowa", escudo:"rakowczestochowa.png", liga:"PKO BP Ekstraklasa", nivel:68 },
    { nombre:"Widzew Łódź", escudo:"widzewlodz.png", liga:"PKO BP Ekstraklasa", nivel:71 },
    { nombre:"Wisła Płock", escudo:"wislaplock.png", liga:"PKO BP Ekstraklasa", nivel:65 },
    { nombre:"Zagłębie Lubin", escudo:"zaglebielubin.png", liga:"PKO BP Ekstraklasa", nivel:62 },
  ],
  PT: [
    { nombre:"AVS Futebol SAD", escudo:"avsfutebol.png", liga:"Liga Portugal", nivel:79 },
    { nombre:"Casa Pia AC", escudo:"casapiaac.png", liga:"Liga Portugal", nivel:80 },
    { nombre:"CD Nacional", escudo:"cdnacional.png", liga:"Liga Portugal", nivel:76 },
    { nombre:"CD Santa Clara", escudo:"cdsantaclara.png", liga:"Liga Portugal", nivel:73 },
    { nombre:"CD Tondela", escudo:"cdtondela.png", liga:"Liga Portugal", nivel:81 },
    { nombre:"CF Estrela da Amadora", escudo:"cfestrelaamadora.png", liga:"Liga Portugal", nivel:80 },
    { nombre:"FC Alverca", escudo:"fcalverca.png", liga:"Liga Portugal", nivel:83 },
    { nombre:"FC Arouca", escudo:"fcarouca.png", liga:"Liga Portugal", nivel:80 },
    { nombre:"FC Famalicão", escudo:"fcfamalicao.png", liga:"Liga Portugal", nivel:77 },
    { nombre:"FC Oporto", escudo:"fcporto.png", liga:"Liga Portugal", nivel:83 },
    { nombre:"GD Estoril Praia", escudo:"gdestorilpraia.png", liga:"Liga Portugal", nivel:77 },
    { nombre:"Gil Vicente FC", escudo:"gilvicentefc.png", liga:"Liga Portugal", nivel:78 },
    { nombre:"Moreirense FC", escudo:"moreirensefc.png", liga:"Liga Portugal", nivel:73 },
    { nombre:"Rio Ave FC", escudo:"rioavefc.png", liga:"Liga Portugal", nivel:79 },
    { nombre:"SC Braga", escudo:"scbraga.png", liga:"Liga Portugal", nivel:78 },
    { nombre:"SL Benfica", escudo:"slbenfica.png", liga:"Liga Portugal", nivel:90 },
    { nombre:"Sporting CP", escudo:"sportingcp.png", liga:"Liga Portugal", nivel:90 },
    { nombre:"Vitória de Guimarães SC", escudo:"vitoriaguimaraessc.png", liga:"Liga Portugal", nivel:81 },
  ],
  RO: [
    { nombre:"FC Argeș Pitești", escudo:"acscfcarges.png", liga:"SuperLiga (Rumania)", nivel:72 },
    { nombre:"AFC Unirea 04 Slobozia", escudo:"afcunirea04slobozia.png", liga:"SuperLiga (Rumania)", nivel:74 },
    { nombre:"AFK Csíkszereda Miercurea Ciuc", escudo:"afkcsikszeredamiercureaciuc.png", liga:"SuperLiga (Rumania)", nivel:67 },
    { nombre:"CFR Cluj", escudo:"cfrcluj.png", liga:"SuperLiga (Rumania)", nivel:68 },
    { nombre:"CS Universitatea Craiova", escudo:"csuniversitateacraiova.png", liga:"SuperLiga (Rumania)", nivel:77 },
    { nombre:"FC Botoșani", escudo:"fcbotosani.png", liga:"SuperLiga (Rumania)", nivel:71 },
    { nombre:"FC Dinamo 1948", escudo:"fcdinamo1948.png", liga:"SuperLiga (Rumania)", nivel:62 },
    { nombre:"FC Hermannstadt", escudo:"fchermannstadt.png", liga:"SuperLiga (Rumania)", nivel:69 },
    { nombre:"FC Metaloglobus București", escudo:"fcmetaloglobusbucharest.png", liga:"SuperLiga (Rumania)", nivel:71 },
    { nombre:"FC Rapid 1923", escudo:"fcrapid1923.png", liga:"SuperLiga (Rumania)", nivel:73 },
    { nombre:"FCSB", escudo:"fcsb.png", liga:"SuperLiga (Rumania)", nivel:74 },
    { nombre:"FC Universitatea Cluj", escudo:"fcuniversitateacluj.png", liga:"SuperLiga (Rumania)", nivel:70 },
    { nombre:"FC Farul Constanța", escudo:"fcvfarulconstanta.png", liga:"SuperLiga (Rumania)", nivel:65 },
    { nombre:"Petrolul Ploiești", escudo:"petrolulploiesti.png", liga:"SuperLiga (Rumania)", nivel:73 },
    { nombre:"SC Oțelul Galați", escudo:"scotelulgalati.png", liga:"SuperLiga (Rumania)", nivel:73 },
    { nombre:"UTA Arad", escudo:"utaarad.png", liga:"SuperLiga (Rumania)", nivel:70 },
  ],
  RU: [
    { nombre:"Akhmat Grozny", escudo:"akhmatgrozny.png", liga:"Premier Liga (Rusia)", nivel:63 },
    { nombre:"Akron Tolyatti", escudo:"akrontogliatti.png", liga:"Premier Liga (Rusia)", nivel:66 },
    { nombre:"Baltika Kaliningrado", escudo:"baltikakaliningrad.png", liga:"Premier Liga (Rusia)", nivel:73 },
    { nombre:"CSKA Moscú", escudo:"cskamoscow.png", liga:"Premier Liga (Rusia)", nivel:78 },
    { nombre:"Dinamo Majachkalá", escudo:"dinamomakhachkala.png", liga:"Premier Liga (Rusia)", nivel:69 },
    { nombre:"Dinamo Moscú", escudo:"dynamomoscow.png", liga:"Premier Liga (Rusia)", nivel:72 },
    { nombre:"FC Krasnodar", escudo:"fckrasnodar.png", liga:"Premier Liga (Rusia)", nivel:66 },
    { nombre:"FC Pari Nizhny Nóvgorod", escudo:"fcparinizhniynovgorod.png", liga:"Premier Liga (Rusia)", nivel:74 },
    { nombre:"FC Rostov", escudo:"fcrostov.png", liga:"Premier Liga (Rusia)", nivel:72 },
    { nombre:"FC Sochi", escudo:"fcsochi.png", liga:"Premier Liga (Rusia)", nivel:70 },
    { nombre:"Krylia Sovetov Samara", escudo:"krylyasovetovsamara.png", liga:"Premier Liga (Rusia)", nivel:64 },
    { nombre:"Lokomotiv Moscú", escudo:"lokomotivmoscow.png", liga:"Premier Liga (Rusia)", nivel:70 },
    { nombre:"Rubin Kazán", escudo:"rubinkazan.png", liga:"Premier Liga (Rusia)", nivel:65 },
    { nombre:"Spartak Moscú", escudo:"spartakmoscow.png", liga:"Premier Liga (Rusia)", nivel:70 },
    { nombre:"Torpedo Moscú", escudo:"torpedomoscow.png", liga:"Premier Liga (Rusia)", nivel:63 },
    { nombre:"Zenit San Petersburgo", escudo:"zenitstpetersburg.png", liga:"Premier Liga (Rusia)", nivel:78 },
  ],
  "GB-SCT": [
    { nombre:"Aberdeen FC", escudo:"aberdeenfc.png", liga:"Scottish Premiership", nivel:68 },
    { nombre:"Celtic FC", escudo:"celticfc.png", liga:"Scottish Premiership", nivel:75 },
    { nombre:"Dundee FC", escudo:"dundeefc.png", liga:"Scottish Premiership", nivel:63 },
    { nombre:"Dundee United FC", escudo:"dundeeunitedfc.png", liga:"Scottish Premiership", nivel:71 },
    { nombre:"Falkirk FC", escudo:"falkirkfc.png", liga:"Scottish Premiership", nivel:68 },
    { nombre:"Heart of Midlothian FC", escudo:"heartofmidlothianfc.png", liga:"Scottish Premiership", nivel:68 },
    { nombre:"Hibernian FC", escudo:"hibernianfc.png", liga:"Scottish Premiership", nivel:67 },
    { nombre:"Kilmarnock FC", escudo:"kilmarnockfc.png", liga:"Scottish Premiership", nivel:69 },
    { nombre:"Livingston FC", escudo:"livingstonfc.png", liga:"Scottish Premiership", nivel:65 },
    { nombre:"Motherwell FC", escudo:"motherwellfc.png", liga:"Scottish Premiership", nivel:72 },
    { nombre:"Rangers FC", escudo:"rangersfc.png", liga:"Scottish Premiership", nivel:79 },
    { nombre:"St Mirren FC", escudo:"stmirrenfc.png", liga:"Scottish Premiership", nivel:65 },
  ],
  RS: [
    { nombre:"FK Čukarički", escudo:"fkcukaricki.png", liga:"Super liga Srbije", nivel:71 },
    { nombre:"FK IMT Belgrado", escudo:"fkimtbelgrad.png", liga:"Super liga Srbije", nivel:67 },
    { nombre:"FK Javor Matis Ivanjica", escudo:"fkjavormatisivanjica.png", liga:"Super liga Srbije", nivel:71 },
    { nombre:"FK Mladost Lučani", escudo:"fkmladostlucani.png", liga:"Super liga Srbije", nivel:63 },
    { nombre:"FK Napredak Kruševac", escudo:"fknapredakkrusevac.png", liga:"Super liga Srbije", nivel:62 },
    { nombre:"FK Novi Pazar", escudo:"fknovipazar.png", liga:"Super liga Srbije", nivel:73 },
    { nombre:"FK Partizán de Belgrado", escudo:"fkpartizanbelgrade.png", liga:"Super liga Srbije", nivel:69 },
    { nombre:"FK Radnički 1923 Kragujevac", escudo:"fkradnicki1923kragujevac.png", liga:"Super liga Srbije", nivel:67 },
    { nombre:"FK Radnički Niš", escudo:"fkradnickinis.png", liga:"Super liga Srbije", nivel:72 },
    { nombre:"FK Radnik Surdulica", escudo:"fkradniksurdulica.png", liga:"Super liga Srbije", nivel:65 },
    { nombre:"FK Spartak Subotica", escudo:"fkspartaksubotica.png", liga:"Super liga Srbije", nivel:71 },
    { nombre:"FK TSC Bačka Topola", escudo:"fktscbackatopola.png", liga:"Super liga Srbije", nivel:65 },
    { nombre:"FK Vojvodina Novi Sad", escudo:"fkvojvodinanovisad.png", liga:"Super liga Srbije", nivel:71 },
    { nombre:"OFK Beograd", escudo:"ofkbeograd.png", liga:"Super liga Srbije", nivel:70 },
    { nombre:"Estrella Roja de Belgrado", escudo:"redstarbelgrade.png", liga:"Super liga Srbije", nivel:70 },
    { nombre:"FK Železničar Pančevo", escudo:"zeleznicarpancevo.png", liga:"Super liga Srbije", nivel:71 },
  ],
  ES: [
    { nombre:"Athletic Club de Bilbao", escudo:"athleticbilbao.png", liga:"LaLiga", nivel:87 },
    { nombre:"Atlético de Madrid", escudo:"atleticodemadrid.png", liga:"LaLiga", nivel:97 },
    { nombre:"CA Osasuna", escudo:"caosasuna.png", liga:"LaLiga", nivel:84 },
    { nombre:"Celta de Vigo", escudo:"celtadevigo.png", liga:"LaLiga", nivel:93 },
    { nombre:"Deportivo Alavés", escudo:"deportivoalaves.png", liga:"LaLiga", nivel:83 },
    { nombre:"Elche CF", escudo:"elchecf.png", liga:"LaLiga", nivel:86 },
    { nombre:"FC Barcelona", escudo:"fcbarcelona.png", liga:"LaLiga", nivel:99 },
    { nombre:"Getafe CF", escudo:"getafecf.png", liga:"LaLiga", nivel:91 },
    { nombre:"Girona FC", escudo:"gironafc.png", liga:"LaLiga", nivel:84 },
    { nombre:"Levante UD", escudo:"levanteud.png", liga:"LaLiga", nivel:87 },
    { nombre:"Rayo Vallecano", escudo:"rayovallecano.png", liga:"LaLiga", nivel:90 },
    { nombre:"RCD Espanyol de Barcelona", escudo:"rcdespanyolbarcelona.png", liga:"LaLiga", nivel:83 },
    { nombre:"RCD Mallorca", escudo:"rcdmallorca.png", liga:"LaLiga", nivel:84 },
    { nombre:"Real Betis Balompié", escudo:"realbetisbalompie.png", liga:"LaLiga", nivel:92 },
    { nombre:"Real Madrid", escudo:"realmadrid.png", liga:"LaLiga", nivel:99 },
    { nombre:"Real Oviedo", escudo:"realoviedo.png", liga:"LaLiga", nivel:90 },
    { nombre:"Real Sociedad", escudo:"realsociedad.png", liga:"LaLiga", nivel:90 },
    { nombre:"Sevilla FC", escudo:"sevillafc.png", liga:"LaLiga", nivel:90 },
    { nombre:"Valencia CF", escudo:"valenciacf.png", liga:"LaLiga", nivel:83 },
    { nombre:"Villarreal CF", escudo:"villarrealcf.png", liga:"LaLiga", nivel:84 },
  ],
  CH: [
    { nombre:"BSC Young Boys", escudo:"bscyoungboys.png", liga:"Super League (Suiza)", nivel:74 },
    { nombre:"FC Basilea 1893", escudo:"fcbasel1893.png", liga:"Super League (Suiza)", nivel:79 },
    { nombre:"FC Lausana-Sport", escudo:"fclausannesport.png", liga:"Super League (Suiza)", nivel:69 },
    { nombre:"FC Lugano", escudo:"fclugano.png", liga:"Super League (Suiza)", nivel:62 },
    { nombre:"FC Lucerna", escudo:"fcluzern.png", liga:"Super League (Suiza)", nivel:62 },
    { nombre:"FC Sion", escudo:"fcsion.png", liga:"Super League (Suiza)", nivel:63 },
    { nombre:"FC St. Gallen 1879", escudo:"fcstgallen1879.png", liga:"Super League (Suiza)", nivel:66 },
    { nombre:"FC Thun", escudo:"fcthun.png", liga:"Super League (Suiza)", nivel:73 },
    { nombre:"FC Winterthur", escudo:"fcwinterthur.png", liga:"Super League (Suiza)", nivel:74 },
    { nombre:"FC Zúrich", escudo:"fczurich.png", liga:"Super League (Suiza)", nivel:62 },
    { nombre:"Grasshopper Club Zúrich", escudo:"grasshopperclubzurich.png", liga:"Super League (Suiza)", nivel:71 },
    { nombre:"Servette FC", escudo:"servettefc.png", liga:"Super League (Suiza)", nivel:68 },
  ],
  TR: [
    { nombre:"Alanyaspor", escudo:"alanyaspor.png", liga:"Süper Lig", nivel:66 },
    { nombre:"Antalyaspor", escudo:"antalyaspor.png", liga:"Süper Lig", nivel:65 },
    { nombre:"Başakşehir FK", escudo:"basaksehirfk.png", liga:"Süper Lig", nivel:73 },
    { nombre:"Beşiktaş JK", escudo:"besiktasjk.png", liga:"Süper Lig", nivel:77 },
    { nombre:"Çaykur Rizespor", escudo:"caykurrizespor.png", liga:"Süper Lig", nivel:68 },
    { nombre:"Eyüpspor", escudo:"eyupspor.png", liga:"Süper Lig", nivel:68 },
    { nombre:"Fatih Karagümrük", escudo:"fatihkaragumruk.png", liga:"Süper Lig", nivel:66 },
    { nombre:"Fenerbahçe", escudo:"fenerbahce.png", liga:"Süper Lig", nivel:75 },
    { nombre:"Galatasaray", escudo:"galatasaray.png", liga:"Süper Lig", nivel:80 },
    { nombre:"Gaziantep FK", escudo:"gaziantepfk.png", liga:"Süper Lig", nivel:70 },
    { nombre:"Gençlerbirliği Ankara", escudo:"genclerbirligiankara.png", liga:"Süper Lig", nivel:63 },
    { nombre:"Göztepe", escudo:"goztepe.png", liga:"Süper Lig", nivel:73 },
    { nombre:"Kasımpaşa", escudo:"kasimpasa.png", liga:"Süper Lig", nivel:65 },
    { nombre:"Kayserispor", escudo:"kayserispor.png", liga:"Süper Lig", nivel:70 },
    { nombre:"Kocaelispor", escudo:"kocaelispor.png", liga:"Süper Lig", nivel:64 },
    { nombre:"Konyaspor", escudo:"konyaspor.png", liga:"Süper Lig", nivel:71 },
    { nombre:"Samsunspor", escudo:"samsunspor.png", liga:"Süper Lig", nivel:64 },
    { nombre:"Trabzonspor", escudo:"trabzonspor.png", liga:"Süper Lig", nivel:74 },
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

/* =====================================================================
   ADN OCULTO — Fase 1 del rediseño del Modo Carrera.
   Generado una sola vez en carreraElegirClub() y guardado en
   jugador.adn. NUNCA se muestra en la UI (ver documento de diseño,
   sección 1): el jugador lo infiere jugando, no lo lee en una barra.
   Todos los valores se sortean independientes entre sí a propósito --
   así dos jugadores con el mismo OVR/posición inicial pueden terminar
   en historias completamente distintas.
   ===================================================================== */
const CARRERA_PERSONALIDADES = ["ambicioso", "leal", "mercenario", "tranquilo", "mediático"];

function carreraGenerarADN(){
  const rnd = (a, b) => Math.round(a + Math.random() * (b - a));
  return {
    profesionalismo: rnd(0, 100),      // amortigua caídas de potencial y acelera subas (ver carreraActualizarPotencialEfectivo)
    regularidad: rnd(0, 100),          // reservado para Fase 3 (varianza de nota temporada a temporada)
    ambicion: rnd(0, 100),             // reservado para Fase 2 (mercado inteligente)
    adaptacion: rnd(0, 100),           // reservado para Fase 2/4 (penalización al cambiar de país/tier)
    resistenciaFisica: rnd(0, 100),    // reservado para Fase 3 (lesiones profundas)
    propensionLesion: rnd(0, 100),     // reservado para Fase 3 (lesiones profundas)
    personalidad: CARRERA_PERSONALIDADES[Math.floor(Math.random() * CARRERA_PERSONALIDADES.length)],
    edadPico: rnd(24, 32),             // reemplaza el rango fijo 30-32 que tenía carrera.js
    velocidadDecadencia: rnd(0, 100),  // reservado para Fase 3 (curva de declive con ADN)
  };
}

// Ajusta el potencial EFECTIVO del jugador después de cada temporada
// (reemplaza el potencial fijo de por vida que existía antes). Sube con
// buen rendimiento sostenido, baja con inactividad o bajo rendimiento --
// nunca por debajo del general actual ni por encima del techo de ADN
// (potencialMax, fijado una sola vez al crear el jugador). El
// profesionalismo amortigua las bajas y acelera las subas.
function carreraActualizarPotencialEfectivo(j, t){
  let delta = 0;
  if (t.valoracion >= 7.0) delta += 1;
  if (t.partidos >= 36) delta += 1; // continuidad real dentro del bienio, no solo buena nota
  if (t.resultadoClub === "Campeón") delta += 0.5;
  if (t.partidos < 10) delta -= 1.5;
  if (t.valoracion < 5.5) delta -= 1;
  if (t.lesion && t.lesion.tipo === "grave") delta -= 2;
  delta *= (0.5 + j.adn.profesionalismo / 100);
  j.potencialEfectivo = Math.max(j.atributos.general, Math.min(j.adn.potencialMax, j.potencialEfectivo + delta));
}

// Reputación: variable separada del OVR que representa cómo ve al
// jugador el mundo del fútbol. Tiene inercia (el *0.6 final) para que
// no salte de golpe temporada a temporada. `premios` es la lista de
// premios individuales ganados esa temporada -- vacía hasta Fase 5,
// dejado como parámetro ahora para no tener que tocar esta función de
// nuevo cuando se implementen los premios.
function carreraActualizarReputacion(j, t, premios){
  let delta = 0;
  delta += (t.valoracion - 6.0) * 3;
  delta += Math.min(6, t.goles * 0.15 + t.asistencias * 0.1);
  if (t.resultadoClub === "Campeón") delta += 6;
  if (t.convocatoria) delta += 3;
  if (t.cambioDivision === "descenso") delta -= 8;
  if (t.lesion && t.lesion.tipo === "grave") delta -= 5;
  delta += (premios ? premios.length : 0) * 10;
  j.reputacion = Math.max(0, Math.min(100, j.reputacion + delta * 0.6));
}

/* =====================================================================
   PIRÁMIDE EXTENDIDA A EUROPA — Fase 4/6.1: tier 0-5 por liga, para poder
   calcular premios "por tier" (Fase 5, §9) sin depender del nivel
   numérico del club -- los rangos de nivel de tiers vecinos se solapan
   (ver tabla §6.1 del documento de diseño), así que nivel solo no
   alcanza para clasificar de forma confiable. El tier 2 agrupa todas las
   primeras divisiones sudamericanas fuera de la pirámide argentina
   (Brasil, Bolivia, Chile, Colombia, Ecuador, Perú, Paraguay, Uruguay,
   Venezuela): son el mismo escalón competitivo aunque no tengan el
   ascenso/descenso modelado de AR. Cualquier liga que no esté en esta
   tabla (por si se suma un país nuevo más adelante) cae a tier 2 por
   default, no a un tier inventado.
   ===================================================================== */
const CARRERA_TIER_LIGA = {
  "Primera C": 0, "B Metropolitana": 0,
  "Primera Nacional": 1,
  "Liga Profesional": 2, "Brasileirão": 2, "Liga boliviana": 2, "Liga chilena": 2,
  "Liga colombiana": 2, "Liga ecuatoriana": 2, "Liga peruana": 2, "Liga paraguaya": 2,
  "Liga uruguaya": 2, "Liga venezolana": 2,
  // Tier 3 — Europa menor (15 ligas)
  "Bundesliga (Austria)": 3, "Jupiler Pro League": 3, "efbet Liga": 3,
  "Super League (Suiza)": 3, "Chance Liga": 3, "Superliga (Dinamarca)": 3,
  "Scottish Premiership": 3, "Super League 1": 3, "SuperSport HNL": 3,
  "Eliteserien": 3, "PKO BP Ekstraklasa": 3, "SuperLiga (Rumania)": 3,
  "Premier Liga (Rusia)": 3, "Super liga Srbije": 3, "Süper Lig": 3,
  // Tier 4 — Europa media
  "Eredivisie": 4, "Liga Portugal": 4, "Ligue 1": 4,
  // Tier 5 — Europa alta / gigantes
  "Premier League": 5, "Bundesliga (Alemania)": 5, "Serie A": 5, "LaLiga": 5,
};

function carreraObtenerTier(liga){
  return CARRERA_TIER_LIGA[liga] ?? 2;
}

/* =====================================================================
   PREMIOS INDIVIDUALES — Fase 5 (§9). Se calculan al cierre de cada
   temporada, POR TIER (decisión confirmada por el usuario: simulado
   contra un umbral estadístico calibrado por tier/posición, no contra
   rivales reales generados uno por uno -- mismo resultado narrativo,
   muchísimo más barato de calcular). El jugador "compite" contra un
   campo implícito: necesita estar en la cola superior de su tier
   (top ~2-3%), y eso se simula con una probabilidad calibrada en vez de
   armar un ranking real con más jugadores.
   `baseline` es la misma producción "esperada" por posición que ya usa
   la nota de temporada (CARRERA_BASELINE_PRODUCCION), así el criterio de
   "por encima de lo esperado para el rol" es consistente entre la nota y
   los premios en vez de ser dos escalas distintas.
   ===================================================================== */
const CARRERA_TIER_DUREZA = { 0: 0.6, 1: 0.7, 2: 0.85, 3: 0.92, 4: 0.97, 5: 1.05 };

function carreraCalcularPremios(j, t, tier, grupoPosicion, baseline){
  const premios = [];
  if (t.partidos < 20) return premios; // temporada corta: sin volumen para competir por un premio individual

  const dureza = CARRERA_TIER_DUREZA[tier] ?? 0.85;
  const produccionPorPartido = (t.goles + t.asistencias * 0.6) / t.partidos;
  const bonoTitulo = t.resultadoClub === "Campeón" ? 1.2 : t.resultadoClub === "Clasificó a copas internacionales" ? 0.4 : 0;
  // Puntaje "elite" comparable entre posiciones: nota por encima de lo
  // esperado para el rol + aporte ofensivo por encima del baseline +
  // título, todo escalado por la dureza del tier (más difícil destacar
  // cuanto más alto el nivel de competencia).
  const puntajeElite = ((t.valoracion - 6.0) + (produccionPorPartido - baseline) * 3 + bonoTitulo) / dureza;

  // Balón de Oro: el más exigente -- nota alta sostenida Y muy por
  // encima del baseline. Probabilidad baja incluso cumpliendo el piso,
  // para que no se gane automáticamente cada vez que se califica.
  if (t.valoracion >= 8.2 && puntajeElite >= 1.6) {
    const prob = Math.min(0.22, (puntajeElite - 1.6) * 0.12 + 0.03);
    if (Math.random() < prob) premios.push({ tipo: "balon_de_oro", nombre: "Balón de Oro" });
  }

  // Botín de Oro: piso de goles ajustado por grupo de posición (un
  // defensor/arquero no compite en las mismas condiciones que un
  // delantero, pero puede ganarlo si de verdad tuvo una temporada
  // anómala) y por la dureza del tier.
  const pisoGoles = { delantero: 34, medio: 20, defensor: 11, arquero: 3 }[grupoPosicion] * dureza;
  if (t.goles >= pisoGoles) {
    const prob = Math.min(0.35, (t.goles - pisoGoles) * 0.02 + 0.06);
    if (Math.random() < prob) premios.push({ tipo: "botin_de_oro", nombre: "Botín de Oro" });
  }

  // Mejor Jugador Joven: mismo criterio que el Balón de Oro pero con
  // piso más bajo, y solo para 23 años o menos.
  if (j.edad <= 23 && puntajeElite >= 1.0) {
    const prob = Math.min(0.3, (puntajeElite - 1.0) * 0.15 + 0.05);
    if (Math.random() < prob) premios.push({ tipo: "joven_promesa", nombre: "Mejor Jugador Joven" });
  }

  // Equipo Ideal del tier: el más alcanzable de los cuatro (hay 11
  // lugares por tier, no 1 solo), piso más bajo.
  if (puntajeElite >= 0.7) {
    const prob = Math.min(0.4, (puntajeElite - 0.7) * 0.18 + 0.08);
    if (Math.random() < prob) premios.push({ tipo: "equipo_ideal", nombre: "Equipo Ideal" });
  }

  return premios;
}

// Ícono para mostrar como badge chico en la fila de trayectoria cuando esa
// temporada incluyó un premio individual (ver carreraTablaEdadesHTML).
const CARRERA_PREMIO_ICONO = {
  balon_de_oro: "🥇", botin_de_oro: "👟", joven_promesa: "🌟", equipo_ideal: "🛡️",
};

// Info de cada tipo de hito para el timeline del dashboard (§10): ícono +
// texto (sin la edad, que se agrega al renderizar cada fila del timeline
// en carreraMostrarDashboard). "seleccion" es el tipo original (ya
// existía antes de Fase 5, se mantiene para no romper carreras guardadas
// con ese tipo) y se renderiza con la bandera del país en vez de un
// emoji fijo -- ver el caso especial en el render.
const CARRERA_HITO_INFO = {
  debut_profesional:   { icono: "🎽", texto: (h) => `Debut profesional en ${h.club}` },
  primer_gol:          { icono: "⚽", texto: (h) => `Primer gol en ${h.club}` },
  primer_titulo:       { icono: "🏆", texto: (h) => `Primer título con ${h.club}` },
  ascenso:             { icono: "▲", texto: (h) => `Ascenso de división con ${h.club}` },
  descenso:            { icono: "▼", texto: (h) => `Descenso de división con ${h.club}` },
  debut_continental:   { icono: "🌍", texto: (h) => `Debut en copas internacionales con ${h.club}` },
  primer_club_europeo: { icono: "✈️", texto: (h) => `Salto a Europa: ${h.club}` },
  balon_de_oro:        { icono: "🥇", texto: (h) => `Primer Balón de Oro, con ${h.club}` },
  capitan:             { icono: "🎖️", texto: (h) => `Cinta de capitán en ${h.club}` },
  lesion_grave:        { icono: "🩹", texto: (h) => `Lesión grave en ${h.club}` },
  retorno_club_origen: { icono: "🔁", texto: (h) => `Vuelve a ${h.club}` },
  vuelta_pais_origen:  { icono: "🏡", texto: (h) => `Vuelta a casa: ${h.club} (${h.pais})` },
  retiro:              { icono: "🏁", texto: () => `Fin de la carrera` },
};

// Devuelve un array de `cantidad` clubes (sin repetir) para las ofertas
// de cantera, según el país del jugador. Si el país no tiene pool
// propio, cae al pool de Argentina (el simulador solo cubre ligas
// argentinas + Sudamérica, así que un origen sin liga local arranca
// probándose en el ascenso argentino).
function carreraObtenerOfertas(iso2, cantidad){
  const n = cantidad || 3;
  let pool = CARRERA_CLUBES[iso2] || CARRERA_CLUBES.AR;
  // BUG que reportó Pablo: CARRERA_CLUBES.AR tiene las 4 divisiones
  // argentinas juntas en el mismo array (cantera + Nacional + Liga
  // Profesional), porque ahí también se abastece el resto de la carrera
  // (carreraObtenerOfertasPrestamo). Pero la oferta INICIAL de cantera a
  // los 16 años tiene que salir solo de las divisiones de ascenso más
  // bajas -- sin este filtro, un juvenil podía arrancar de entrada en
  // River Plate o Boca, saltándose toda la pirámide.
  if (iso2 === "AR") {
    pool = pool.filter(c => c.liga === "Primera C" || c.liga === "B Metropolitana");
  }
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

// Clase CSS por resultado del club en la temporada, para colorear cada
// fila de la trayectoria (campeón en dorado, descenso en rojo, etc.) en
// vez de dejar todas las filas del mismo gris sin distinción visual.
function carreraClaseResultado(resultado){
  if (resultado === "Campeón") return "resultado-campeon";
  if (resultado === "Clasificó a copas internacionales") return "resultado-copas";
  if (resultado === "Peleó el descenso") return "resultado-pelea";
  if (resultado === "Descendió") return "resultado-descenso";
  return "resultado-neutro";
}

// Logo del torneo por liga, para mostrar junto al escudo del club en la
// trayectoria. Solo cubre las ligas para las que el simulador ya tiene un
// logo en public/logos-torneos -- las que no están (la mayoría de las
// ligas sudamericanas fuera de Argentina/Brasil/Colombia/Ecuador) se
// omiten en vez de mostrar un ícono roto.
const CARRERA_LOGO_LIGA = {
  "Primera C": "primera-c.png",
  "B Metropolitana": "b-metropolitana.png",
  "Primera Nacional": "primera-nacional.png",
  "Liga Profesional": "liga-profesional.png",
  "Brasileirão": "brasileirao.png",
  "Liga colombiana": "LigaBetPlay.png",
  "Liga ecuatoriana": "ligapro.png",
};

function carreraLogoLigaHTML(liga){
  const archivo = CARRERA_LOGO_LIGA[liga];
  if (!archivo) return "";
  return `<img class="carrera-logo-liga" src="logos-torneos/${archivo}" alt="" loading="lazy" onerror="this.remove()">`;
}

// Clase CSS por nota de la temporada (escala 1-10, como el rating de
// partido de Sofascore): verde para buena temporada, rojo para mala.
function carreraClaseNota(nota){
  if (nota >= 7.5) return "nota-elite";
  if (nota >= 6.8) return "nota-alta";
  if (nota >= 6.0) return "nota-media";
  if (nota >= 5.0) return "nota-baja";
  return "nota-mala";
}

// Color principal por club, para pintar la fila de la trayectoria con la
// identidad del club en vez de un color genérico. Son aproximaciones (un
// solo color dominante, no la paleta completa) para los clubes más
// conocidos de la Liga Profesional y algunos tradicionales de ascenso;
// el resto (incluida toda Sudamérica fuera de Argentina) cae al color
// estable por hash de carreraColorClub(), así igual quedan diferenciados
// entre sí y siempre el mismo color para el mismo club, aunque no sea
// necesariamente su color real -- si tenés los colores exactos de algún
// club que uses seguido, pasámelos y los sumo acá.
const CARRERA_COLOR_CLUB = {
  "River Plate": "#D91A2A", "Boca Juniors": "#0F4C92", "Racing Club": "#77C7E8",
  "Talleres de Córdoba": "#0A4595", "Vélez Sarsfield": "#1E5AA8",
  "Estudiantes de La Plata": "#C8102E", "Independiente": "#D91C24",
  "San Lorenzo": "#0C2340", "Rosario Central": "#1B3B6F", "Argentinos Juniors": "#E2001A",
  "Huracán": "#E30613", "Defensa y Justicia": "#6E2585", "Newell's Old Boys": "#B5121B",
  "Lanús": "#6F1D2B", "Unión de Santa Fe": "#D2232A", "Gimnasia La Plata": "#002D62",
  "Belgrano": "#1B1F3B", "Central Córdoba (SdE)": "#10245C", "Atlético Tucumán": "#6EC6E8",
  "Instituto": "#C8102E", "Tigre": "#0033A0", "Platense": "#2B2B2B",
  "Banfield": "#2E7D32", "Barracas Central": "#7A1F2B", "Sarmiento (Junín)": "#1B7B3A",
  "Independiente Rivadavia": "#1C3F94", "Deportivo Riestra": "#F26522",
  "Chacarita": "#1a1a1a", "Atlanta": "#1B3B6F", "Quilmes": "#6EC6E8",
  "Colón": "#B5121B", "Godoy Cruz": "#0A4595", "Patronato": "#B5121B",
  "All Boys": "#1a1a1a", "Temperley": "#6EC6E8", "Almagro": "#B5121B",
  "Chicago": "#1a1a1a", "Los Andes": "#E2001A",
};

// Color estable por nombre de club (hash simple -> tono HSL), para todo
// club que no tiene una entrada curada arriba.
function carreraColorClub(nombreClub){
  if (CARRERA_COLOR_CLUB[nombreClub]) return CARRERA_COLOR_CLUB[nombreClub];
  let hash = 0;
  for (let i = 0; i < nombreClub.length; i++) hash = nombreClub.charCodeAt(i) + ((hash << 5) - hash);
  const hue = Math.abs(hash) % 360;
  return `hsl(${hue}, 50%, 52%)`;
}

// Clase CSS por rango de OVR, para el color del badge grande de la ficha.
function carreraClaseOVR(ovr){
  if (ovr >= 80) return "ovr-elite";
  if (ovr >= 70) return "ovr-alto";
  if (ovr >= 60) return "ovr-medio";
  if (ovr >= 45) return "ovr-bajo";
  return "ovr-juvenil";
}

// Pool completo de clubes (todas las nacionalidades) aplanado, con su iso2
// de origen. Se usa para armar ofertas de préstamo/transferencia a mitad de
// carrera, sin importar el país original del jugador. Dedupea por
// nombre+país (no solo por nombre) porque hay nombres repetidos entre
// países -- "Universidad Católica" (Chile/Ecuador), "Nacional"
// (Paraguay/Uruguay) -- y dedupear solo por nombre hacía desaparecer para
// siempre a uno de los dos clubes de la lista de ofertas.
function carreraTodosClubes(){
  const vistos = new Set();
  const out = [];
  Object.entries(CARRERA_CLUBES).forEach(([iso2, lista]) => {
    lista.forEach(c => {
      const clave = c.nombre + "|" + iso2;
      if (!vistos.has(clave)) { vistos.add(clave); out.push({ ...c, iso2 }); }
    });
  });
  return out;
}

// A partir de qué nivel general empieza a "verlo" el scouting del exterior.
// Por debajo de esto, las ofertas de préstamo/transferencia se limitan a
// clubes argentinos (así la carrera realmente escala Primera C/B Metro ->
// Primera Nacional -> Liga Profesional en vez de saltar directo afuera).
const CARRERA_UMBRAL_OFERTA_EXTERIOR = 58; // se mantiene como referencia/fallback, ya no se usa como corte binario

// Fase 4 (§6.2): reemplaza el corte binario de arriba por una función de
// probabilidad continua sobre reputación. Con esto "tarde o temprano
// aparece alguna oportunidad europea" -- ni 100% determinístico (todos los
// que superan el número entran, todos los que no jamás) ni 100% azar puro
// (reputación sigue siendo lo que más pesa). Logística centrada en
// reputación 50, con piso 4% y techo 96% para que nunca sea imposible ni
// garantizado.
function carreraProbabilidadScoutingExterior(reputacion){
  const rep = reputacion || 0;
  const x = (rep - 50) / 14;
  const logistic = 1 / (1 + Math.exp(-x));
  return Math.max(0.04, Math.min(0.96, logistic));
}

// Complemento de la de arriba, para cuando el jugador YA está en Europa:
// llegar por primera vez tiene que costar (curva de arriba), pero quedarse
// adentro no puede exigir lo mismo -- si no, un juvenil de 16 años con
// reputación inicial baja (todavía no tuvo chance de demostrar nada) cae
// casi siempre de vuelta a Sudamérica en cada ventana de mercado, que es
// justo el bug que reportó el usuario. Curva centrada mucho más abajo (25
// en vez de 50, con pendiente más floja) y techo bajo (55% en vez de 96%
// como probabilidad de CAÍDA), así hace falta reputación genuinamente mala
// y sostenida para que el pool sudamericano vuelva a aparecer.
function carreraProbabilidadCaidaSudamerica(reputacion){
  const rep = reputacion || 0;
  const x = (rep - 25) / 12;
  const logistic = 1 / (1 + Math.exp(-x));
  return Math.max(0.04, Math.min(0.55, 1 - logistic));
}

// Para un jugador de origen EUROPEO que ya está instalado en Europa: acá
// Europa no es un salto que en algún momento se revierte, es SU
// continente. La caída a Sudamérica tiene que ser una rareza, no una
// posibilidad real en cada ventana de mercado -- techo bajísimo (8% en
// vez de 55%) y piso también más bajo, así casi nunca aparece salvo con
// reputación realmente por el piso y sostenida en el tiempo.
function carreraProbabilidadCaidaSudamericaOrigenEuropeo(reputacion){
  const rep = reputacion || 0;
  const x = (rep - 15) / 10;
  const logistic = 1 / (1 + Math.exp(-x));
  return Math.max(0.01, Math.min(0.08, 1 - logistic));
}

// Umbral de "nivel" a partir del cual un club brasileño cuenta como
// gigante (Flamengo, Palmeiras, Corinthians, São Paulo, etc.) -- son la
// única excepción real para que un europeo de origen europeo termine en
// Sudamérica: nadie con carrera hecha en Europa se va a probar a un
// equipo chico de Primera C, pero SÍ puede tentarlo un grande de Brasil
// sobre el cierre de carrera (algo que pasa de verdad en el fútbol real).
const CARRERA_NIVEL_GIGANTE_BRASIL = 69;

/* =====================================================================
   MERCADO DE PASES INTELIGENTE — Fase 2 del rediseño.
   Reemplaza el matching plano por distancia de nivel por un score
   compuesto: nivel/OVR domina (confirmado), pero reputación, necesidad
   de posición del club, franja de edad objetivo y política de fichajes
   también entran en juego -- no cualquier club fichar a cualquier
   jugador solo porque el número de nivel da parecido.

   Los clubes de CARRERA_CLUBES no tienen (todavía) prestigio/presupuesto/
   política/edadObjetivo cargados a mano -- estos helpers devuelven un
   default razonable derivado de `nivel` cuando el campo no existe, así
   el sistema funciona ya mismo con los ~900 clubes actuales y se puede
   ir curando club por club sin romper nada.
   ===================================================================== */
function carreraClubPrestigio(club){ return club.prestigio ?? club.nivel; }
function carreraClubPolitica(club){ return club.politica ?? "oportunista"; }
function carreraClubEdadObjetivo(club){ return club.edadObjetivo ?? [18, 32]; }

function carreraGrupoDePosicion(pos){
  if (CARRERA_GRUPOS_POSICION.delantero.includes(pos)) return "delantero";
  if (CARRERA_GRUPOS_POSICION.medio.includes(pos)) return "medio";
  if (CARRERA_GRUPOS_POSICION.defensor.includes(pos)) return "defensor";
  return "arquero";
}

// Necesidad de plantilla simplificada (ver documento de diseño, 5.3): en
// vez de simular una plantilla completa por club, cada club tiene 1-2
// "puestos calientes" por temporada, determinados por un hash simple de
// club+temporada -- así es estable dentro de la misma temporada (todas
// las ofertas de ese período son consistentes) pero cambia de una
// temporada a otra sin guardar estado extra en ningún lado.
function carreraClubNecesitaPosicion(club, grupoPosicion, temporadaActual){
  if (club.posicionesNecesarias) return club.posicionesNecesarias.includes(grupoPosicion);
  const grupos = ["delantero", "medio", "defensor", "arquero"];
  const str = club.nombre + "|" + temporadaActual;
  let seed = 0;
  for (let i = 0; i < str.length; i++) seed = (seed * 31 + str.charCodeAt(i)) >>> 0;
  const cantidadCalientes = 1 + (seed % 2); // 1 o 2 puestos calientes esta temporada
  const arr = grupos.slice();
  let s = seed || 1;
  for (let i = arr.length - 1; i > 0; i--) {
    s = (s * 1103515245 + 12345) >>> 0;
    const j = s % (i + 1);
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr.slice(0, cantidadCalientes).includes(grupoPosicion);
}

// Score de compatibilidad club-jugador. Nivel domina (peso 0.55, tal como
// se definió para este mercado); el resto de los factores desempatan y
// evitan que "cualquier club de nivel parecido" sirva por igual.
function carreraScoreClub(club, jugador, nivelBusqueda, temporadaActual){
  // Mismo castigo asimétrico que antes: bajar de nivel pesa más que subir,
  // para que la progresión se sienta ascendente por default.
  const diff = club.nivel - nivelBusqueda;
  const distanciaNivel = diff >= 0 ? diff * 0.75 : Math.abs(diff) * 1.3;
  const scoreNivel = 100 - Math.min(100, distanciaNivel);

  const prestigio = carreraClubPrestigio(club);
  const scoreReputacion = 100 - Math.min(100, Math.abs(prestigio - jugador.reputacion));

  const grupoPos = carreraGrupoDePosicion(jugador.posicion);
  const scorePosicion = carreraClubNecesitaPosicion(club, grupoPos, temporadaActual) ? 100 : 55;

  const [edadMin, edadMax] = carreraClubEdadObjetivo(club);
  let scoreEdad = 100;
  if (jugador.edad < edadMin) scoreEdad = 100 - (edadMin - jugador.edad) * 6;
  else if (jugador.edad > edadMax) scoreEdad = 100 - (jugador.edad - edadMax) * 6;
  scoreEdad = Math.max(0, scoreEdad);

  // Política de fichajes del club: modula según edad/reputación del
  // jugador, y un club "oportunista" además pondera la ambición baja del
  // jugador (ADN) porque son fichajes más fáciles de cerrar.
  const politica = carreraClubPolitica(club);
  let scorePolitica = 60;
  if (politica === "cantera") scorePolitica = jugador.edad <= 23 ? 90 : 40;
  else if (politica === "estrellas") scorePolitica = jugador.reputacion >= 55 ? 90 : 30;
  else if (politica === "veteranos") scorePolitica = jugador.edad >= 28 ? 85 : 45;
  if (politica === "oportunista" && jugador.adn) scorePolitica += (100 - jugador.adn.ambicion) * 0.15;

  const ruido = Math.random() * 12; // variedad, no determinismo puro

  return scoreNivel * 0.55 + scoreReputacion * 0.15 + scorePosicion * 0.15
       + scoreEdad * 0.10 + scorePolitica * 0.05 + ruido;
}

// Ofertas de préstamo/transferencia a mitad de carrera: ahora ordenadas
// por el score compuesto de carreraScoreClub en vez de solo distancia de
// nivel, excluyendo el club en el que ya está y acotando el pool "local"
// al CONTINENTE del club actual del jugador (Sudamérica o Europa) en vez
// de a Argentina a secas -- así un jugador que arrancó o llegó a Europa
// recibe ofertas europeas, y uno en Sudamérica recibe ofertas
// sudamericanas, sin importar su nacionalidad de origen.
function carreraObtenerOfertasPrestamo(jugador, temporadaActual, nombreClubActual, nivelBusqueda, cantidad, excluirRecientes){
  const n = cantidad || 2;
  const excluir = new Set([nombreClubActual, ...(excluirRecientes || [])]);
  let candidatos = carreraTodosClubes().filter(c => !excluir.has(c.nombre));
  const continenteActual = carreraContinente(jugador.club && jugador.club.iso2) || "sudamerica";
  const continenteOrigen = carreraContinente(jugador.pais && jugador.pais.iso2);
  let poolContinente;
  let soloGigantesBrasil = false;
  if (continenteActual === "europa") {
    // Un europeo de origen resiste MUCHO más la caída que un sudamericano
    // que llegó a Europa como salto de carrera (ver comentario en
    // carreraProbabilidadCaidaSudamericaOrigenEuropeo).
    const esOrigenEuropeo = continenteOrigen === "europa";
    const probCaida = esOrigenEuropeo
      ? carreraProbabilidadCaidaSudamericaOrigenEuropeo(jugador.reputacion)
      : carreraProbabilidadCaidaSudamerica(jugador.reputacion);
    const cae = Math.random() < probCaida;
    poolContinente = cae ? "sudamerica" : "europa";
    // Si cae y es de origen europeo, la única puerta a Sudamérica son los
    // gigantes brasileños -- no cualquier club sudamericano.
    soloGigantesBrasil = cae && esOrigenEuropeo;
  } else {
    // Sudamérica (o continente desconocido, con Sudamérica como base): la
    // reputación decide si esta ventana trae el salto a Europa o si el
    // jugador sigue viendo ofertas locales.
    const probExterior = carreraProbabilidadScoutingExterior(jugador.reputacion);
    poolContinente = Math.random() < probExterior ? "europa" : "sudamerica";
  }
  candidatos = candidatos.filter(c => carreraContinente(c.iso2) === poolContinente);
  if (soloGigantesBrasil) {
    const soloGigantes = candidatos.filter(c => c.iso2 === "BR" && c.nivel >= CARRERA_NIVEL_GIGANTE_BRASIL);
    // Si por exclusiones (club actual/recientes) no queda ningún gigante
    // disponible esta ventana, mejor mantenerlo en Europa que ofrecerle
    // un club sudamericano cualquiera -- la excepción es SOLO el gigante.
    candidatos = soloGigantes.length ? soloGigantes
      : carreraTodosClubes().filter(c => !excluir.has(c.nombre) && carreraContinente(c.iso2) === "europa");
  }
  candidatos.forEach(c => { c._score = carreraScoreClub(c, jugador, nivelBusqueda, temporadaActual); });
  candidatos.sort((a, b) => b._score - a._score);
  const acotado = candidatos.slice(0, Math.min(n * 4, candidatos.length));
  for (let i = acotado.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [acotado[i], acotado[j]] = [acotado[j], acotado[i]];
  }
  return acotado.slice(0, n);
}

// Etiqueta de "salto de nivel" para mostrar en la tarjeta de oferta: le
// da al jugador una lectura rápida de si la oferta es una mejora, un
// paso lateral o un paso atrás respecto de SU CLUB ACTUAL (nivel de
// club contra nivel de club, no nivel de club contra OVR del jugador --
// así compara peras con peras: si tu club actual es de nivel 40 y te
// ofrecen uno de 45, es "similar" aunque tu OVR personal sea 70).
//
// OJO con esto: antes había un único corte en ±8, así que TODO lo que
// quedaba más de 8 puntos abajo cayía en la misma etiqueta "Nivel más
// bajo" -- un club apenas por debajo (ej. -11) y un club de dos
// divisiones menos (ej. -30) se veían idénticos en la tarjeta, aunque
// nivel numérico fuera bien distinto. Con 5 franjas en vez de 3 la
// etiqueta ahora refleja el tamaño real de la brecha.
function carreraClaseSalto(nivelClub, nivelClubActual){
  const diff = nivelClub - nivelClubActual;
  if (diff >= 18) return { texto: "↑↑ Salto enorme", clase: "salto-arriba-fuerte" };
  if (diff >= 6) return { texto: "↑ Salto de nivel", clase: "salto-arriba" };
  if (diff > -6) return { texto: "= Nivel similar", clase: "salto-igual" };
  if (diff > -18) return { texto: "↓ Nivel más bajo", clase: "salto-abajo" };
  return { texto: "↓↓ Categoría inferior", clase: "salto-abajo-fuerte" };
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
