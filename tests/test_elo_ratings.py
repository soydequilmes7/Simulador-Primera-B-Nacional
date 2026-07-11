from season.elo_ratings import actualizar_por_partido, rating_default


def test_actualizar_por_partido_mueve_los_cuatro_componentes_relevantes():
    local = rating_default()
    visitante = rating_default()

    update = actualizar_por_partido(
        local,
        visitante,
        goles_local=3,
        goles_visitante=0,
        promedio_local=1.35,
        promedio_visitante=1.05,
    )

    assert update.expected_local == 1.35
    assert update.expected_visitante == 1.05
    assert update.local_post["ataque_local"] > local["ataque_local"]
    assert update.visitante_post["defensa_visitante"] > visitante["defensa_visitante"]
    assert update.visitante_post["ataque_visitante"] < visitante["ataque_visitante"]
    assert update.local_post["defensa_local"] < local["defensa_local"]
    assert update.local_post["partidos_computados"] == 1
    assert update.visitante_post["partidos_computados"] == 1


def test_k_efectivo_baja_con_partidos_computados():
    nuevo = rating_default()
    asentado = {**rating_default(), "partidos_computados": 160}

    update_nuevo = actualizar_por_partido(nuevo, nuevo, 3, 0, 1.35, 1.05)
    update_asentado = actualizar_por_partido(asentado, asentado, 3, 0, 1.35, 1.05)

    assert update_nuevo.local_post["ataque_local"] - 1.0 > update_asentado.local_post["ataque_local"] - 1.0
