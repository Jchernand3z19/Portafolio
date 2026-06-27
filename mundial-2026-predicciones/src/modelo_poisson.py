"""
Modelo Poisson para predicción de partidos del Mundial 2026.

Este módulo contiene la lógica matemática del modelo:
- cálculo de goles esperados
- probabilidades de victoria, empate y derrota
- marcador estimado
- favorito
- nivel de confianza
"""

import math
import numpy as np
import pandas as pd

from src.utils import texto_limpio, numero


MAX_GOLES_POISSON = 8


def poisson_pmf(k, lam):
    """
    Calcula la probabilidad de marcar k goles usando distribución Poisson.
    """
    return (math.exp(-lam) * (lam ** k)) / math.factorial(k)


def calcular_probs_poisson(lambda_a, lambda_b, max_goles=MAX_GOLES_POISSON):
    """
    Calcula probabilidades de:
    - gana equipo A
    - empate
    - gana equipo B

    También devuelve el marcador más probable.
    """
    probs_a = [poisson_pmf(i, lambda_a) for i in range(max_goles + 1)]
    probs_b = [poisson_pmf(i, lambda_b) for i in range(max_goles + 1)]

    matriz = np.outer(probs_a, probs_b)
    matriz = matriz / matriz.sum()

    prob_gana_a = 0
    prob_empate = 0
    prob_gana_b = 0

    marcador_max = (0, 0)
    prob_marcador_max = -1

    for i in range(max_goles + 1):
        for j in range(max_goles + 1):
            p = matriz[i, j]

            if i > j:
                prob_gana_a += p
            elif i == j:
                prob_empate += p
            else:
                prob_gana_b += p

            if p > prob_marcador_max:
                prob_marcador_max = p
                marcador_max = (i, j)

    return prob_gana_a, prob_empate, prob_gana_b, marcador_max


def clasificar_confianza(prob_top, prob_second):
    """
    Clasifica la confianza de la predicción.

    Alta:
    - favorito con probabilidad >= 65%
    - margen sobre segunda opción >= 15 puntos porcentuales

    Media:
    - favorito con probabilidad >= 50%
    - margen sobre segunda opción >= 8 puntos porcentuales

    Baja:
    - partido parejo o sin favorito fuerte
    """
    margen = prob_top - prob_second

    if prob_top >= 0.65 and margen >= 0.15:
        return "Alta"
    elif prob_top >= 0.50 and margen >= 0.08:
        return "Media"
    else:
        return "Baja"


def obtener_factores_equipo(
    codigo,
    ranking_dict,
    stats_dict,
    global_gf,
    global_ga,
):
    """
    Obtiene los factores de fuerza de una selección:
    - ranking FIFA
    - puntos FIFA
    - Elo
    - ataque reciente
    - debilidad defensiva reciente
    """
    codigo = texto_limpio(codigo).upper()

    r = ranking_dict.get(codigo, {})
    s = stats_dict.get(codigo, {})

    puntos_fifa = numero(r.get("puntos_fifa", np.nan))
    elo = numero(r.get("elo", np.nan))
    ranking_fifa = numero(r.get("ranking_fifa", np.nan))

    gf = numero(s.get("gf_prom_pond", np.nan))
    ga = numero(s.get("ga_prom_pond", np.nan))
    partidos = numero(s.get("partidos_recientes", 0), 0)
    puntos_prom = numero(s.get("puntos_prom_pond", np.nan))

    if pd.isna(gf) or gf <= 0:
        gf = global_gf

    if pd.isna(ga) or ga <= 0:
        ga = global_ga

    if pd.isna(puntos_prom):
        puntos_prom = 1.3

    ataque = gf / global_gf
    defensa_debilidad = ga / global_ga

    ataque = np.clip(ataque, 0.60, 1.60)
    defensa_debilidad = np.clip(defensa_debilidad, 0.60, 1.60)

    return {
        "codigo": codigo,
        "puntos_fifa": puntos_fifa,
        "elo": elo,
        "ranking_fifa": ranking_fifa,
        "ataque": ataque,
        "defensa_debilidad": defensa_debilidad,
        "partidos_recientes": partidos,
        "puntos_prom": puntos_prom,
    }


def calcular_lambdas(
    codigo_a,
    codigo_b,
    ranking_dict,
    stats_dict,
    global_gf,
    global_ga,
):
    """
    Calcula goles esperados para ambos equipos.
    """
    a = obtener_factores_equipo(
        codigo_a,
        ranking_dict,
        stats_dict,
        global_gf,
        global_ga,
    )

    b = obtener_factores_equipo(
        codigo_b,
        ranking_dict,
        stats_dict,
        global_gf,
        global_ga,
    )

    base_goles = 1.35

    diff_fifa = 0
    if not pd.isna(a["puntos_fifa"]) and not pd.isna(b["puntos_fifa"]):
        diff_fifa = (a["puntos_fifa"] - b["puntos_fifa"]) / 200

    diff_elo = 0
    if not pd.isna(a["elo"]) and not pd.isna(b["elo"]):
        diff_elo = (a["elo"] - b["elo"]) / 400

    fuerza_diff = (0.55 * diff_fifa) + (0.45 * diff_elo)
    fuerza_diff = np.clip(fuerza_diff, -1.00, 1.00)

    lambda_a = (
        base_goles
        * a["ataque"]
        * b["defensa_debilidad"]
        * math.exp(0.35 * fuerza_diff)
    )

    lambda_b = (
        base_goles
        * b["ataque"]
        * a["defensa_debilidad"]
        * math.exp(-0.35 * fuerza_diff)
    )

    lambda_a = float(np.clip(lambda_a, 0.20, 4.50))
    lambda_b = float(np.clip(lambda_b, 0.20, 4.50))

    return lambda_a, lambda_b


def predecir_partido(
    equipo_a,
    codigo_a,
    equipo_b,
    codigo_b,
    ranking_dict,
    stats_dict,
    global_gf,
    global_ga,
):
    """
    Predice un partido y devuelve probabilidades, favorito,
    confianza y marcador estimado.
    """
    lambda_a, lambda_b = calcular_lambdas(
        codigo_a,
        codigo_b,
        ranking_dict,
        stats_dict,
        global_gf,
        global_ga,
    )

    prob_a, prob_empate, prob_b, marcador = calcular_probs_poisson(
        lambda_a,
        lambda_b,
        MAX_GOLES_POISSON,
    )

    opciones = [
        ("A", prob_a),
        ("Empate", prob_empate),
        ("B", prob_b),
    ]

    opciones_ordenadas = sorted(opciones, key=lambda x: x[1], reverse=True)

    top_label, top_prob = opciones_ordenadas[0]
    second_prob = opciones_ordenadas[1][1]

    if top_label == "A":
        favorito = equipo_a
    elif top_label == "B":
        favorito = equipo_b
    else:
        favorito = "Empate"

    confianza = clasificar_confianza(top_prob, second_prob)

    return {
        "goles_esperados_a": lambda_a,
        "goles_esperados_b": lambda_b,
        "prob_a": prob_a,
        "prob_empate": prob_empate,
        "prob_b": prob_b,
        "favorito": favorito,
        "prob_favorito": top_prob,
        "confianza": confianza,
        "marcador_estimado": f"{marcador[0]}-{marcador[1]}",
    }
