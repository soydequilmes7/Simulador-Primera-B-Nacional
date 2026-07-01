class Equipo:

    def __init__(self, nombre):

        self.nombre = nombre

        # Últimos partidos
        self.ultimos10 = []

        self.zona = None

        # Estadísticas
        self.puntos = 0
        self.goles_favor = 0
        self.goles_contra = 0

        # Local
        self.local_gf = 0
        self.local_gc = 0

        # Visitante
        self.visitante_gf = 0
        self.visitante_gc = 0

    # Cantidad de partidos considerados en cada ventana (puede ser <10)
        self.partidos_local_n = 0
        self.partidos_visitante_n = 0

    # Ratings de ataque/defensa (relativos al promedio de liga)
        self.ataque_local = 1.0
        self.defensa_local = 1.0
        self.ataque_visitante = 1.0
        self.defensa_visitante = 1.0

    def __str__(self):
        return self.nombre