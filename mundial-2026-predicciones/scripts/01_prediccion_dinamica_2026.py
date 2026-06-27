"""
Predicción dinámica Mundial 2026.

Este script:
1. Lee datos desde Google Sheets.
2. Usa resultados recientes + partidos jugados del calendario 2026.
3. Genera predicciones dinámicas solo para partidos pendientes/programados.
4. Sobrescribe fact_predicciones_2026.
5. Agrega histórico en fact_predicciones_snapshot_2026.

No contiene credenciales.
Las credenciales se leen desde variables de entorno o GitHub Secrets.
"""

from datetime import datetime

import numpy as np
import pandas as pd

from src.config import (
    TAB_CALENDARIO,
    TAB_RANKING,
    TAB_RESULTADOS,
    TAB_EQUIVALENCIAS,
    TAB_SALIDA,
    TAB_SNAPSHOT,
    MODEL_VERSION,
    MODELO_NOMBRE,
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
    detectar_estado_partido,
)

from src.modelo_poisson import predecir_partido


INCLUIR_PARTIDOS_JUGADOS = False
HALF_LIFE_DIAS = 365

RUN_ID = datetime.now().strftime("run_%Y%m%d_%H%M%S")
FECHA_HORA_EJECUCION = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def cargar_tablas():
    """
    Lee las tablas necesarias desde Google Sheets.
    """
    calendario = limpiar_columnas(leer_hoja(TAB_CALENDARIO))
    ranking = limpiar_columnas(leer_hoja(TAB_RANKING))
    resultados = limpiar_columnas(leer_hoja(TAB_RESULTADOS))

    try:
        equivalencias = limpiar_columnas(leer_hoja(TAB_EQUIVALENCIAS))
    except Exception:
        equivalencias = pd.DataFrame()

    print("Tablas cargadas:")
    print("Calendario:", calendario.shape)
    print("Ranking:", ranking.shape)
    print("Resultados recientes:", resultados.shape)
    print("Equivalencias:", equivalencias.shape)

    return calendario, ranking, resultados, equivalencias


def validar_columnas(calendario, ranking, resultados):
    """
    Valida que existan las columnas mínimas requeridas.
    """
    columnas_calendario_necesarias = [
        "match_id",
        "fecha",
        "fase",
        "grupo",
        "equipo_a",
        "codigo_a",
        "equipo_b",
        "codigo_b",
    ]

    columnas_ranking_necesarias = [
        "codigo",
        "seleccion",
        "ranking_fifa",
        "puntos_fifa",
        "elo",
        "confederacion",
    ]

    columnas_resultados_necesarias = [
        "fecha",
        "codigo_local",
        "codigo_visitante",
        "goles_local",
        "goles_visitante",
    ]

    for col in columnas_calendario_necesarias:
        if col not in calendario.columns:
            raise ValueError(f"Falta columna en calendario: {col}")

    for col in columnas_ranking_necesarias:
        if col not in ranking.columns:
            raise ValueError(f"Falta columna en dim_ranking_equipos: {col}")

    for col in columnas_resultados_necesarias:
        if col not in resultados.columns:
            raise ValueError(f"Falta columna en fact_resultados_recientes: {col}")


def preparar_ranking(ranking):
    """
    Limpia ranking FIFA/Elo y crea diccionario de fuerza por selección.
    """
    ranking = ranking.copy()

    ranking["codigo"] = ranking["codigo"].astype(str).str.strip().str.upper()
    ranking["ranking_fifa"] = ranking["ranking_fifa"].apply(numero)
    ranking["puntos_fifa"] = ranking["puntos_fifa"].apply(numero)
    ranking["elo"] = ranking["elo"].apply(numero)

    ranking = ranking.drop_duplicates(subset=["codigo"], keep="first")

    ranking_dict = ranking.set_index("codigo").to_dict("index")
    codigos_objetivo = set(ranking["codigo"].dropna().astype(str).str.upper())

    print("Selecciones en ranking:", len(codigos_objetivo))

    return ranking, ranking_dict, codigos_objetivo


def extraer_partidos_jugados_calendario(calendario_df, codigos_objetivo, fecha_actual):
    """
    Convierte partidos jugados del calendario 2026 al formato de resultados recientes.
    """
    registros = []

    for _, row in calendario_df.iterrows():
        estado = detectar_estado_partido(row)

        if estado != "Jugado":
            continue

        match_id = texto_limpio(row.get("match_id", ""))
        fecha = fecha_yyyy_mm_dd(row.get("fecha", ""))

        equipo_a = texto_limpio(row.get("equipo_a", ""))
        equipo_b = texto_limpio(row.get("equipo_b", ""))
        codigo_a = texto_limpio(row.get("codigo_a", "")).upper()
        codigo_b = texto_limpio(row.get("codigo_b", "")).upper()

        goles_a = entero(row.get("goles_a", ""))
        goles_b = entero(row.get("goles_b", ""))

        if pd.isna(fecha):
            continue

        if fecha > fecha_actual:
            continue

        if not equipo_valido(equipo_a) or not equipo_valido(equipo_b):
            continue

        if not codigo_valido(codigo_a) or not codigo_valido(codigo_b):
            continue

        if codigo_a not in codigos_objetivo or codigo_b not in codigos_objetivo:
            continue

        if pd.isna(goles_a) or pd.isna(goles_b):
            continue

        registros.append(
            {
                "match_id_reciente": f"WC2026_{match_id}",
                "fecha": fecha,
                "equipo_local": equipo_a,
                "codigo_local": codigo_a,
                "equipo_visitante": equipo_b,
                "codigo_visitante": codigo_b,
                "goles_local": goles_a,
                "goles_visitante": goles_b,
                "torneo": "FIFA World Cup 2026",
                "tipo_partido": "Oficial",
                "neutral": True,
                "fuente": "Calendario Mundial 2026 - Data Matrix",
                "notas": "Partido jugado tomado automáticamente desde el calendario",
                "origen_resultado": "calendario_2026",
            }
        )

    return pd.DataFrame(registros)


def crear_clave_resultado(row):
    """
    Crea una clave para evitar duplicados entre fact_resultados_recientes y calendario.
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


def preparar_resultados_modelo(resultados, calendario, codigos_objetivo, fecha_actual):
    """
    Combina resultados recientes históricos con partidos jugados del Mundial 2026.
    """
    resultados_base = resultados.copy()
    resultados_base["origen_resultado"] = "fact_resultados_recientes"

    resultados_calendario = extraer_partidos_jugados_calendario(
        calendario,
        codigos_objetivo,
        fecha_actual,
    )

    print("Partidos jugados del calendario detectados:", len(resultados_calendario))

    resultados = pd.concat(
        [resultados_base, resultados_calendario],
        ignore_index=True,
        sort=False,
    )

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

    resultados = resultados[resultados["fecha"] <= fecha_actual].copy()

    resultados["clave_resultado"] = resultados.apply(crear_clave_resultado, axis=1)

    resultados["prioridad_origen"] = np.where(
        resultados["origen_resultado"] == "calendario_2026",
        0,
        1,
    )

    resultados = (
        resultados
        .sort_values(["clave_resultado", "prioridad_origen"])
        .drop_duplicates(subset=["clave_resultado"], keep="first")
        .drop(columns=["clave_resultado", "prioridad_origen"])
        .copy()
    )

    dias_antiguedad = (fecha_actual - resultados["fecha"]).dt.days.clip(lower=0)
    resultados["peso_recencia"] = 0.5 ** (dias_antiguedad / HALF_LIFE_DIAS)

    print("Resultados recientes válidos para el modelo:", len(resultados))
    print(
        "Incluye partidos jugados del Mundial 2026:",
        (resultados["origen_resultado"] == "calendario_2026").sum(),
    )

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


def generar_predicciones(
    calendario,
    ranking_dict,
    stats_dict,
    global_gf,
    global_ga,
    codigos_objetivo,
    fecha_actual,
):
    """
    Genera predicciones dinámicas solo para partidos pendientes/programados.
    """
    predicciones = []
    fecha_prediccion = fecha_actual.strftime("%Y-%m-%d")

    for _, row in calendario.iterrows():
        match_id = texto_limpio(row.get("match_id", ""))
        fecha = texto_limpio(row.get("fecha", ""))
        fase = texto_limpio(row.get("fase", ""))
        grupo = texto_limpio(row.get("grupo", ""))

        equipo_a = texto_limpio(row.get("equipo_a", ""))
        equipo_b = texto_limpio(row.get("equipo_b", ""))
        codigo_a = texto_limpio(row.get("codigo_a", "")).upper()
        codigo_b = texto_limpio(row.get("codigo_b", "")).upper()

        estado_partido = detectar_estado_partido(row)

        if not equipo_valido(equipo_a) or not equipo_valido(equipo_b):
            continue

        if not codigo_valido(codigo_a) or not codigo_valido(codigo_b):
            continue

        if codigo_a not in codigos_objetivo or codigo_b not in codigos_objetivo:
            continue

        if not INCLUIR_PARTIDOS_JUGADOS and estado_partido == "Jugado":
            continue

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

        notas = ""

        if codigo_a not in stats_dict:
            notas += f"Sin suficientes resultados recientes para {codigo_a}. "

        if codigo_b not in stats_dict:
            notas += f"Sin suficientes resultados recientes para {codigo_b}. "

        predicciones.append(
            {
                "match_id": match_id,
                "fecha": fecha,
                "fase": fase,
                "grupo": grupo,
                "equipo_a": equipo_a,
                "codigo_a": codigo_a,
                "equipo_b": equipo_b,
                "codigo_b": codigo_b,
                "goles_esperados_a": round(resultado["goles_esperados_a"], 3),
                "goles_esperados_b": round(resultado["goles_esperados_b"], 3),
                "prob_a": round(resultado["prob_a"], 4),
                "prob_empate": round(resultado["prob_empate"], 4),
                "prob_b": round(resultado["prob_b"], 4),
                "favorito": resultado["favorito"],
                "prob_favorito": round(resultado["prob_favorito"], 4),
                "confianza": resultado["confianza"],
                "marcador_estimado": resultado["marcador_estimado"],
                "modelo": MODELO_NOMBRE,
                "version_modelo": MODEL_VERSION,
                "fecha_prediccion": fecha_prediccion,
                "estado_partido": estado_partido,
                "notas": notas.strip(),
            }
        )

    columnas_salida = [
        "match_id",
        "fecha",
        "fase",
        "grupo",
        "equipo_a",
        "codigo_a",
        "equipo_b",
        "codigo_b",
        "goles_esperados_a",
        "goles_esperados_b",
        "prob_a",
        "prob_empate",
        "prob_b",
        "favorito",
        "prob_favorito",
        "confianza",
        "marcador_estimado",
        "modelo",
        "version_modelo",
        "fecha_prediccion",
        "estado_partido",
        "notas",
    ]

    pred_df = pd.DataFrame(predicciones)

    if pred_df.empty:
        pred_df = pd.DataFrame(columns=columnas_salida)
    else:
        pred_df = pred_df[columnas_salida]

    return pred_df


def validar_predicciones(pred_df):
    """
    Valida calidad básica de la salida.
    """
    print("Predicciones dinámicas generadas:", len(pred_df))

    if pred_df.empty:
        return pred_df

    pred_df["suma_probs"] = (
        pred_df["prob_a"]
        + pred_df["prob_empate"]
        + pred_df["prob_b"]
    )

    min_prob = pred_df["suma_probs"].min()
    max_prob = pred_df["suma_probs"].max()

    print("Validación suma probabilidades:")
    print("Mín:", round(min_prob, 4), "Máx:", round(max_prob, 4))

    pred_df = pred_df.drop(columns=["suma_probs"])

    duplicados = pred_df["match_id"].duplicated().sum()
    print("Match IDs duplicados:", duplicados)

    if duplicados > 0:
        print("Advertencia: hay match_id duplicados en la salida.")

    return pred_df


def crear_snapshot(pred_df):
    """
    Crea snapshot histórico de la corrida actual.
    """
    snapshot_df = pred_df.copy()

    if not snapshot_df.empty:
        snapshot_df.insert(0, "run_id", RUN_ID)
        snapshot_df.insert(1, "fecha_hora_ejecucion", FECHA_HORA_EJECUCION)
        snapshot_df.insert(2, "tipo_prediccion", "dinamica")
        snapshot_df.insert(3, "tabla_origen", TAB_SALIDA)

    print("Filas para snapshot:", len(snapshot_df))

    return snapshot_df


def main():
    """
    Ejecución principal del pipeline.
    """
    print("====================================================")
    print("Predicción dinámica Mundial 2026")
    print(f"Run ID: {RUN_ID}")
    print(f"Fecha/hora ejecución: {FECHA_HORA_EJECUCION}")
    print("====================================================")

    fecha_actual = pd.Timestamp.today().normalize()

    calendario, ranking, resultados, _ = cargar_tablas()

    validar_columnas(calendario, ranking, resultados)

    _, ranking_dict, codigos_objetivo = preparar_ranking(ranking)

    resultados_modelo = preparar_resultados_modelo(
        resultados=resultados,
        calendario=calendario,
        codigos_objetivo=codigos_objetivo,
        fecha_actual=fecha_actual,
    )

    stats_dict, global_gf, global_ga = calcular_estadisticas_seleccion(
        resultados=resultados_modelo,
        codigos_objetivo=codigos_objetivo,
    )

    pred_df = generar_predicciones(
        calendario=calendario,
        ranking_dict=ranking_dict,
        stats_dict=stats_dict,
        global_gf=global_gf,
        global_ga=global_ga,
        codigos_objetivo=codigos_objetivo,
        fecha_actual=fecha_actual,
    )

    pred_df = validar_predicciones(pred_df)

    snapshot_df = crear_snapshot(pred_df)

    escribir_df_en_hoja(pred_df, TAB_SALIDA)
    append_df_en_hoja(snapshot_df, TAB_SNAPSHOT)

    print("====================================================")
    print("Proceso terminado.")
    print(f"Tabla dinámica escrita en: {TAB_SALIDA}")
    print(f"Snapshot agregado en: {TAB_SNAPSHOT}")
    print(f"Filas dinámicas generadas: {len(pred_df)}")
    print(f"Filas agregadas al snapshot: {len(snapshot_df)}")
    print("====================================================")


if __name__ == "__main__":
    main()
