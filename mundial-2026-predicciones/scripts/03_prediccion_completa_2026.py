"""
Predicción completa base Mundial 2026.

Este script genera una simulación pura del Mundial completo.

Importante:
- NO usa resultados reales del Mundial actual.
- NO usa goles_a/goles_b del calendario.
- NO usa estado = Jugado del calendario.
- Usa el calendario solo como estructura: grupos, partidos, fases y equipos.
- Usa ranking, Elo, forma reciente histórica y modelo Poisson.

Salida:
- fact_prediccion_completa_2026
- fact_tabla_grupos_predicha_2026
- fact_camino_predicho_2026

Este script está pensado para ejecutarse manualmente una vez,
no como parte del workflow diario.
"""

from datetime import datetime
import re
import unicodedata

import numpy as np
import pandas as pd

from src.config import (
    TAB_CALENDARIO,
    TAB_RANKING,
    TAB_RESULTADOS,
    TAB_PREDICCION_COMPLETA,
    TAB_TABLA_GRUPOS_PREDICHA,
    TAB_CAMINO_PREDICHO,
    TAB_LOGS,
    MODEL_VERSION,
    MODELO_NOMBRE,
    ENVIRONMENT,
)

from src.sheets_client import (
    leer_hoja,
    escribir_df_en_hoja,
    append_df_en_hoja,
)

from src.utils import (
    limpiar_columnas,
    texto_limpio,
    numero,
    entero,
    fecha_yyyy_mm_dd,
    codigo_valido,
    equipo_valido,
)

from src.modelo_poisson import predecir_partido


RUN_ID = datetime.now().strftime("run_completa_%Y%m%d_%H%M%S")
FECHA_HORA_EJECUCION = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

ESCENARIO = "simulacion_base"
USA_RESULTADOS_REALES_MUNDIAL = "No"

GROUPS = list("ABCDEFGHIJKL")
HALF_LIFE_DIAS = 365


COLUMNAS_PARTIDOS = [
    "run_id",
    "fecha_hora_ejecucion",
    "escenario",
    "usa_resultados_reales_mundial",
    "fase",
    "orden_fase",
    "match_id",
    "fecha",
    "grupo",
    "equipo_a",
    "codigo_a",
    "equipo_b",
    "codigo_b",
    "goles_estimados_a",
    "goles_estimados_b",
    "marcador_estimado",
    "prob_a",
    "prob_empate",
    "prob_b",
    "favorito",
    "ganador_predicho",
    "codigo_ganador_predicho",
    "perdedor_predicho",
    "codigo_perdedor_predicho",
    "confianza",
    "tipo_prediccion",
    "modelo",
    "version_modelo",
    "notas",
]


COLUMNAS_GRUPOS = [
    "run_id",
    "fecha_hora_ejecucion",
    "escenario",
    "grupo",
    "posicion_grupo",
    "seleccion",
    "codigo",
    "pj",
    "pg",
    "pe",
    "pp",
    "gf",
    "gc",
    "dg",
    "pts",
    "clasifica",
    "tipo_clasificacion",
    "version_modelo",
]


COLUMNAS_CAMINO = [
    "run_id",
    "fecha_hora_ejecucion",
    "escenario",
    "seleccion",
    "codigo",
    "grupo",
    "posicion_grupo_predicha",
    "clasifica_grupos",
    "tipo_clasificacion",
    "ronda_alcanzada",
    "eliminado_por",
    "codigo_eliminado_por",
    "campeon_predicho",
    "subcampeon_predicho",
    "tercer_lugar_predicho",
    "cuarto_lugar_predicho",
    "version_modelo",
]


def quitar_acentos(texto):
    """
    Quita acentos para facilitar búsquedas de texto.
    """
    texto = texto_limpio(texto)
    return "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )


def texto_norm(texto):
    """
    Normaliza texto para comparaciones.
    """
    return quitar_acentos(texto).upper().strip()


def id_limpio(x):
    """
    Convierte match_id a texto estable.
    Evita diferencias tipo 71 vs 71.0.
    """
    if pd.isna(x):
        return ""

    txt = str(x).strip()

    if txt.endswith(".0"):
        txt = txt[:-2]

    return txt


def es_placeholder(texto):
    """
    Detecta si un texto parece placeholder y no una selección real.
    """
    t = texto_norm(texto)

    palabras_placeholder = [
        "TBD",
        "PENDIENTE",
        "GANADOR",
        "WINNER",
        "VENCEDOR",
        "PERDEDOR",
        "LOSER",
        "GRUPO",
        "GROUP",
        "RUNNER",
        "SEGUNDO",
        "TERCERO",
        "THIRD",
        "1ST",
        "2ND",
        "3RD",
        "W OF",
        "L OF",
    ]

    return any(p in t for p in palabras_placeholder)


def equipo_concreto(equipo, codigo):
    """
    Valida si un slot ya contiene una selección real.
    """
    equipo = texto_limpio(equipo)
    codigo = texto_limpio(codigo).upper()

    if not equipo_valido(equipo):
        return False

    if not codigo_valido(codigo):
        return False

    if len(codigo) != 3:
        return False

    if es_placeholder(f"{equipo} {codigo}"):
        return False

    return True


def fase_normalizada(fase):
    """
    Normaliza nombres de fase.
    """
    f = texto_norm(fase)

    if any(x in f for x in ["GRUPO", "GROUP"]):
        return "Fase de grupos"

    if any(x in f for x in ["RONDA DE 32", "ROUND OF 32", "32"]):
        return "Ronda de 32"

    if any(x in f for x in ["OCTAVOS", "ROUND OF 16", "16"]):
        return "Octavos"

    if any(x in f for x in ["CUARTOS", "QUARTER"]):
        return "Cuartos"

    if any(x in f for x in ["SEMIFINAL"]):
        return "Semifinal"

    if any(x in f for x in ["TERCER", "3RD", "THIRD"]):
        return "Tercer lugar"

    if "FINAL" in f:
        return "Final"

    return texto_limpio(fase)


def orden_fase(fase):
    """
    Orden lógico de fases.
    """
    orden = {
        "Fase de grupos": 1,
        "Ronda de 32": 2,
        "Octavos": 3,
        "Cuartos": 4,
        "Semifinal": 5,
        "Tercer lugar": 6,
        "Final": 7,
    }

    return orden.get(fase, 99)


def cargar_tablas():
    """
    Lee las tablas necesarias desde Google Sheets.
    """
    calendario = limpiar_columnas(leer_hoja(TAB_CALENDARIO))
    ranking = limpiar_columnas(leer_hoja(TAB_RANKING))
    resultados = limpiar_columnas(leer_hoja(TAB_RESULTADOS))

    print("Tablas cargadas:")
    print("Calendario:", calendario.shape)
    print("Ranking:", ranking.shape)
    print("Resultados recientes:", resultados.shape)

    return calendario, ranking, resultados


def validar_columnas(calendario, ranking, resultados):
    """
    Valida columnas mínimas.
    """
    columnas_calendario = [
        "match_id",
        "fecha",
        "fase",
        "grupo",
        "equipo_a",
        "codigo_a",
        "equipo_b",
        "codigo_b",
    ]

    columnas_ranking = [
        "codigo",
        "seleccion",
        "ranking_fifa",
        "puntos_fifa",
        "elo",
    ]

    columnas_resultados = [
        "fecha",
        "codigo_local",
        "codigo_visitante",
        "goles_local",
        "goles_visitante",
    ]

    for col in columnas_calendario:
        if col not in calendario.columns:
            raise ValueError(f"Falta columna en calendario: {col}")

    for col in columnas_ranking:
        if col not in ranking.columns:
            raise ValueError(f"Falta columna en dim_ranking_equipos: {col}")

    for col in columnas_resultados:
        if col not in resultados.columns:
            raise ValueError(f"Falta columna en fact_resultados_recientes: {col}")


def preparar_ranking(ranking):
    """
    Limpia ranking FIFA/Elo y crea diccionarios.
    """
    ranking = ranking.copy()

    ranking["codigo"] = ranking["codigo"].astype(str).str.strip().str.upper()
    ranking["seleccion"] = ranking["seleccion"].astype(str).str.strip()
    ranking["ranking_fifa"] = ranking["ranking_fifa"].apply(numero)
    ranking["puntos_fifa"] = ranking["puntos_fifa"].apply(numero)
    ranking["elo"] = ranking["elo"].apply(numero)

    ranking = ranking.drop_duplicates(subset=["codigo"], keep="first")

    ranking_dict = ranking.set_index("codigo").to_dict("index")
    codigos_objetivo = set(ranking["codigo"].dropna().astype(str).str.upper())

    print("Selecciones en ranking:", len(codigos_objetivo))

    return ranking, ranking_dict, codigos_objetivo


def crear_clave_resultado(row):
    """
    Crea clave para evitar duplicados en resultados recientes.
    """
    fecha_txt = row["fecha"].strftime("%Y-%m-%d") if not pd.isna(row["fecha"]) else ""

    codigo_1 = texto_limpio(row["codigo_local"]).upper()
    codigo_2 = texto_limpio(row["codigo_visitante"]).upper()

    goles_1 = int(row["goles_local"])
    goles_2 = int(row["goles_visitante"])

    pares = sorted(
        [
            (codigo_1, goles_1),
            (codigo_2, goles_2),
        ],
        key=lambda x: x[0],
    )

    return f"{fecha_txt}|{pares[0][0]}:{pares[0][1]}|{pares[1][0]}:{pares[1][1]}"


def preparar_resultados_modelo(resultados, codigos_objetivo):
    """
    Prepara resultados recientes históricos para alimentar el modelo.

    Importante:
    Esta función NO agrega resultados reales del Mundial actual desde el calendario.
    """
    resultados = resultados.copy()

    resultados["fecha"] = resultados["fecha"].apply(fecha_yyyy_mm_dd)
    resultados["codigo_local"] = resultados["codigo_local"].astype(str).str.strip().str.upper()
    resultados["codigo_visitante"] = resultados["codigo_visitante"].astype(str).str.strip().str.upper()
    resultados["goles_local"] = resultados["goles_local"].apply(entero)
    resultados["goles_visitante"] = resultados["goles_visitante"].apply(entero)

    resultados = resultados[
        resultados["fecha"].notna()
        & resultados["goles_local"].notna()
        & resultados["goles_visitante"].notna()
        & resultados["codigo_local"].apply(codigo_valido)
        & resultados["codigo_visitante"].apply(codigo_valido)
    ].copy()

    resultados = resultados[
        resultados["codigo_local"].isin(codigos_objetivo)
        & resultados["codigo_visitante"].isin(codigos_objetivo)
    ].copy()

    resultados["clave_resultado"] = resultados.apply(crear_clave_resultado, axis=1)

    resultados = (
        resultados
        .drop_duplicates(subset=["clave_resultado"], keep="first")
        .drop(columns=["clave_resultado"])
        .copy()
    )

    fecha_actual = pd.Timestamp.today().normalize()
    dias_antiguedad = (fecha_actual - resultados["fecha"]).dt.days.clip(lower=0)
    resultados["peso_recencia"] = 0.5 ** (dias_antiguedad / HALF_LIFE_DIAS)

    print("Resultados recientes históricos válidos para el modelo:", len(resultados))

    return resultados


def calcular_estadisticas_seleccion(resultados, codigos_objetivo):
    """
    Calcula estadísticas ponderadas por selección.
    """
    registros_team = []

    for _, row in resultados.iterrows():
        local = row["codigo_local"]
        visitante = row["codigo_visitante"]
        gl = row["goles_local"]
        gv = row["goles_visitante"]
        peso = row["peso_recencia"]

        if codigo_valido(local):
            if gl > gv:
                puntos = 3
                win, draw, loss = 1, 0, 0
            elif gl == gv:
                puntos = 1
                win, draw, loss = 0, 1, 0
            else:
                puntos = 0
                win, draw, loss = 0, 0, 1

            registros_team.append(
                {
                    "codigo": local,
                    "partido": 1,
                    "gf": gl,
                    "ga": gv,
                    "puntos": puntos,
                    "win": win,
                    "draw": draw,
                    "loss": loss,
                    "peso": peso,
                }
            )

        if codigo_valido(visitante):
            if gv > gl:
                puntos = 3
                win, draw, loss = 1, 0, 0
            elif gv == gl:
                puntos = 1
                win, draw, loss = 0, 1, 0
            else:
                puntos = 0
                win, draw, loss = 0, 0, 1

            registros_team.append(
                {
                    "codigo": visitante,
                    "partido": 1,
                    "gf": gv,
                    "ga": gl,
                    "puntos": puntos,
                    "win": win,
                    "draw": draw,
                    "loss": loss,
                    "peso": peso,
                }
            )

    team_long = pd.DataFrame(registros_team)

    if team_long.empty:
        team_long = pd.DataFrame(
            columns=[
                "codigo",
                "partido",
                "gf",
                "ga",
                "puntos",
                "win",
                "draw",
                "loss",
                "peso",
            ]
        )

    team_long = team_long[team_long["codigo"].isin(codigos_objetivo)].copy()

    def promedio_ponderado(x, valor):
        pesos = x["peso"].sum()

        if pesos == 0:
            return np.nan

        return (x[valor] * x["peso"]).sum() / pesos

    stats = []

    for codigo, g in team_long.groupby("codigo"):
        stats.append(
            {
                "codigo": codigo,
                "partidos_recientes": len(g),
                "gf_prom_pond": promedio_ponderado(g, "gf"),
                "ga_prom_pond": promedio_ponderado(g, "ga"),
                "puntos_prom_pond": promedio_ponderado(g, "puntos"),
                "win_rate_pond": promedio_ponderado(g, "win"),
                "peso_total": g["peso"].sum(),
            }
        )

    stats_df = pd.DataFrame(stats)

    stats_dict = stats_df.set_index("codigo").to_dict("index") if not stats_df.empty else {}

    global_gf = team_long["gf"].mean() if len(team_long) else 1.35
    global_ga = team_long["ga"].mean() if len(team_long) else 1.35

    if pd.isna(global_gf) or global_gf <= 0:
        global_gf = 1.35

    if pd.isna(global_ga) or global_ga <= 0:
        global_ga = 1.35

    print("Selecciones con estadísticas recientes:", len(stats_dict))
    print("Promedio global goles a favor:", round(global_gf, 3))
    print("Promedio global goles en contra:", round(global_ga, 3))

    return stats_dict, global_gf, global_ga


def parsear_marcador_estimado(marcador):
    """
    Convierte marcador estimado tipo 1-0 en dos enteros.
    """
    marcador = texto_limpio(marcador).replace(" ", "")

    if "-" not in marcador:
        return 0, 0

    partes = marcador.split("-")

    if len(partes) != 2:
        return 0, 0

    try:
        return int(partes[0]), int(partes[1])
    except Exception:
        return 0, 0


def rating_equipo(codigo, ranking_dict):
    """
    Score auxiliar para desempatar por fuerza.
    """
    r = ranking_dict.get(codigo, {})

    elo = numero(r.get("elo", np.nan))
    puntos = numero(r.get("puntos_fifa", np.nan))
    ranking_fifa = numero(r.get("ranking_fifa", np.nan))

    score = 0

    if not pd.isna(elo):
        score += elo

    if not pd.isna(puntos):
        score += puntos

    if not pd.isna(ranking_fifa):
        score += max(0, 300 - ranking_fifa)

    return score


def predecir_match(
    equipo_a,
    codigo_a,
    equipo_b,
    codigo_b,
    ranking_dict,
    stats_dict,
    global_gf,
    global_ga,
    permitir_empate=True,
):
    """
    Predice un partido y define ganador si es eliminatoria.
    """
    resultado = predecir_partido(
        equipo_a=equipo_a,
        codigo_a=codigo_a,
        equipo_b=equipo_b,
        codigo_b=codigo_b,
        ranking_dict=ranking_dict,
        stats_dict=stats_dict,
        global_gf=global_gf,
        global_ga=global_ga,
    )

    goles_a, goles_b = parsear_marcador_estimado(resultado["marcador_estimado"])

    if permitir_empate and goles_a == goles_b:
        return resultado, "Empate", "", "", ""

    if goles_a > goles_b:
        return resultado, equipo_a, codigo_a, equipo_b, codigo_b

    if goles_b > goles_a:
        return resultado, equipo_b, codigo_b, equipo_a, codigo_a

    # Eliminatoria con marcador estimado empatado.
    # Se desempata usando probabilidad directa sin empate.
    if resultado["prob_a"] > resultado["prob_b"]:
        return resultado, equipo_a, codigo_a, equipo_b, codigo_b

    if resultado["prob_b"] > resultado["prob_a"]:
        return resultado, equipo_b, codigo_b, equipo_a, codigo_a

    # Último desempate por rating.
    if rating_equipo(codigo_a, ranking_dict) >= rating_equipo(codigo_b, ranking_dict):
        return resultado, equipo_a, codigo_a, equipo_b, codigo_b

    return resultado, equipo_b, codigo_b, equipo_a, codigo_a


def crear_registro_partido(
    fase,
    match_id,
    fecha,
    grupo,
    equipo_a,
    codigo_a,
    equipo_b,
    codigo_b,
    resultado,
    ganador_nombre,
    ganador_codigo,
    perdedor_nombre,
    perdedor_codigo,
    notas="",
):
    """
    Crea registro estándar para fact_prediccion_completa_2026.
    """
    goles_a, goles_b = parsear_marcador_estimado(resultado["marcador_estimado"])

    return {
        "run_id": RUN_ID,
        "fecha_hora_ejecucion": FECHA_HORA_EJECUCION,
        "escenario": ESCENARIO,
        "usa_resultados_reales_mundial": USA_RESULTADOS_REALES_MUNDIAL,
        "fase": fase,
        "orden_fase": orden_fase(fase),
        "match_id": match_id,
        "fecha": fecha,
        "grupo": grupo,
        "equipo_a": equipo_a,
        "codigo_a": codigo_a,
        "equipo_b": equipo_b,
        "codigo_b": codigo_b,
        "goles_estimados_a": goles_a,
        "goles_estimados_b": goles_b,
        "marcador_estimado": resultado["marcador_estimado"],
        "prob_a": round(resultado["prob_a"], 4),
        "prob_empate": round(resultado["prob_empate"], 4),
        "prob_b": round(resultado["prob_b"], 4),
        "favorito": resultado["favorito"],
        "ganador_predicho": ganador_nombre,
        "codigo_ganador_predicho": ganador_codigo,
        "perdedor_predicho": perdedor_nombre,
        "codigo_perdedor_predicho": perdedor_codigo,
        "confianza": resultado["confianza"],
        "tipo_prediccion": "simulacion_base",
        "modelo": MODELO_NOMBRE,
        "version_modelo": MODEL_VERSION,
        "notas": notas,
    }


def extraer_partidos_grupo(calendario):
    """
    Toma del calendario únicamente partidos de fase de grupos con equipos definidos.
    Ignora resultados reales aunque existan.
    """
    df = calendario.copy()
    df["fase_norm"] = df["fase"].apply(fase_normalizada)
    df["match_id_limpio"] = df["match_id"].apply(id_limpio)
    df["fecha_dt"] = df["fecha"].apply(fecha_yyyy_mm_dd)

    partidos = df[
        (df["fase_norm"] == "Fase de grupos")
        & df["grupo"].astype(str).str.strip().str.upper().isin(GROUPS)
    ].copy()

    partidos["codigo_a"] = partidos["codigo_a"].astype(str).str.strip().str.upper()
    partidos["codigo_b"] = partidos["codigo_b"].astype(str).str.strip().str.upper()

    partidos = partidos[
        partidos.apply(lambda r: equipo_concreto(r["equipo_a"], r["codigo_a"]), axis=1)
        & partidos.apply(lambda r: equipo_concreto(r["equipo_b"], r["codigo_b"]), axis=1)
    ].copy()

    partidos = partidos.sort_values(
        ["grupo", "fecha_dt", "match_id_limpio"],
        ascending=[True, True, True],
    )

    print("Partidos de fase de grupos para simular:", len(partidos))

    return partidos


def inicializar_tabla_grupos(partidos_grupo):
    """
    Inicializa standings por grupo/equipo desde los partidos de grupo.
    """
    equipos = {}

    for _, row in partidos_grupo.iterrows():
        grupo = texto_limpio(row["grupo"]).upper()

        for lado in ["a", "b"]:
            codigo = texto_limpio(row[f"codigo_{lado}"]).upper()
            equipo = texto_limpio(row[f"equipo_{lado}"])

            if not equipo_concreto(equipo, codigo):
                continue

            key = (grupo, codigo)

            if key not in equipos:
                equipos[key] = {
                    "grupo": grupo,
                    "seleccion": equipo,
                    "codigo": codigo,
                    "pj": 0,
                    "pg": 0,
                    "pe": 0,
                    "pp": 0,
                    "gf": 0,
                    "gc": 0,
                    "dg": 0,
                    "pts": 0,
                }

    return equipos


def actualizar_standing(tabla, grupo, codigo, gf, gc):
    """
    Actualiza estadísticas de un equipo en la tabla de grupos.
    """
    key = (grupo, codigo)

    if key not in tabla:
        return

    tabla[key]["pj"] += 1
    tabla[key]["gf"] += gf
    tabla[key]["gc"] += gc
    tabla[key]["dg"] = tabla[key]["gf"] - tabla[key]["gc"]

    if gf > gc:
        tabla[key]["pg"] += 1
        tabla[key]["pts"] += 3
    elif gf == gc:
        tabla[key]["pe"] += 1
        tabla[key]["pts"] += 1
    else:
        tabla[key]["pp"] += 1


def simular_fase_grupos(
    partidos_grupo,
    ranking_dict,
    stats_dict,
    global_gf,
    global_ga,
):
    """
    Simula todos los partidos de fase de grupos.
    """
    tabla = inicializar_tabla_grupos(partidos_grupo)
    registros_partidos = []

    for _, row in partidos_grupo.iterrows():
        grupo = texto_limpio(row["grupo"]).upper()
        match_id = id_limpio(row["match_id"])
        fecha = texto_limpio(row.get("fecha", ""))

        equipo_a = texto_limpio(row["equipo_a"])
        equipo_b = texto_limpio(row["equipo_b"])
        codigo_a = texto_limpio(row["codigo_a"]).upper()
        codigo_b = texto_limpio(row["codigo_b"]).upper()

        resultado, ganador, codigo_ganador, perdedor, codigo_perdedor = predecir_match(
            equipo_a=equipo_a,
            codigo_a=codigo_a,
            equipo_b=equipo_b,
            codigo_b=codigo_b,
            ranking_dict=ranking_dict,
            stats_dict=stats_dict,
            global_gf=global_gf,
            global_ga=global_ga,
            permitir_empate=True,
        )

        goles_a, goles_b = parsear_marcador_estimado(resultado["marcador_estimado"])

        actualizar_standing(tabla, grupo, codigo_a, goles_a, goles_b)
        actualizar_standing(tabla, grupo, codigo_b, goles_b, goles_a)

        registros_partidos.append(
            crear_registro_partido(
                fase="Fase de grupos",
                match_id=match_id,
                fecha=fecha,
                grupo=grupo,
                equipo_a=equipo_a,
                codigo_a=codigo_a,
                equipo_b=equipo_b,
                codigo_b=codigo_b,
                resultado=resultado,
                ganador_nombre=ganador,
                ganador_codigo=codigo_ganador,
                perdedor_nombre=perdedor,
                perdedor_codigo=codigo_perdedor,
                notas="Predicción de fase de grupos. No usa resultados reales del Mundial.",
            )
        )

    tabla_df = pd.DataFrame(tabla.values())

    if tabla_df.empty:
        return pd.DataFrame(columns=COLUMNAS_PARTIDOS), pd.DataFrame(columns=COLUMNAS_GRUPOS)

    tabla_df["ranking_aux"] = tabla_df["codigo"].apply(
        lambda c: rating_equipo(c, ranking_dict)
    )

    tabla_df = tabla_df.sort_values(
        ["grupo", "pts", "dg", "gf", "ranking_aux"],
        ascending=[True, False, False, False, False],
    ).copy()

    tabla_df["posicion_grupo"] = tabla_df.groupby("grupo").cumcount() + 1

    tabla_df["clasifica"] = np.where(tabla_df["posicion_grupo"] <= 2, "Sí", "No")
    tabla_df["tipo_clasificacion"] = np.where(
        tabla_df["posicion_grupo"] == 1,
        "Primero de grupo",
        np.where(tabla_df["posicion_grupo"] == 2, "Segundo de grupo", "No clasifica"),
    )

    terceros = tabla_df[tabla_df["posicion_grupo"] == 3].copy()
    terceros = terceros.sort_values(
        ["pts", "dg", "gf", "ranking_aux"],
        ascending=[False, False, False, False],
    ).copy()

    mejores_terceros_codigos = terceros.head(8)["codigo"].tolist()

    tabla_df.loc[
        tabla_df["codigo"].isin(mejores_terceros_codigos),
        "clasifica",
    ] = "Sí"

    tabla_df.loc[
        tabla_df["codigo"].isin(mejores_terceros_codigos),
        "tipo_clasificacion",
    ] = "Mejor tercero"

    tabla_salida = tabla_df.copy()

    tabla_salida.insert(0, "run_id", RUN_ID)
    tabla_salida.insert(1, "fecha_hora_ejecucion", FECHA_HORA_EJECUCION)
    tabla_salida.insert(2, "escenario", ESCENARIO)
    tabla_salida["version_modelo"] = MODEL_VERSION

    tabla_salida = tabla_salida[
        [
            "run_id",
            "fecha_hora_ejecucion",
            "escenario",
            "grupo",
            "posicion_grupo",
            "seleccion",
            "codigo",
            "pj",
            "pg",
            "pe",
            "pp",
            "gf",
            "gc",
            "dg",
            "pts",
            "clasifica",
            "tipo_clasificacion",
            "version_modelo",
        ]
    ].copy()

    partidos_df = pd.DataFrame(registros_partidos)

    if partidos_df.empty:
        partidos_df = pd.DataFrame(columns=COLUMNAS_PARTIDOS)
    else:
        partidos_df = partidos_df[COLUMNAS_PARTIDOS]

    print("Partidos de grupo simulados:", len(partidos_df))
    print("Clasificados simulados:", (tabla_salida["clasifica"] == "Sí").sum())

    return partidos_df, tabla_salida


def lista_clasificados(tabla_grupos):
    """
    Devuelve clasificados ordenados por posición, puntos y diferencia.
    """
    clasificados = tabla_grupos[tabla_grupos["clasifica"] == "Sí"].copy()

    tipo_orden = {
        "Primero de grupo": 1,
        "Segundo de grupo": 2,
        "Mejor tercero": 3,
    }

    clasificados["tipo_orden"] = clasificados["tipo_clasificacion"].map(tipo_orden).fillna(9)

    clasificados = clasificados.sort_values(
        ["tipo_orden", "pts", "dg", "gf"],
        ascending=[True, False, False, False],
    ).copy()

    return [
        {
            "equipo": row["seleccion"],
            "codigo": row["codigo"],
            "grupo": row["grupo"],
            "posicion_grupo": row["posicion_grupo"],
            "tipo_clasificacion": row["tipo_clasificacion"],
        }
        for _, row in clasificados.iterrows()
    ]


def fallback_ronda_32(tabla_grupos):
    """
    Crea emparejamientos simulados si el calendario no trae slots resolubles.
    """
    clasificados = lista_clasificados(tabla_grupos)

    if len(clasificados) < 32:
        raise ValueError(
            f"No hay 32 clasificados para armar ronda de 32. Hay: {len(clasificados)}"
        )

    clasificados = clasificados[:32]
    partidos = []

    for i in range(16):
        equipo_a = clasificados[i]
        equipo_b = clasificados[31 - i]

        partidos.append(
            {
                "match_id": f"R32_{i + 1:02d}",
                "fecha": "",
                "grupo": "",
                "equipo_a_resuelto": equipo_a,
                "equipo_b_resuelto": equipo_b,
                "notas": "Cruce generado por siembra simulada 1-vs-32. No usa resultados reales.",
            }
        )

    return partidos


def fallback_emparejar_lista(equipos, fase_objetivo):
    """
    Fallback para emparejar ganadores de la ronda anterior.
    """
    partidos = []

    for i in range(0, len(equipos), 2):
        if i + 1 >= len(equipos):
            break

        partidos.append(
            {
                "match_id": f"{fase_objetivo.replace(' ', '_').upper()}_{(i // 2) + 1:02d}",
                "fecha": "",
                "grupo": "",
                "equipo_a_resuelto": equipos[i],
                "equipo_b_resuelto": equipos[i + 1],
                "notas": "Cruce generado por ganadores previos. No usa resultados reales.",
            }
        )

    return partidos


def simular_eliminatoria(
    partidos,
    fase,
    ranking_dict,
    stats_dict,
    global_gf,
    global_ga,
):
    """
    Simula una fase de eliminación directa.
    """
    registros = []
    ganadores_fase = []
    perdedores_fase = []

    for partido in partidos:
        match_id = id_limpio(partido["match_id"])
        fecha = texto_limpio(partido.get("fecha", ""))
        grupo = texto_limpio(partido.get("grupo", ""))
        notas = texto_limpio(partido.get("notas", ""))

        equipo_a_info = partido["equipo_a_resuelto"]
        equipo_b_info = partido["equipo_b_resuelto"]

        equipo_a = equipo_a_info["equipo"]
        codigo_a = equipo_a_info["codigo"]
        equipo_b = equipo_b_info["equipo"]
        codigo_b = equipo_b_info["codigo"]

        resultado, ganador, codigo_ganador, perdedor, codigo_perdedor = predecir_match(
            equipo_a=equipo_a,
            codigo_a=codigo_a,
            equipo_b=equipo_b,
            codigo_b=codigo_b,
            ranking_dict=ranking_dict,
            stats_dict=stats_dict,
            global_gf=global_gf,
            global_ga=global_ga,
            permitir_empate=False,
        )

        ganador_info = {
            "equipo": ganador,
            "codigo": codigo_ganador,
            "grupo": "",
            "posicion_grupo": "",
            "tipo_clasificacion": "",
        }

        perdedor_info = {
            "equipo": perdedor,
            "codigo": codigo_perdedor,
            "grupo": "",
            "posicion_grupo": "",
            "tipo_clasificacion": "",
        }

        ganadores_fase.append(ganador_info)
        perdedores_fase.append(perdedor_info)

        registros.append(
            crear_registro_partido(
                fase=fase,
                match_id=match_id,
                fecha=fecha,
                grupo=grupo,
                equipo_a=equipo_a,
                codigo_a=codigo_a,
                equipo_b=equipo_b,
                codigo_b=codigo_b,
                resultado=resultado,
                ganador_nombre=ganador,
                ganador_codigo=codigo_ganador,
                perdedor_nombre=perdedor,
                perdedor_codigo=codigo_perdedor,
                notas=notas,
            )
        )

    df = pd.DataFrame(registros)

    if df.empty:
        df = pd.DataFrame(columns=COLUMNAS_PARTIDOS)
    else:
        df = df[COLUMNAS_PARTIDOS]

    print(f"Partidos simulados - {fase}:", len(df))

    return df, ganadores_fase, perdedores_fase


def actualizar_camino_inicial(tabla_grupos):
    """
    Crea estructura inicial de camino por selección.
    """
    camino = {}

    for _, row in tabla_grupos.iterrows():
        codigo = row["codigo"]

        camino[codigo] = {
            "run_id": RUN_ID,
            "fecha_hora_ejecucion": FECHA_HORA_EJECUCION,
            "escenario": ESCENARIO,
            "seleccion": row["seleccion"],
            "codigo": codigo,
            "grupo": row["grupo"],
            "posicion_grupo_predicha": row["posicion_grupo"],
            "clasifica_grupos": row["clasifica"],
            "tipo_clasificacion": row["tipo_clasificacion"],
            "ronda_alcanzada": "Fase de grupos" if row["clasifica"] == "No" else "Clasificado a Ronda de 32",
            "eliminado_por": "",
            "codigo_eliminado_por": "",
            "campeon_predicho": "No",
            "subcampeon_predicho": "No",
            "tercer_lugar_predicho": "No",
            "cuarto_lugar_predicho": "No",
            "version_modelo": MODEL_VERSION,
        }

    return camino


def actualizar_camino_por_fase(camino, partidos_df, fase):
    """
    Actualiza camino de selecciones usando ganadores/perdedores de una fase.
    """
    if partidos_df.empty:
        return camino

    for _, row in partidos_df.iterrows():
        ganador_codigo = texto_limpio(row["codigo_ganador_predicho"]).upper()
        perdedor_codigo = texto_limpio(row["codigo_perdedor_predicho"]).upper()

        ganador_nombre = texto_limpio(row["ganador_predicho"])

        if ganador_codigo in camino:
            if fase == "Final":
                camino[ganador_codigo]["ronda_alcanzada"] = "Campeón"
                camino[ganador_codigo]["campeon_predicho"] = "Sí"
            elif fase == "Tercer lugar":
                camino[ganador_codigo]["ronda_alcanzada"] = "Tercer lugar"
                camino[ganador_codigo]["tercer_lugar_predicho"] = "Sí"
            else:
                camino[ganador_codigo]["ronda_alcanzada"] = f"Avanza desde {fase}"

        if perdedor_codigo in camino:
            if fase == "Final":
                camino[perdedor_codigo]["ronda_alcanzada"] = "Subcampeón"
                camino[perdedor_codigo]["subcampeon_predicho"] = "Sí"
            elif fase == "Tercer lugar":
                camino[perdedor_codigo]["ronda_alcanzada"] = "Cuarto lugar"
                camino[perdedor_codigo]["cuarto_lugar_predicho"] = "Sí"
            else:
                camino[perdedor_codigo]["ronda_alcanzada"] = f"Eliminado en {fase}"
                camino[perdedor_codigo]["eliminado_por"] = ganador_nombre
                camino[perdedor_codigo]["codigo_eliminado_por"] = ganador_codigo

    return camino


def generar_prediccion_completa(
    calendario,
    ranking_dict,
    stats_dict,
    global_gf,
    global_ga,
):
    """
    Genera simulación completa del Mundial.
    """
    partidos_grupo = extraer_partidos_grupo(calendario)

    partidos_grupo_df, tabla_grupos_df = simular_fase_grupos(
        partidos_grupo=partidos_grupo,
        ranking_dict=ranking_dict,
        stats_dict=stats_dict,
        global_gf=global_gf,
        global_ga=global_ga,
    )

    camino = actualizar_camino_inicial(tabla_grupos_df)
    todos_partidos = [partidos_grupo_df]

    # Ronda de 32.
    partidos_r32 = fallback_ronda_32(tabla_grupos_df)

    df_r32, ganadores_r32, _ = simular_eliminatoria(
        partidos=partidos_r32,
        fase="Ronda de 32",
        ranking_dict=ranking_dict,
        stats_dict=stats_dict,
        global_gf=global_gf,
        global_ga=global_ga,
    )

    todos_partidos.append(df_r32)
    camino = actualizar_camino_por_fase(camino, df_r32, "Ronda de 32")

    # Octavos.
    partidos_octavos = fallback_emparejar_lista(ganadores_r32, "Octavos")

    df_octavos, ganadores_octavos, _ = simular_eliminatoria(
        partidos=partidos_octavos,
        fase="Octavos",
        ranking_dict=ranking_dict,
        stats_dict=stats_dict,
        global_gf=global_gf,
        global_ga=global_ga,
    )

    todos_partidos.append(df_octavos)
    camino = actualizar_camino_por_fase(camino, df_octavos, "Octavos")

    # Cuartos.
    partidos_cuartos = fallback_emparejar_lista(ganadores_octavos, "Cuartos")

    df_cuartos, ganadores_cuartos, _ = simular_eliminatoria(
        partidos=partidos_cuartos,
        fase="Cuartos",
        ranking_dict=ranking_dict,
        stats_dict=stats_dict,
        global_gf=global_gf,
        global_ga=global_ga,
    )

    todos_partidos.append(df_cuartos)
    camino = actualizar_camino_por_fase(camino, df_cuartos, "Cuartos")

    # Semifinal.
    partidos_semifinal = fallback_emparejar_lista(ganadores_cuartos, "Semifinal")

    df_semifinal, ganadores_semifinal, perdedores_semifinal = simular_eliminatoria(
        partidos=partidos_semifinal,
        fase="Semifinal",
        ranking_dict=ranking_dict,
        stats_dict=stats_dict,
        global_gf=global_gf,
        global_ga=global_ga,
    )

    todos_partidos.append(df_semifinal)
    camino = actualizar_camino_por_fase(camino, df_semifinal, "Semifinal")

    # Tercer lugar.
    partidos_tercero = fallback_emparejar_lista(perdedores_semifinal, "Tercer lugar")

    df_tercero, _, _ = simular_eliminatoria(
        partidos=partidos_tercero[:1],
        fase="Tercer lugar",
        ranking_dict=ranking_dict,
        stats_dict=stats_dict,
        global_gf=global_gf,
        global_ga=global_ga,
    )

    todos_partidos.append(df_tercero)
    camino = actualizar_camino_por_fase(camino, df_tercero, "Tercer lugar")

    # Final.
    partidos_final = fallback_emparejar_lista(ganadores_semifinal, "Final")

    df_final, _, _ = simular_eliminatoria(
        partidos=partidos_final[:1],
        fase="Final",
        ranking_dict=ranking_dict,
        stats_dict=stats_dict,
        global_gf=global_gf,
        global_ga=global_ga,
    )

    todos_partidos.append(df_final)
    camino = actualizar_camino_por_fase(camino, df_final, "Final")

    prediccion_completa_df = pd.concat(
        todos_partidos,
        ignore_index=True,
        sort=False,
    )

    if prediccion_completa_df.empty:
        prediccion_completa_df = pd.DataFrame(columns=COLUMNAS_PARTIDOS)
    else:
        prediccion_completa_df = prediccion_completa_df[COLUMNAS_PARTIDOS]

    camino_df = pd.DataFrame(camino.values())

    if camino_df.empty:
        camino_df = pd.DataFrame(columns=COLUMNAS_CAMINO)
    else:
        camino_df = camino_df[COLUMNAS_CAMINO]

    print("Total partidos simulados:", len(prediccion_completa_df))
    print("Filas tabla grupos:", len(tabla_grupos_df))
    print("Filas camino predicho:", len(camino_df))

    return prediccion_completa_df, tabla_grupos_df, camino_df


def crear_log_ejecucion(
    prediccion_completa_df,
    tabla_grupos_df,
    camino_df,
    estado="OK",
    mensaje="Predicción completa base generada correctamente",
):
    """
    Crea log de ejecución.
    """
    return pd.DataFrame(
        [
            {
                "run_id": RUN_ID,
                "fecha_hora_ejecucion": FECHA_HORA_EJECUCION,
                "proyecto": "mundial-2026-predicciones",
                "script": "03_prediccion_completa_2026.py",
                "origen": ENVIRONMENT,
                "estado": estado,
                "filas_predicciones": len(prediccion_completa_df),
                "filas_snapshot": "",
                "tabla_predicciones": TAB_PREDICCION_COMPLETA,
                "tabla_snapshot": "",
                "version_modelo": MODEL_VERSION,
                "mensaje": (
                    f"{mensaje}. "
                    f"Partidos simulados: {len(prediccion_completa_df)}. "
                    f"Tabla grupos: {len(tabla_grupos_df)}. "
                    f"Camino predicho: {len(camino_df)}."
                ),
            }
        ]
    )


def main():
    """
    Ejecución principal.
    """
    print("====================================================")
    print("Predicción completa base Mundial 2026")
    print(f"Run ID: {RUN_ID}")
    print(f"Fecha/hora ejecución: {FECHA_HORA_EJECUCION}")
    print("IMPORTANTE: No usa resultados reales del Mundial actual.")
    print("====================================================")

    calendario, ranking, resultados = cargar_tablas()

    validar_columnas(calendario, ranking, resultados)

    _, ranking_dict, codigos_objetivo = preparar_ranking(ranking)

    resultados_modelo = preparar_resultados_modelo(
        resultados=resultados,
        codigos_objetivo=codigos_objetivo,
    )

    stats_dict, global_gf, global_ga = calcular_estadisticas_seleccion(
        resultados=resultados_modelo,
        codigos_objetivo=codigos_objetivo,
    )

    prediccion_completa_df, tabla_grupos_df, camino_df = generar_prediccion_completa(
        calendario=calendario,
        ranking_dict=ranking_dict,
        stats_dict=stats_dict,
        global_gf=global_gf,
        global_ga=global_ga,
    )

    escribir_df_en_hoja(prediccion_completa_df, TAB_PREDICCION_COMPLETA)
    escribir_df_en_hoja(tabla_grupos_df, TAB_TABLA_GRUPOS_PREDICHA)
    escribir_df_en_hoja(camino_df, TAB_CAMINO_PREDICHO)

    log_df = crear_log_ejecucion(
        prediccion_completa_df=prediccion_completa_df,
        tabla_grupos_df=tabla_grupos_df,
        camino_df=camino_df,
    )

    append_df_en_hoja(log_df, TAB_LOGS)

    print("====================================================")
    print("Predicción completa base terminada.")
    print(f"Tabla escrita: {TAB_PREDICCION_COMPLETA}")
    print(f"Tabla escrita: {TAB_TABLA_GRUPOS_PREDICHA}")
    print(f"Tabla escrita: {TAB_CAMINO_PREDICHO}")
    print(f"Partidos simulados: {len(prediccion_completa_df)}")
    print("====================================================")


if __name__ == "__main__":
    main()
