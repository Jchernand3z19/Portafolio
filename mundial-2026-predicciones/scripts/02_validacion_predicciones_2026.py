"""
Validación de predicciones Mundial 2026.

Este script:
1. Lee el calendario del Mundial 2026 desde Google Sheets.
2. Lee el histórico de predicciones desde fact_predicciones_snapshot_2026.
3. Detecta partidos jugados con marcador real.
4. Busca la última predicción disponible para cada partido jugado.
5. Compara predicción vs resultado real.
6. Sobrescribe fact_validacion_predicciones_2026.
7. Registra la ejecución en _logs_mundial_2026.

No contiene credenciales.
Las credenciales se leen desde variables de entorno o GitHub Secrets.
"""

from datetime import datetime

import numpy as np
import pandas as pd

from src.config import (
    TAB_CALENDARIO,
    TAB_SNAPSHOT,
    TAB_VALIDACION,
    TAB_LOGS,
    MODEL_VERSION,
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
    entero,
    fecha_yyyy_mm_dd,
    codigo_valido,
    equipo_valido,
    detectar_estado_partido,
)


RUN_ID = datetime.now().strftime("run_validacion_%Y%m%d_%H%M%S")
FECHA_HORA_EJECUCION = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


COLUMNAS_VALIDACION = [
    "run_id_validacion",
    "fecha_hora_validacion",
    "match_id",
    "fecha",
    "fase",
    "grupo",
    "equipo_a",
    "codigo_a",
    "equipo_b",
    "codigo_b",
    "goles_a",
    "goles_b",
    "marcador_real",
    "resultado_real",
    "run_id_prediccion",
    "fecha_hora_prediccion",
    "fecha_prediccion",
    "favorito_predicho",
    "resultado_predicho",
    "marcador_estimado",
    "prob_a",
    "prob_empate",
    "prob_b",
    "prob_favorito",
    "confianza",
    "acerto_resultado",
    "acerto_marcador",
    "diferencia_goles_a",
    "diferencia_goles_b",
    "tiene_prediccion",
    "version_modelo",
    "tabla_origen_prediccion",
    "notas",
]


def cargar_tablas():
    """
    Lee calendario y snapshot desde Google Sheets.
    """
    calendario = limpiar_columnas(leer_hoja(TAB_CALENDARIO))

    try:
        snapshot = limpiar_columnas(leer_hoja(TAB_SNAPSHOT))
    except Exception as e:
        print(f"No se pudo leer {TAB_SNAPSHOT}. Se usará snapshot vacío.")
        print("Detalle:", str(e))
        snapshot = pd.DataFrame()

    print("Tablas cargadas:")
    print("Calendario:", calendario.shape)
    print("Snapshot:", snapshot.shape)

    return calendario, snapshot


def validar_columnas_calendario(calendario):
    """
    Valida columnas mínimas del calendario.
    """
    columnas_necesarias = [
        "match_id",
        "fecha",
        "fase",
        "grupo",
        "equipo_a",
        "codigo_a",
        "equipo_b",
        "codigo_b",
    ]

    for col in columnas_necesarias:
        if col not in calendario.columns:
            raise ValueError(f"Falta columna en calendario: {col}")


def obtener_resultado(goles_a, goles_b):
    """
    Devuelve el resultado del partido:
    - A
    - Empate
    - B
    """
    if pd.isna(goles_a) or pd.isna(goles_b):
        return ""

    if goles_a > goles_b:
        return "A"

    if goles_a < goles_b:
        return "B"

    return "Empate"


def resultado_texto(resultado, equipo_a, equipo_b):
    """
    Convierte resultado A/B/Empate a texto entendible.
    """
    if resultado == "A":
        return equipo_a

    if resultado == "B":
        return equipo_b

    if resultado == "Empate":
        return "Empate"

    return ""


def parsear_marcador_estimado(marcador):
    """
    Convierte marcador estimado tipo '1-0' en dos números.
    """
    marcador = texto_limpio(marcador).replace(" ", "")

    if "-" not in marcador:
        return np.nan, np.nan

    partes = marcador.split("-")

    if len(partes) != 2:
        return np.nan, np.nan

    try:
        goles_a = int(partes[0])
        goles_b = int(partes[1])
        return goles_a, goles_b
    except Exception:
        return np.nan, np.nan


def preparar_calendario_jugado(calendario):
    """
    Filtra partidos jugados con marcador real válido.
    """
    registros = []

    for _, row in calendario.iterrows():
        estado = detectar_estado_partido(row)

        if estado != "Jugado":
            continue

        match_id = texto_limpio(row.get("match_id", ""))
        fecha = fecha_yyyy_mm_dd(row.get("fecha", ""))

        fase = texto_limpio(row.get("fase", ""))
        grupo = texto_limpio(row.get("grupo", ""))

        equipo_a = texto_limpio(row.get("equipo_a", ""))
        equipo_b = texto_limpio(row.get("equipo_b", ""))

        codigo_a = texto_limpio(row.get("codigo_a", "")).upper()
        codigo_b = texto_limpio(row.get("codigo_b", "")).upper()

        goles_a = entero(row.get("goles_a", ""))
        goles_b = entero(row.get("goles_b", ""))

        if not match_id:
            continue

        if pd.isna(fecha):
            continue

        if not equipo_valido(equipo_a) or not equipo_valido(equipo_b):
            continue

        if not codigo_valido(codigo_a) or not codigo_valido(codigo_b):
            continue

        if pd.isna(goles_a) or pd.isna(goles_b):
            continue

        resultado_real_codigo = obtener_resultado(goles_a, goles_b)

        registros.append(
            {
                "match_id": match_id,
                "fecha": fecha.strftime("%Y-%m-%d"),
                "fecha_dt": fecha,
                "fase": fase,
                "grupo": grupo,
                "equipo_a": equipo_a,
                "codigo_a": codigo_a,
                "equipo_b": equipo_b,
                "codigo_b": codigo_b,
                "goles_a": goles_a,
                "goles_b": goles_b,
                "marcador_real": f"{goles_a}-{goles_b}",
                "resultado_real_codigo": resultado_real_codigo,
                "resultado_real": resultado_texto(
                    resultado_real_codigo,
                    equipo_a,
                    equipo_b,
                ),
            }
        )

    partidos_jugados = pd.DataFrame(registros)

    print("Partidos jugados detectados para validar:", len(partidos_jugados))

    return partidos_jugados


def preparar_snapshot(snapshot):
    """
    Limpia el snapshot y deja una predicción por match_id:
    la última predicción disponible.
    """
    columnas_minimas = [
        "run_id",
        "fecha_hora_ejecucion",
        "match_id",
        "equipo_a",
        "equipo_b",
        "favorito",
        "marcador_estimado",
        "prob_a",
        "prob_empate",
        "prob_b",
        "prob_favorito",
        "confianza",
        "version_modelo",
    ]

    if snapshot.empty:
        print("Snapshot vacío.")
        return pd.DataFrame(columns=columnas_minimas)

    for col in columnas_minimas:
        if col not in snapshot.columns:
            print(f"Advertencia: falta columna en snapshot: {col}")

    snapshot = snapshot.copy()

    if "match_id" not in snapshot.columns:
        return pd.DataFrame(columns=columnas_minimas)

    snapshot["match_id"] = snapshot["match_id"].astype(str).str.strip()
    snapshot = snapshot[snapshot["match_id"] != ""].copy()

    if "fecha_hora_ejecucion" in snapshot.columns:
        snapshot["fecha_hora_ejecucion_dt"] = pd.to_datetime(
            snapshot["fecha_hora_ejecucion"],
            errors="coerce",
        )
    else:
        snapshot["fecha_hora_ejecucion_dt"] = pd.NaT

    snapshot = snapshot.sort_values(
        ["match_id", "fecha_hora_ejecucion_dt"],
        ascending=[True, True],
    )

    snapshot_ultima = (
        snapshot
        .drop_duplicates(subset=["match_id"], keep="last")
        .copy()
    )

    print("Predicciones únicas disponibles para validar:", len(snapshot_ultima))

    return snapshot_ultima


def obtener_resultado_predicho(pred_row, equipo_a, equipo_b):
    """
    Convierte el favorito de la predicción en resultado A/B/Empate.
    """
    favorito = texto_limpio(pred_row.get("favorito", ""))

    if favorito == "":
        return ""

    if favorito.lower() == "empate":
        return "Empate"

    if favorito.strip().lower() == texto_limpio(equipo_a).lower():
        return "A"

    if favorito.strip().lower() == texto_limpio(equipo_b).lower():
        return "B"

    return ""


def generar_validacion(partidos_jugados, snapshot_ultima):
    """
    Genera la tabla final de validación.
    """
    registros = []

    if partidos_jugados.empty:
        print("No hay partidos jugados para validar.")
        return pd.DataFrame(columns=COLUMNAS_VALIDACION)

    snapshot_dict = {}

    if not snapshot_ultima.empty and "match_id" in snapshot_ultima.columns:
        snapshot_dict = snapshot_ultima.set_index("match_id").to_dict("index")

    for _, partido in partidos_jugados.iterrows():
        match_id = texto_limpio(partido["match_id"])
        pred = snapshot_dict.get(match_id, {})

        tiene_prediccion = bool(pred)

        equipo_a = partido["equipo_a"]
        equipo_b = partido["equipo_b"]

        resultado_real_codigo = partido["resultado_real_codigo"]

        resultado_predicho_codigo = ""
        resultado_predicho = ""
        favorito_predicho = ""
        marcador_estimado = ""

        goles_estimados_a = np.nan
        goles_estimados_b = np.nan

        acerto_resultado = "No"
        acerto_marcador = "No"

        diferencia_goles_a = ""
        diferencia_goles_b = ""

        notas = ""

        if tiene_prediccion:
            favorito_predicho = texto_limpio(pred.get("favorito", ""))
            resultado_predicho_codigo = obtener_resultado_predicho(
                pred,
                equipo_a,
                equipo_b,
            )
            resultado_predicho = resultado_texto(
                resultado_predicho_codigo,
                equipo_a,
                equipo_b,
            )

            marcador_estimado = texto_limpio(pred.get("marcador_estimado", ""))
            goles_estimados_a, goles_estimados_b = parsear_marcador_estimado(
                marcador_estimado
            )

            if resultado_predicho_codigo == resultado_real_codigo:
                acerto_resultado = "Sí"

            if (
                not pd.isna(goles_estimados_a)
                and not pd.isna(goles_estimados_b)
                and int(goles_estimados_a) == int(partido["goles_a"])
                and int(goles_estimados_b) == int(partido["goles_b"])
            ):
                acerto_marcador = "Sí"

            if not pd.isna(goles_estimados_a):
                diferencia_goles_a = int(goles_estimados_a) - int(partido["goles_a"])

            if not pd.isna(goles_estimados_b):
                diferencia_goles_b = int(goles_estimados_b) - int(partido["goles_b"])

            if resultado_predicho_codigo == "":
                notas = "No se pudo mapear el favorito predicho contra equipo_a/equipo_b."
        else:
            notas = "No existe predicción histórica para este match_id en el snapshot."

        registros.append(
            {
                "run_id_validacion": RUN_ID,
                "fecha_hora_validacion": FECHA_HORA_EJECUCION,
                "match_id": match_id,
                "fecha": partido["fecha"],
                "fase": partido["fase"],
                "grupo": partido["grupo"],
                "equipo_a": equipo_a,
                "codigo_a": partido["codigo_a"],
                "equipo_b": equipo_b,
                "codigo_b": partido["codigo_b"],
                "goles_a": partido["goles_a"],
                "goles_b": partido["goles_b"],
                "marcador_real": partido["marcador_real"],
                "resultado_real": partido["resultado_real"],
                "run_id_prediccion": texto_limpio(pred.get("run_id", "")),
                "fecha_hora_prediccion": texto_limpio(
                    pred.get("fecha_hora_ejecucion", "")
                ),
                "fecha_prediccion": texto_limpio(pred.get("fecha_prediccion", "")),
                "favorito_predicho": favorito_predicho,
                "resultado_predicho": resultado_predicho,
                "marcador_estimado": marcador_estimado,
                "prob_a": pred.get("prob_a", ""),
                "prob_empate": pred.get("prob_empate", ""),
                "prob_b": pred.get("prob_b", ""),
                "prob_favorito": pred.get("prob_favorito", ""),
                "confianza": texto_limpio(pred.get("confianza", "")),
                "acerto_resultado": acerto_resultado,
                "acerto_marcador": acerto_marcador,
                "diferencia_goles_a": diferencia_goles_a,
                "diferencia_goles_b": diferencia_goles_b,
                "tiene_prediccion": "Sí" if tiene_prediccion else "No",
                "version_modelo": texto_limpio(
                    pred.get("version_modelo", MODEL_VERSION)
                ),
                "tabla_origen_prediccion": TAB_SNAPSHOT,
                "notas": notas,
            }
        )

    validacion_df = pd.DataFrame(registros)

    if validacion_df.empty:
        validacion_df = pd.DataFrame(columns=COLUMNAS_VALIDACION)
    else:
        validacion_df = validacion_df[COLUMNAS_VALIDACION]

    print("Filas de validación generadas:", len(validacion_df))

    if not validacion_df.empty:
        print(
            "Predicciones con resultado acertado:",
            (validacion_df["acerto_resultado"] == "Sí").sum(),
        )
        print(
            "Predicciones con marcador exacto:",
            (validacion_df["acerto_marcador"] == "Sí").sum(),
        )

    return validacion_df


def crear_log_ejecucion(
    validacion_df,
    snapshot_df,
    estado="OK",
    mensaje="Validación terminada correctamente",
):
    """
    Crea una fila de auditoría para registrar cada ejecución del pipeline.
    """
    return pd.DataFrame(
        [
            {
                "run_id": RUN_ID,
                "fecha_hora_ejecucion": FECHA_HORA_EJECUCION,
                "proyecto": "mundial-2026-predicciones",
                "script": "02_validacion_predicciones_2026.py",
                "origen": ENVIRONMENT,
                "estado": estado,
                "filas_predicciones": len(validacion_df),
                "filas_snapshot": len(snapshot_df),
                "tabla_predicciones": TAB_VALIDACION,
                "tabla_snapshot": TAB_SNAPSHOT,
                "version_modelo": MODEL_VERSION,
                "mensaje": mensaje,
            }
        ]
    )


def main():
    """
    Ejecución principal del pipeline de validación.
    """
    print("====================================================")
    print("Validación de predicciones Mundial 2026")
    print(f"Run ID: {RUN_ID}")
    print(f"Fecha/hora ejecución: {FECHA_HORA_EJECUCION}")
    print("====================================================")

    calendario, snapshot = cargar_tablas()

    validar_columnas_calendario(calendario)

    partidos_jugados = preparar_calendario_jugado(calendario)

    snapshot_ultima = preparar_snapshot(snapshot)

    validacion_df = generar_validacion(partidos_jugados, snapshot_ultima)

    escribir_df_en_hoja(validacion_df, TAB_VALIDACION)

    mensaje_log = (
        f"Validación generada. Partidos jugados: {len(partidos_jugados)}. "
        f"Filas validación: {len(validacion_df)}."
    )

    log_df = crear_log_ejecucion(
        validacion_df=validacion_df,
        snapshot_df=snapshot,
        mensaje=mensaje_log,
    )

    append_df_en_hoja(log_df, TAB_LOGS)

    print("====================================================")
    print("Proceso de validación terminado.")
    print(f"Tabla de validación escrita en: {TAB_VALIDACION}")
    print(f"Log agregado en: {TAB_LOGS}")
    print(f"Filas de validación generadas: {len(validacion_df)}")
    print("====================================================")


if __name__ == "__main__":
    main()
