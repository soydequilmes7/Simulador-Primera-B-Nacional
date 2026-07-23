# -*- coding: utf-8 -*-
"""manager_mode/eventos.py

Catálogo de eventos del Modo DT. Cada evento tiene 2-3 opciones; cada
opción modifica variables internas del club (moral, confianza de la
dirigencia, relación con la hinchada, relación con el vestuario,
presupuesto, reputación del DT) y dispara una reacción narrativa vía
NarrativaService -- el usuario nunca ve el número, solo la crónica.
Fase 1 del plan (docs/PLAN_MODO_DT.md).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from manager_mode.narrativa import Intensidad, TipoReaccion


class CategoriaEvento(str, Enum):
    VIAJES = "viajes"
    VESTUARIO = "vestuario"
    MERCADO = "mercado"
    DIRIGENCIA = "dirigencia"
    PRENSA = "prensa"
    LESIONES = "lesiones"
    JUVENILES = "juveniles"
    SPONSORS = "sponsors"
    INFRAESTRUCTURA = "infraestructura"
    CLASICOS = "clasicos"
    CRISIS = "crisis"
    SELECCIONES = "selecciones"
    COPAS = "copas"
    LIBERTADORES = "libertadores"
    SUDAMERICANA = "sudamericana"
    RUMORES = "rumores"
    ARBITROS_HINCHADA = "arbitros_hinchada"
    VIDA_PLANTEL = "vida_plantel"


# Claves de variable válidas en EstadoClub. Mantener en sync con los
# atributos del dataclass de abajo.
VARIABLES_VALIDAS = frozenset(
    {"moral", "confianza", "hinchada", "vestuario", "presupuesto", "reputacion"}
)


@dataclass(frozen=True)
class Efecto:
    """Un modificador de una opción sobre una variable interna."""

    variable: str
    delta: float

    def __post_init__(self) -> None:
        if self.variable not in VARIABLES_VALIDAS:
            raise ValueError(f"variable desconocida: {self.variable!r}")


@dataclass(frozen=True)
class OpcionEvento:
    """Una de las 2-3 opciones que el usuario puede elegir ante un
    evento.

    Atributos:
      codigo: identificador único dentro del evento (ej. "hablar").
      texto: label corto mostrado en el botón (ej. "Hablar con él").
      efectos: modificadores sobre variables internas del club.
      tipo_reaccion: qué actor reacciona narrativamente, o None si la
        opción no dispara una reacción pública (ej. una decisión
        puramente interna del vestuario).
      intensidad: tono de la reacción narrativa a elegir.
    """

    codigo: str
    texto: str
    efectos: tuple[Efecto, ...]
    intensidad: Intensidad
    tipo_reaccion: TipoReaccion | None = None


@dataclass(frozen=True)
class Evento:
    """Un evento del catálogo, con 2-3 opciones."""

    codigo: str
    categoria: CategoriaEvento
    titulo: str
    descripcion: str
    opciones: tuple[OpcionEvento, ...]

    def opcion(self, codigo: str) -> OpcionEvento:
        for opcion in self.opciones:
            if opcion.codigo == codigo:
                return opcion
        raise KeyError(f"la opcion {codigo!r} no existe en el evento {self.codigo!r}")


@dataclass
class EstadoClub:
    """Variables internas del club dirigido, todas en escala 0-100
    salvo `presupuesto` (moneda libre del simulador). Los efectos de
    los eventos se clampean a este rango para que no se puedan romper
    ni desbordar por acumulación."""

    moral: float = 50.0
    confianza: float = 50.0
    hinchada: float = 50.0
    vestuario: float = 50.0
    presupuesto: float = 0.0
    reputacion: float = 50.0

    def aplicar(self, efectos: tuple[Efecto, ...]) -> None:
        for efecto in efectos:
            valor_actual = getattr(self, efecto.variable)
            nuevo_valor = valor_actual + efecto.delta
            if efecto.variable != "presupuesto":
                nuevo_valor = max(0.0, min(100.0, nuevo_valor))
            setattr(self, efecto.variable, nuevo_valor)


def _ev(codigo: str, categoria: CategoriaEvento, titulo: str, descripcion: str,
        opciones: tuple[OpcionEvento, ...]) -> Evento:
    return Evento(codigo=codigo, categoria=categoria, titulo=titulo,
                   descripcion=descripcion, opciones=opciones)


def _op(codigo: str, texto: str, intensidad: Intensidad,
        efectos: tuple[Efecto, ...], tipo_reaccion: TipoReaccion | None = None) -> OpcionEvento:
    return OpcionEvento(codigo=codigo, texto=texto, intensidad=intensidad,
                         efectos=efectos, tipo_reaccion=tipo_reaccion)


_EVENTOS: list[Evento] = [
    # ---------------------------------------------------------------- VIAJES
    _ev("el_micro", CategoriaEvento.VIAJES, "El Micro",
        "14 horas de viaje hasta la próxima cancha. El cuerpo técnico debate cómo llegar.",
        (
            _op("rotar", "Rotar el plantel", Intensidad.NEUTRA,
                (Efecto("vestuario", 3), Efecto("moral", -2))),
            _op("titulares", "Viajar con los titulares", Intensidad.NEGATIVA,
                (Efecto("moral", -4),), TipoReaccion.VESTUARIO),
            _op("hotel_extra", "Pagar una noche extra de hotel", Intensidad.POSITIVA,
                (Efecto("moral", 4), Efecto("presupuesto", -500))),
        )),
    _ev("vuelo_cancelado", CategoriaEvento.VIAJES, "Vuelo Cancelado",
        "El vuelo se cancela y el plantel llega sobre la hora al estadio rival.",
        (
            _op("reclamar", "Reclamar a la aerolínea públicamente", Intensidad.NEUTRA,
                (Efecto("hinchada", 2),), TipoReaccion.PRENSA),
            _op("aceptar", "Aceptar y enfocarse en el partido", Intensidad.NEUTRA,
                (Efecto("vestuario", 2),)),
        )),
    _ev("clima_extremo", CategoriaEvento.VIAJES, "Clima Extremo",
        "Alerta meteorológica para el día del partido. Se debate si pedir la suspensión.",
        (
            _op("pedir_suspension", "Pedir la suspensión", Intensidad.NEUTRA,
                (Efecto("confianza", -2),)),
            _op("jugar_igual", "Jugar de todas formas", Intensidad.NEUTRA,
                (Efecto("moral", 2),)),
        )),

    # ------------------------------------------------------------- VESTUARIO
    _ev("el_capitan", CategoriaEvento.VESTUARIO, "El Capitán",
        "El capitán está enojado por no ser tenido en cuenta en las decisiones importantes.",
        (
            _op("hablar", "Hablar con él en privado", Intensidad.POSITIVA,
                (Efecto("vestuario", 6),), TipoReaccion.VESTUARIO),
            _op("ignorar", "Ignorar el reclamo", Intensidad.NEGATIVA,
                (Efecto("vestuario", -6),), TipoReaccion.VESTUARIO),
            _op("sacar_cinta", "Sacarle la cinta de capitán", Intensidad.NEGATIVA,
                (Efecto("vestuario", -10), Efecto("hinchada", -3)), TipoReaccion.PRENSA),
        )),
    _ev("lider_silencioso", CategoriaEvento.VESTUARIO, "Líder Silencioso",
        "Un referente del plantel pide más protagonismo dentro del vestuario.",
        (
            _op("darle_lugar", "Darle más responsabilidad", Intensidad.POSITIVA,
                (Efecto("vestuario", 4),)),
            _op("mantener_orden", "Mantener el orden actual", Intensidad.NEUTRA,
                (Efecto("vestuario", -1),)),
        )),
    _ev("grupo_dividido", CategoriaEvento.VESTUARIO, "Grupo Dividido",
        "El plantel se nota partido en dos bandos y empieza a afectar los entrenamientos.",
        (
            _op("reunion_grupal", "Convocar una reunión general", Intensidad.POSITIVA,
                (Efecto("vestuario", 5),)),
            _op("dejar_pasar", "Dejar que se acomode solo", Intensidad.NEGATIVA,
                (Efecto("vestuario", -5),)),
        )),

    # --------------------------------------------------------------- MERCADO
    _ev("oferta_figura", CategoriaEvento.MERCADO, "Oferta por la Figura",
        "Un club grande hace una oferta importante por tu mejor jugador.",
        (
            _op("aceptar", "Aceptar la venta", Intensidad.NEGATIVA,
                (Efecto("presupuesto", 3000), Efecto("hinchada", -6)), TipoReaccion.HINCHADA),
            _op("rechazar", "Rechazar la oferta", Intensidad.POSITIVA,
                (Efecto("hinchada", 5), Efecto("confianza", -2)), TipoReaccion.HINCHADA),
            _op("negociar", "Negociar una cifra mayor", Intensidad.NEUTRA,
                (Efecto("presupuesto", 4000), Efecto("hinchada", -3))),
        )),
    _ev("refuerzo_ultimo_momento", CategoriaEvento.MERCADO, "Refuerzo de Último Momento",
        "Aparece una chance de sumar un jugador a precio de saldo antes del cierre del libro de pases.",
        (
            _op("firmar", "Cerrar el fichaje", Intensidad.POSITIVA,
                (Efecto("presupuesto", -800), Efecto("confianza", 3))),
            _op("pasar", "Dejarlo pasar", Intensidad.NEUTRA, ()),
        )),
    _ev("venta_forzada", CategoriaEvento.MERCADO, "Venta Forzada",
        "La dirigencia necesita caja urgente y pide liberar a un jugador importante.",
        (
            _op("acatar", "Acatar la decisión", Intensidad.NEGATIVA,
                (Efecto("presupuesto", 2000), Efecto("vestuario", -4)), TipoReaccion.VESTUARIO),
            _op("resistir", "Resistir la venta ante la dirigencia", Intensidad.NEUTRA,
                (Efecto("confianza", -5), Efecto("vestuario", 3)), TipoReaccion.DIRIGENCIA),
        )),

    # ------------------------------------------------------------ DIRIGENCIA
    _ev("presidente_nuevo", CategoriaEvento.DIRIGENCIA, "Presidente Nuevo",
        "Cambió la dirigencia del club. Los objetivos de la temporada podrían cambiar.",
        (
            _op("adaptarse", "Adaptarse al nuevo proyecto", Intensidad.NEUTRA,
                (Efecto("confianza", 2),)),
            _op("plantear_condiciones", "Plantear condiciones para continuar", Intensidad.NEUTRA,
                (Efecto("confianza", -3), Efecto("reputacion", 2))),
        )),
    _ev("recorte_presupuesto", CategoriaEvento.DIRIGENCIA, "Recorte de Presupuesto",
        "La institución atraviesa un ajuste y hay que arreglárselas con menos plata.",
        (
            _op("aceptar", "Aceptar el recorte sin quejas", Intensidad.NEUTRA,
                (Efecto("presupuesto", -1000), Efecto("confianza", 3))),
            _op("reclamar", "Reclamar públicamente", Intensidad.NEGATIVA,
                (Efecto("confianza", -6),), TipoReaccion.DIRIGENCIA),
        )),
    _ev("confianza_ciega", CategoriaEvento.DIRIGENCIA, "Confianza Ciega",
        "Después de una buena racha, la dirigencia te da carta blanca para decidir sin condiciones.",
        (
            _op("aprovechar", "Aprovechar la libertad para reforzar el plantel", Intensidad.POSITIVA,
                (Efecto("presupuesto", -1500), Efecto("confianza", 5))),
            _op("ser_prudente", "Ser prudente y no pedir de más", Intensidad.POSITIVA,
                (Efecto("confianza", 3),)),
        )),

    # ---------------------------------------------------------------- PRENSA
    _ev("conferencia_incomoda", CategoriaEvento.PRENSA, "Conferencia Incómoda",
        "La prensa te acorrala con preguntas después de una mala racha.",
        (
            _op("responder", "Responder con firmeza", Intensidad.NEUTRA,
                (Efecto("reputacion", 1),), TipoReaccion.PRENSA),
            _op("culpar", "Echarle la culpa al plantel", Intensidad.NEGATIVA,
                (Efecto("vestuario", -6), Efecto("reputacion", -2)), TipoReaccion.PRENSA),
            _op("no_hablar", "No responder ninguna pregunta", Intensidad.NEGATIVA,
                (Efecto("reputacion", -1),), TipoReaccion.PRENSA),
        )),
    _ev("filtracion", CategoriaEvento.PRENSA, "Filtración",
        "Una charla interna del vestuario se filtró a los medios.",
        (
            _op("investigar", "Investigar quién filtró", Intensidad.NEUTRA,
                (Efecto("vestuario", -2),)),
            _op("dejar_pasar", "Dejarlo pasar sin hacer olas", Intensidad.NEUTRA,
                (Efecto("vestuario", 1),)),
        )),
    _ev("elogio_inesperado", CategoriaEvento.PRENSA, "Elogio Inesperado",
        "Un cronista referente te banca en vivo tras una decisión polémica.",
        (
            _op("agradecer", "Agradecer públicamente", Intensidad.POSITIVA,
                (Efecto("reputacion", 3),), TipoReaccion.PRENSA),
            _op("restar_importancia", "Restarle importancia", Intensidad.NEUTRA,
                (Efecto("vestuario", 1),)),
        )),

    # -------------------------------------------------------------- LESIONES
    _ev("baja_sensible", CategoriaEvento.LESIONES, "Baja Sensible",
        "Se lesiona un titular clave justo antes de un partido importante.",
        (
            _op("plan_b", "Activar el plan B ya preparado", Intensidad.NEUTRA,
                (Efecto("vestuario", 2),)),
            _op("improvisar", "Improvisar sobre la marcha", Intensidad.NEGATIVA,
                (Efecto("confianza", -3),)),
        )),
    _ev("vuelta_anticipada", CategoriaEvento.LESIONES, "Vuelta Anticipada",
        "Un jugador lesionado pide volver antes de tiempo para no perderse un partido grande.",
        (
            _op("arriesgar", "Arriesgarlo", Intensidad.NEUTRA,
                (Efecto("moral", 3), Efecto("vestuario", -1))),
            _op("cuidar", "Cuidarlo y esperar el alta médica", Intensidad.POSITIVA,
                (Efecto("vestuario", 2),)),
        )),
    _ev("lesion_fantasma", CategoriaEvento.LESIONES, "Lesión Fantasma",
        "El cuerpo médico sospecha que un jugador exagera una molestia para no jugar.",
        (
            _op("confrontar", "Confrontarlo directamente", Intensidad.NEGATIVA,
                (Efecto("vestuario", -3),), TipoReaccion.VESTUARIO),
            _op("dar_beneficio_duda", "Darle el beneficio de la duda", Intensidad.NEUTRA,
                (Efecto("vestuario", 1),)),
        )),

    # ------------------------------------------------------------- JUVENILES
    _ev("el_juvenil", CategoriaEvento.JUVENILES, "El Juvenil",
        "La joya de las inferiores pide pista en primera.",
        (
            _op("titular", "Ponerlo de titular", Intensidad.POSITIVA,
                (Efecto("hinchada", 4), Efecto("confianza", -1))),
            _op("banco", "Sumarlo al banco", Intensidad.NEUTRA,
                (Efecto("hinchada", 1),)),
            _op("esperar", "Seguir esperando", Intensidad.NEGATIVA,
                (Efecto("hinchada", -2),)),
        )),
    _ev("oferta_joya", CategoriaEvento.JUVENILES, "Oferta por la Joya",
        "Un club grande quiere comprar a la joya de inferiores todavía sin debutar en primera.",
        (
            _op("vender", "Vender ahora que hay oferta", Intensidad.NEGATIVA,
                (Efecto("presupuesto", 1500), Efecto("hinchada", -4)), TipoReaccion.HINCHADA),
            _op("retener", "Retenerlo para que crezca en el club", Intensidad.POSITIVA,
                (Efecto("hinchada", 3),), TipoReaccion.HINCHADA),
        )),
    _ev("padre_presente", CategoriaEvento.JUVENILES, "Padre Presente",
        "El entorno del juvenil presiona por más minutos en cada rueda de prensa.",
        (
            _op("poner_limites", "Poner límites con el entorno", Intensidad.NEUTRA,
                (Efecto("vestuario", 1),)),
            _op("ceder", "Ceder algo de rodaje", Intensidad.NEUTRA,
                (Efecto("hinchada", 1),)),
        )),

    # -------------------------------------------------------------- SPONSORS
    _ev("sponsor_exigente", CategoriaEvento.SPONSORS, "Sponsor Exigente",
        "El sponsor principal pide resultados concretos a cambio de más presupuesto.",
        (
            _op("aceptar_condiciones", "Aceptar las condiciones", Intensidad.NEUTRA,
                (Efecto("presupuesto", 1000), Efecto("confianza", -2))),
            _op("rechazar", "Rechazar la propuesta", Intensidad.NEUTRA,
                (Efecto("confianza", 1),)),
        )),
    _ev("nuevo_auspiciante", CategoriaEvento.SPONSORS, "Nuevo Auspiciante",
        "Aparece un sponsor nuevo con plata extra, pero con condiciones raras para la imagen del club.",
        (
            _op("firmar", "Firmar el acuerdo", Intensidad.NEUTRA,
                (Efecto("presupuesto", 1200), Efecto("hinchada", -2))),
            _op("declinar", "Declinar la propuesta", Intensidad.NEUTRA, ()),
        )),
    _ev("ruptura_contrato", CategoriaEvento.SPONSORS, "Ruptura de Contrato",
        "Un sponsor se baja del club en medio de un escándalo ajeno a lo deportivo.",
        (
            _op("buscar_reemplazo", "Salir a buscar reemplazo ya", Intensidad.NEUTRA,
                (Efecto("presupuesto", -500),)),
            _op("resistir", "Bancar el bache económico", Intensidad.NEGATIVA,
                (Efecto("presupuesto", -1000), Efecto("confianza", -2))),
        )),

    # -------------------------------------------------------- INFRAESTRUCTURA
    _ev("cancha_mal_estado", CategoriaEvento.INFRAESTRUCTURA, "Cancha en Mal Estado",
        "El estado de la cancha propia empieza a afectar el rendimiento como local.",
        (
            _op("reclamar_arreglo", "Reclamar el arreglo a la dirigencia", Intensidad.NEUTRA,
                (Efecto("confianza", -2),), TipoReaccion.DIRIGENCIA),
            _op("adaptarse", "Adaptar el estilo de juego a la cancha", Intensidad.NEUTRA,
                (Efecto("vestuario", 1),)),
        )),
    _ev("nuevo_predio", CategoriaEvento.INFRAESTRUCTURA, "Nuevo Predio",
        "La dirigencia decide invertir en un predio nuevo para las inferiores.",
        (
            _op("celebrar", "Celebrar la decisión públicamente", Intensidad.POSITIVA,
                (Efecto("hinchada", 3), Efecto("confianza", 2)), TipoReaccion.HINCHADA),
            _op("pedir_prioridad", "Pedir que se priorice el plantel de primera", Intensidad.NEUTRA,
                (Efecto("confianza", -2),)),
        )),
    _ev("obra_frenada", CategoriaEvento.INFRAESTRUCTURA, "Obra Frenada",
        "Una mejora de infraestructura prometida sigue sin llegar.",
        (
            _op("reclamar", "Reclamar públicamente", Intensidad.NEGATIVA,
                (Efecto("confianza", -3),), TipoReaccion.PRENSA),
            _op("ignorar", "No hacer olas por ahora", Intensidad.NEUTRA, ()),
        )),

    # --------------------------------------------------------------- CLASICOS
    _ev("el_clasico", CategoriaEvento.CLASICOS, "El Clásico",
        "La ciudad entera se paraliza. Una derrota puede costarte el cargo.",
        (
            _op("plantel_mas_experiente", "Priorizar experiencia sobre juventud", Intensidad.NEUTRA,
                (Efecto("confianza", 2),)),
            _op("arriesgar", "Arriesgar con una alineación ofensiva", Intensidad.NEUTRA,
                (Efecto("hinchada", 2),)),
        )),
    _ev("historia_reciente", CategoriaEvento.CLASICOS, "Historia Reciente",
        "El equipo arrastra una mala racha puntual frente a este rival histórico.",
        (
            _op("hablar_del_pasado", "Hablarle al plantel sobre la historia", Intensidad.NEUTRA,
                (Efecto("vestuario", 2),)),
            _op("bajarle_el_precio", "Bajarle el precio al partido", Intensidad.NEUTRA,
                (Efecto("moral", 1),)),
        )),
    _ev("provocacion_rival", CategoriaEvento.CLASICOS, "Provocación Rival",
        "El DT del equipo rival te provoca en la previa a través de los medios.",
        (
            _op("responder", "Responderle con la misma moneda", Intensidad.NEUTRA,
                (Efecto("hinchada", 2), Efecto("reputacion", -1)), TipoReaccion.PRENSA),
            _op("bajar_perfil", "Bajar el perfil y no entrar en el juego", Intensidad.NEUTRA,
                (Efecto("reputacion", 1),)),
        )),

    # ----------------------------------------------------------------- CRISIS
    _ev("crisis_resultados", CategoriaEvento.CRISIS, "Crisis de Resultados",
        "Cinco partidos sin ganar y la presión empieza a sentirse en todos lados.",
        (
            _op("dar_la_cara", "Dar la cara ante los hinchas", Intensidad.NEUTRA,
                (Efecto("hinchada", 3), Efecto("confianza", -1)), TipoReaccion.HINCHADA),
            _op("encerrarse", "Encerrarse a trabajar sin hablar con nadie", Intensidad.NEGATIVA,
                (Efecto("confianza", -4),), TipoReaccion.PRENSA),
        )),
    _ev("motin_silencioso", CategoriaEvento.CRISIS, "Motín Silencioso",
        "El plantel cuestiona puertas adentro el método de trabajo del cuerpo técnico.",
        (
            _op("reunion_urgente", "Convocar una reunión urgente", Intensidad.NEUTRA,
                (Efecto("vestuario", 4),)),
            _op("sostener_metodo", "Sostener el método sin cambios", Intensidad.NEGATIVA,
                (Efecto("vestuario", -5),)),
        )),
    _ev("escandalo_extrafutbolistico", CategoriaEvento.CRISIS, "Escándalo Extrafutbolístico",
        "Un jugador aparece en la tapa de los diarios por algo completamente ajeno a lo deportivo.",
        (
            _op("respaldar", "Respaldarlo públicamente", Intensidad.NEUTRA,
                (Efecto("vestuario", 2), Efecto("reputacion", -1)), TipoReaccion.PRENSA),
            _op("marcar_distancia", "Marcar distancia del hecho", Intensidad.NEUTRA,
                (Efecto("vestuario", -2), Efecto("reputacion", 1)), TipoReaccion.PRENSA),
        )),

    # ------------------------------------------------------------ SELECCIONES
    _ev("convocatoria", CategoriaEvento.SELECCIONES, "Convocatoria",
        "Citan a un jugador clave a la selección a mitad de temporada.",
        (
            _op("celebrar", "Celebrar la convocatoria con el plantel", Intensidad.POSITIVA,
                (Efecto("moral", 3), Efecto("reputacion", 1)),),
            _op("preocuparse_desgaste", "Preocuparse por el desgaste físico", Intensidad.NEUTRA,
                (Efecto("confianza", -1),)),
        )),
    _ev("vuelve_golpeado", CategoriaEvento.SELECCIONES, "Vuelve Golpeado",
        "El jugador citado vuelve con la carga física al límite tras la fecha FIFA.",
        (
            _op("descansarlo", "Descansarlo el próximo partido", Intensidad.NEUTRA,
                (Efecto("vestuario", 1),)),
            _op("ponerlo_igual", "Ponerlo igual, hace falta", Intensidad.NEGATIVA,
                (Efecto("vestuario", -2),)),
        )),
    _ev("debut_seleccion", CategoriaEvento.SELECCIONES, "Debut en Selección",
        "Un jugador formado en el club debuta en la selección mayor.",
        (
            _op("destacar_formacion", "Destacar el trabajo formativo del club", Intensidad.POSITIVA,
                (Efecto("reputacion", 3), Efecto("hinchada", 2)), TipoReaccion.PRENSA),
            _op("bajo_perfil", "Mantener bajo perfil sobre el mérito propio", Intensidad.NEUTRA,
                (Efecto("reputacion", 1),)),
        )),

    # ----------------------------------------------------------------- COPAS
    _ev("sorpresa_copera", CategoriaEvento.COPAS, "Sorpresa Copera",
        "Eliminaste a un grande en la Copa Argentina. Todo el país habla de vos.",
        (
            _op("disfrutar", "Disfrutar el momento con el plantel", Intensidad.POSITIVA,
                (Efecto("moral", 5), Efecto("reputacion", 4)), TipoReaccion.PRENSA),
            _op("bajar_expectativas", "Bajar las expectativas de inmediato", Intensidad.NEUTRA,
                (Efecto("reputacion", 2),)),
        )),
    _ev("final_historica", CategoriaEvento.COPAS, "Final Histórica",
        "Se juega todo en 90 minutos: la final que puede cambiar tu carrera.",
        (
            _op("apostar_titulares", "Ir con lo mejor que tenés", Intensidad.NEUTRA,
                (Efecto("confianza", 2),)),
            _op("sorpresa_tactica", "Sorprender con un planteo distinto", Intensidad.NEUTRA,
                (Efecto("reputacion", 1),)),
        )),
    _ev("grupos_complejos", CategoriaEvento.COPAS, "Fase de Grupos Compleja",
        "Viajes largos y climas muy distintos entre rivales de Libertadores o Sudamericana.",
        (
            _op("priorizar_local", "Priorizar los partidos de local", Intensidad.NEUTRA,
                (Efecto("confianza", 1),)),
            _op("apostar_todo", "Ir a fondo por la clasificación", Intensidad.NEUTRA,
                (Efecto("presupuesto", -300),)),
        )),

    # ---------------------------------------------------------- LIBERTADORES
    # Solo aplican a clubes con PerfilClub.clasifica_copas_internacionales=True
    # (los grandes de Primera). Ver manager_mode/copas_continentales.py.
    _ev("grupo_muerte_libertadores", CategoriaEvento.LIBERTADORES, "Grupo de la Muerte",
        "El sorteo te cruzó con dos candidatos al título en la misma zona.",
        (
            _op("priorizar_libertadores", "Priorizar la Copa desde la fase de grupos", Intensidad.NEUTRA,
                (Efecto("reputacion", 1), Efecto("confianza", -1))),
            _op("priorizar_liga", "Priorizar el torneo local", Intensidad.NEUTRA,
                (Efecto("confianza", 2),)),
        )),
    _ev("viaje_altura", CategoriaEvento.LIBERTADORES, "Viaje a la Altura",
        "Toca visitar a un rival boliviano a más de 3.000 metros de altura.",
        (
            _op("concentrar_antes", "Concentrar varios días antes para aclimatarse", Intensidad.NEUTRA,
                (Efecto("presupuesto", -400), Efecto("moral", 2))),
            _op("viajar_mismo_dia", "Viajar el mismo día del partido", Intensidad.NEGATIVA,
                (Efecto("moral", -3),)),
        )),
    _ev("prestigio_continental", CategoriaEvento.LIBERTADORES, "Prestigio en Juego",
        "Toda Sudamérica sigue la serie por televisión: es tu vidriera internacional.",
        (
            _op("disfrutar_vidriera", "Disfrutar la vidriera y hablar con confianza", Intensidad.POSITIVA,
                (Efecto("reputacion", 2),), TipoReaccion.PRENSA),
            _op("bajar_presion", "Bajarle el precio en la conferencia previa", Intensidad.NEUTRA,
                (Efecto("confianza", 1),)),
        )),

    # ----------------------------------------------------------- SUDAMERICANA
    # Idem Libertadores: solo para clubes con clasifica_copas_internacionales.
    _ev("el_hermano_menor", CategoriaEvento.SUDAMERICANA, "El Hermano Menor",
        "La prensa compara todo el tiempo la Sudamericana con la Libertadores.",
        (
            _op("reivindicar_torneo", "Reivindicar la importancia del torneo", Intensidad.POSITIVA,
                (Efecto("hinchada", 2),), TipoReaccion.PRENSA),
            _op("restarle_valor", "Restarle valor frente a la prensa", Intensidad.NEGATIVA,
                (Efecto("hinchada", -2),), TipoReaccion.HINCHADA),
        )),
    _ev("playoff_ida_vuelta", CategoriaEvento.SUDAMERICANA, "Playoff de Ida y Vuelta",
        "Un cruce a partido de ida y vuelta define la clasificación a octavos.",
        (
            _op("resguardar_titulares", "Resguardar a los titulares para la vuelta", Intensidad.NEUTRA,
                (Efecto("confianza", 1),)),
            _op("arriesgar_todo", "Arriesgar todo en la ida", Intensidad.NEUTRA,
                (Efecto("reputacion", 1),)),
        )),
    _ev("rival_sorpresa_brasil", CategoriaEvento.SUDAMERICANA, "Rival Sorpresa",
        "Te toca un equipo chico de Brasil que viene de eliminar a un grande.",
        (
            _op("tomarlo_en_serio", "Tomarlo en serio desde el análisis", Intensidad.POSITIVA,
                (Efecto("vestuario", 2),)),
            _op("subestimarlo", "Subestimarlo en la previa", Intensidad.NEGATIVA,
                (Efecto("vestuario", -3),), TipoReaccion.PRENSA),
        )),

    # -------------------------------------------------------------- RUMORES
    _ev("rumor_salida", CategoriaEvento.RUMORES, "Rumor de Salida",
        "Se filtra que otro club te sondea para la próxima temporada.",
        (
            _op("desmentir", "Desmentirlo públicamente", Intensidad.NEUTRA,
                (Efecto("confianza", 2),), TipoReaccion.PRENSA),
            _op("no_confirmar_ni_desmentir", "No confirmar ni desmentir", Intensidad.NEGATIVA,
                (Efecto("confianza", -3),), TipoReaccion.DIRIGENCIA),
        )),
    _ev("sospecha_amanio", CategoriaEvento.RUMORES, "Sospecha de Amaño",
        "Un resultado raro genera ruido mediático sobre la honestidad del certamen.",
        (
            _op("pedir_investigacion", "Pedir una investigación formal", Intensidad.NEUTRA,
                (Efecto("reputacion", 1),), TipoReaccion.PRENSA),
            _op("no_opinar", "No opinar sobre el tema", Intensidad.NEUTRA, ()),
        )),
    _ev("escandalo_vestuario", CategoriaEvento.RUMORES, "Escándalo de Vestuario",
        "Trasciende públicamente un conflicto interno que se creía privado.",
        (
            _op("dar_explicaciones", "Dar explicaciones a la prensa", Intensidad.NEUTRA,
                (Efecto("vestuario", -1),), TipoReaccion.PRENSA),
            _op("cerrar_filas", "Cerrar filas y no hablar del tema", Intensidad.NEGATIVA,
                (Efecto("vestuario", -3),), TipoReaccion.PRENSA),
        )),

    # ------------------------------------------------------ ARBITROS_HINCHADA
    _ev("polemica_arbitral", CategoriaEvento.ARBITROS_HINCHADA, "Polémica Arbitral",
        "Un fallo arbitral discutido termina cambiando el resultado del partido.",
        (
            _op("reclamar_publico", "Reclamar públicamente tras el partido", Intensidad.NEUTRA,
                (Efecto("hinchada", 2), Efecto("reputacion", -1)), TipoReaccion.PRENSA),
            _op("no_hablar_arbitraje", "No hablar del arbitraje", Intensidad.NEUTRA,
                (Efecto("reputacion", 1),)),
        )),
    _ev("la_barra", CategoriaEvento.ARBITROS_HINCHADA, "La Barra",
        "Organizan un banderazo de aliento antes de un partido clave.",
        (
            _op("ir", "Ir a agradecerles personalmente", Intensidad.NEUTRA,
                (Efecto("hinchada", 4), Efecto("reputacion", -1))),
            _op("no_ir", "No ir, mantener distancia institucional", Intensidad.NEUTRA,
                (Efecto("hinchada", -2), Efecto("reputacion", 1))),
            _op("mandar_jugadores", "Mandar a algunos jugadores en tu lugar", Intensidad.NEUTRA,
                (Efecto("hinchada", 2),)),
        )),
    _ev("aliento_incondicional", CategoriaEvento.ARBITROS_HINCHADA, "Aliento Incondicional",
        "La hinchada responde con un aliento total en el peor momento del equipo.",
        (
            _op("agradecer_publico", "Agradecer públicamente en conferencia", Intensidad.POSITIVA,
                (Efecto("hinchada", 3),), TipoReaccion.HINCHADA),
            _op("enfocarse_trabajo", "Enfocarse solo en el trabajo diario", Intensidad.NEUTRA,
                (Efecto("vestuario", 1),)),
        )),

    # ---------------------------------------------------------- VIDA_PLANTEL
    _ev("guerra_de_faldas", CategoriaEvento.VIDA_PLANTEL, "Guerra de Faldas",
        "Dos jugadores se pelean puertas adentro porque uno le \"levantó\" la novia al otro.",
        (
            _op("mediar", "Mediar entre los dos", Intensidad.NEUTRA,
                (Efecto("vestuario", 2),)),
            _op("separarlos", "Separarlos y bajar el tema al instante", Intensidad.NEUTRA,
                (Efecto("vestuario", -1),)),
            _op("dejar_que_se_arreglen", "Dejar que se arreglen solos", Intensidad.NEGATIVA,
                (Efecto("vestuario", -4),)),
        )),
    _ev("noche_de_joda", CategoriaEvento.VIDA_PLANTEL, "Noche de Joda",
        "Un grupo del plantel sale de fiesta antes de un partido importante y se filtra en redes.",
        (
            _op("sancionar", "Sancionar a los responsables", Intensidad.NEGATIVA,
                (Efecto("vestuario", -3), Efecto("reputacion", 1)), TipoReaccion.PRENSA),
            _op("llamado_atencion", "Un llamado de atención privado", Intensidad.NEUTRA,
                (Efecto("vestuario", 1),)),
            _op("hacer_la_vista_gorda", "Hacer la vista gorda", Intensidad.NEGATIVA,
                (Efecto("vestuario", -2), Efecto("confianza", -1))),
        )),
    _ev("el_bromista", CategoriaEvento.VIDA_PLANTEL, "El Bromista",
        "Un jugador le hace una cargada pesada a otro delante de todo el plantel y se arma quilombo.",
        (
            _op("frenar_la_joda", "Frenar la joda ahí mismo", Intensidad.NEUTRA,
                (Efecto("vestuario", 1),)),
            _op("reirse_con_el_grupo", "Reírse y aflojar la tensión", Intensidad.POSITIVA,
                (Efecto("vestuario", 3), Efecto("moral", 2))),
        )),
    _ev("pelea_de_egos", CategoriaEvento.VIDA_PLANTEL, "Pelea de Egos",
        "Dos figuras del plantel se disputan en voz alta quién patea los penales.",
        (
            _op("elegir_uno", "Definir un pateador fijo", Intensidad.NEUTRA,
                (Efecto("vestuario", -1),)),
            _op("rotar", "Rotar según el partido", Intensidad.NEUTRA,
                (Efecto("vestuario", 1),)),
        )),
    _ev("el_nuevo_no_encaja", CategoriaEvento.VIDA_PLANTEL, "El Nuevo No Encaja",
        "Un refuerzo caro no logra hacer buena migas con el grupo.",
        (
            _op("integrarlo", "Organizar una actividad para integrarlo", Intensidad.POSITIVA,
                (Efecto("vestuario", 3),)),
            _op("dejarlo_solo", "Dejar que se acomode a su ritmo", Intensidad.NEUTRA,
                (Efecto("vestuario", -1),)),
        )),
    _ev("cabala_grupal", CategoriaEvento.VIDA_PLANTEL, "Cábala Grupal",
        "El plantel se agarra de una cábala ridícula (las medias, el asiento del micro, la comida) y exige respetarla.",
        (
            _op("seguirles_la_cabala", "Seguirles la cábala", Intensidad.POSITIVA,
                (Efecto("moral", 3),)),
            _op("cortar_por_lo_sano", "Cortar por lo sano, esto no suma", Intensidad.NEGATIVA,
                (Efecto("vestuario", -2),)),
        )),
    _ev("cumpleanos_descontrolado", CategoriaEvento.VIDA_PLANTEL, "Cumpleaños Descontrolado",
        "Un festejo de cumpleaños en la concentración se va completamente de tema.",
        (
            _op("cortar_la_fiesta", "Cortar la fiesta ahí mismo", Intensidad.NEGATIVA,
                (Efecto("vestuario", -2),)),
            _op("dejar_que_termine", "Dejar que termine con horario límite", Intensidad.NEUTRA,
                (Efecto("moral", 1),)),
        )),
]

CATALOGO_EVENTOS: dict[str, Evento] = {evento.codigo: evento for evento in _EVENTOS}


def eventos_por_categoria(categoria: CategoriaEvento) -> list[Evento]:
    """Devuelve todos los eventos del catálogo de una categoría dada."""
    return [evento for evento in _EVENTOS if evento.categoria == categoria]
