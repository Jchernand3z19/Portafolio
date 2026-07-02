import os
import re
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "service_account.json")

SOURCE_SHEET = "fact_predicciones_2026"
OUTPUT_SHEET = "fact_partidos_prediccion_2026"


OUTPUT_COLUMNS = [
    "partido_id",
    "fecha",
    "hora",
    "fase",
    "grupo",
    "sede",
    "equipo_a",
    "equipo_b",

    "goles_pred_inicial_a",
    "goles_pred_inicial_b",
    "ganador_pred_inicial",
    "confianza_pred_inicial",

    "goles_pred_vivo_a",
    "goles_pred_vivo_b",
    "ganador_pred_vivo",
    "confianza_pred_vivo",

    "estado_partido",
    "goles_real_a",
    "goles_real_b",
    "penales_real_a",
    "penales_real_b",
    "ganador_real",

    "estado_usado",
    "goles_usados_a",
    "goles_usados_b",
    "ganador_usado",
    "et    "estado_usado",
    "goles_usados_a",
    "goles_usados_b",
    "iqueta_visual",
    "es_penales",

    "ultima_actualizacion"
]


def get_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    credentials = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=scopes
    )

    return gspread.authorize(credentials)


def read_sheet(spreadsheet, sheet_name):
    try:
        ws = spreadsheet.worksheet(sheet_name)
        data = ws.get_all_records()
        return pd.DataFrame(data)
    except gspread.WorksheetNotFound:
        return pd.DataFrame()


def write_sheet(spreadsheet, sheet_name, df):
    try:
        ws = spreadsheet.worksheet(sheet_name)
        ws.clear()
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(
            title=sheet_name,
            rows=max(len(df) + 20, 100),
            cols=max(len(df.columns) + 5, 30)
        )

    values = [df.columns.tolist()] + df.fillna("").astype(str).values.tolist()
    ws.update(values)


def normalize_columns(df):
    df = df.copy()
    df.columns = [
        str(c).strip().lower().replace(" ", "_").replace("-", "_")
        for c in df.columns
    ]
    return df


def find_col(df, options):
    for col in options:
        if col in df.columns:
            return col
    return None


def clean_id(value):
    value = str(value).strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value


def build_partido_id(row, idx, cols):
    for possible in ["partido_id", "match_id", "id_partido", "id"]:
        if possible in row and str(row[possible]).strip():
            return str(row[possible]).strip()

    fase = str(row.get(cols["fase"], "")).strip()
    grupo = str(row.get(cols["grupo"], "")).strip()
    equipo_a = str(row.get(cols["equipo_a"], "")).strip()
    equipo_b = str(row.get(cols["equipo_b"], "")).strip()

    base = f"{idx + 1}_{fase}_{grupo}_{equipo_a}_vs_{equipo_b}"
    return clean_id(base)


def detectar_columnas_base(df):
    cols = {
        "fecha": find_col(df, ["fecha", "date", "match_date"]),
        "hora": find_col(df, ["hora", "time", "match_time"]),
        "fase": find_col(df, ["fase", "ronda", "round", "etapa"]),
        "grupo": find_col(df, ["grupo", "group"]),
        "sede": find_col(df, ["sede", "venue", "estadio", "stadium"]),

        "equipo_a": find_col(df, [
            "equipo_a", "seleccion_a", "team_a", "local", "home_team", "pais_a"
        ]),
        "equipo_b": find_col(df, [
            "equipo_b", "seleccion_b", "team_b", "visitante", "away_team", "pais_b"
        ]),

        "goles_pred_a": find_col(df, [
            "goles_pred_a", "goles_a_pred", "pred_goles_a",
            "goles_equipo_a", "goles_a", "score_a"
        ]),
        "goles_pred_b": find_col(df, [
            "goles_pred_b", "goles_b_pred", "pred_goles_b",
            "goles_equipo_b", "goles_b", "score_b"
        ]),

        "ganador_predicho": find_col(df, [
            "ganador_predicho", "winner_pred", "predicted_winner",
            "ganador", "clasificado"
        ]),
        "confianza": find_col(df, [
            "confianza", "nivel_confianza", "confidence"
        ]),
    }

    required = ["fase", "equipo_a", "equipo_b", "goles_pred_a", "goles_pred_b"]
    missing = [c for c in required if cols[c] is None]

    if missing:
        raise ValueError(
            "No se puede crear fact_partidos_prediccion_2026. "
            f"Faltan columnas base en {SOURCE_SHEET}: {missing}. "
            f"Columnas disponibles: {list(df.columns)}"
        )

    return cols


def crear_base_partidos(df_source, cols):
    rows = []

    for idx, row in df_source.iterrows():
        partido_id = build_partido_id(row, idx, cols)

        equipo_a = row.get(cols["equipo_a"], "")
        equipo_b = row.get(cols["equipo_b"], "")

        goles_a = row.get(cols["goles_pred_a"], "")
        goles_b = row.get(cols["goles_pred_b"], "")

        ganador = ""
        if cols["ganador_predicho"]:
            ganador = row.get(cols["ganador_predicho"], "")

        if not ganador:
            try:
                if float(goles_a) > float(goles_b):
                    ganador = equipo_a
                elif float(goles_b) > float(goles_a):
                    ganador = equipo_b
                else:
                    ganador = ""
            except Exception:
                ganador = ""

        rows.append({
            "partido_id": partido_id,
            "fecha": row.get(cols["fecha"], "") if cols["fecha"] else "",
            "hora": row.get(cols["hora"], "") if cols["hora"] else "",
            "fase": row.get(cols["fase"], ""),
            "grupo": row.get(cols["grupo"], "") if cols["grupo"] else "",
            "sede": row.get(cols["sede"], "") if cols["sede"] else "",
            "equipo_a": equipo_a,
            "equipo_b": equipo_b,

            "goles_pred_inicial_a": goles_a,
            "goles_pred_inicial_b": goles_b,
            "ganador_pred_inicial": ganador,
            "confianza_pred_inicial": row.get(cols["confianza"], "") if cols["confianza"] else "",

            "goles_pred_vivo_a": goles_a,
            "goles_pred_vivo_b": goles_b,
            "ganador_pred_vivo": ganador,
            "confianza_pred_vivo": row.get(cols["confianza"], "") if cols["confianza"] else "",

            "estado_partido": "PENDIENTE",
            "goles_real_a": "",
            "goles_real_b": "",
            "penales_real_a": "",
            "penales_real_b": "",
            "ganador_real": "",

            "estado_usado": "PRED",
            "goles_usados_a": goles_a,
            "goles_usados_b": goles_b,
            "ganador_usado": ganador,
            "etiqueta_visual": "PRED",
            "es_penales": "NO",

            "ultima_actualizacion": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

    return pd.DataFrame(rows)


def es_final(row):
    estado = str(row.get("estado_partido", "")).strip().upper()
    if estado in ["FINAL", "FINALIZADO", "COMPLETADO", "COMPLETE"]:
        return True

    goles_real_a = str(row.get("goles_real_a", "")).strip()
    goles_real_b = str(row.get("goles_real_b", "")).strip()

    return goles_real_a != "" and goles_real_b != ""


def merge_con_tabla_existente(df_base, df_existing):
    if df_existing.empty:
        return df_base

    df_existing = normalize_columns(df_existing)

    for col in OUTPUT_COLUMNS:
        if col not in df_existing.columns:
            df_existing[col] = ""

    existing_map = {
        str(row["partido_id"]): row
        for _, row in df_existing.iterrows()
        if str(row.get("partido_id", "")).strip()
    }

    merged_rows = []

    for _, base_row in df_base.iterrows():
        partido_id = str(base_row["partido_id"])

        if partido_id not in existing_map:
            merged_rows.append(base_row.to_dict())
            continue

        old = existing_map[partido_id].to_dict()
        new = base_row.to_dict()

        # Mantener pronóstico inicial si ya existía
        for col in [
            "goles_pred_inicial_a",
            "goles_pred_inicial_b",
            "ganador_pred_inicial",
            "confianza_pred_inicial"
        ]:
            if str(old.get(col, "")).strip():
                new[col] = old.get(col, "")

        # Mantener resultado real si ya existía
        for col in [
            "estado_partido",
            "goles_real_a",
            "goles_real_b",
            "penales_real_a",
            "penales_real_b",
            "ganador_real"
        ]:
            if str(old.get(col, "")).strip():
                new[col] = old.get(col, "")

        # Si está finalizado, no tocar pronóstico vivo existente
        if es_final(old):
            for col in [
                "goles_pred_vivo_a",
                "goles_pred_vivo_b",
                "ganador_pred_vivo",
                "confianza_pred_vivo"
            ]:
                if str(old.get(col, "")).strip():
                    new[col] = old.get(col, "")

        merged_rows.append(new)

    return pd.DataFrame(merged_rows)


def aplicar_resultado_usado(df):
    df = df.copy()

    for idx, row in df.iterrows():
        finalizado = es_final(row)

        penales_real_a = str(row.get("penales_real_a", "")).strip()
        penales_real_b = str(row.get("penales_real_b", "")).strip()

        tiene_penales = penales_real_a != "" and penales_real_b != ""

        if finalizado:
            df.at[idx, "estado_partido"] = "FINAL"
            df.at[idx, "estado_usado"] = "FINAL"
            df.at[idx, "goles_usados_a"] = row.get("goles_real_a", "")
            df.at[idx, "goles_usados_b"] = row.get("goles_real_b", "")
            df.at[idx, "ganador_usado"] = row.get("ganador_real", "")
            df.at[idx, "es_penales"] = "SI" if tiene_penales else "NO"
            df.at[idx, "etiqueta_visual"] = "FINAL / PEN" if tiene_penales else "FINAL"
        else:
            df.at[idx, "estado_partido"] = row.get("estado_partido", "PENDIENTE") or "PENDIENTE"
            df.at[idx, "estado_usado"] = "PRED"
            df.at[idx, "goles_usados_a"] = row.get("goles_pred_vivo_a", "")
            df.at[idx, "goles_usados_b"] = row.get("goles_pred_vivo_b", "")
            df.at[idx, "ganador_usado"] = row.get("ganador_pred_vivo", "")
            df.at[idx, "es_penales"] = "NO"
            df.at[idx, "etiqueta_visual"] = "PRED"

        df.at[idx, "ultima_actualizacion"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return df


def main():
    if not SPREADSHEET_ID:
        raise ValueError("Falta SPREADSHEET_ID en GitHub Secrets.")

    client = get_client()
    spreadsheet = client.open_by_key(SPREADSHEET_ID)

    print(f"Leyendo hoja fuente: {SOURCE_SHEET}")
    df_source = read_sheet(spreadsheet, SOURCE_SHEET)

    if df_source.empty:
        raise ValueError(f"La hoja {SOURCE_SHEET} está vacía o no existe.")

    df_source = normalize_columns(df_source)
    cols = detectar_columnas_base(df_source)

    print("Creando base de partidos desde fact_predicciones_2026...")
    df_base = crear_base_partidos(df_source, cols)

    print(f"Leyendo hoja existente: {OUTPUT_SHEET}")
    df_existing = read_sheet(spreadsheet, OUTPUT_SHEET)

    print("Conservando pronóstico inicial y resultados reales existentes...")
    df_final = merge_con_tabla_existente(df_base, df_existing)

    print("Aplicando resultado usado para dashboard...")
    df_final = aplicar_resultado_usado(df_final)

    for col in OUTPUT_COLUMNS:
        if col not in df_final.columns:
            df_final[col] = ""

    df_final = df_final[OUTPUT_COLUMNS]

    print(f"Escribiendo hoja: {OUTPUT_SHEET}")
    write_sheet(spreadsheet, OUTPUT_SHEET, df_final)

    total = len(df_final)
    finalizados = len(df_final[df_final["estado_usado"] == "FINAL"])
    pred = len(df_final[df_final["estado_usado"] == "PRED"])

    print("--------------------------------")
    print("Tabla actualizada correctamente")
    print(f"Hoja: {OUTPUT_SHEET}")
    print(f"Filas procesadas: {total}")
    print(f"Partidos con FINAL: {finalizados}")
    print(f"Partidos con PRED: {pred}")
    print("--------------------------------")


if __name__ == "__main__":
    main()
