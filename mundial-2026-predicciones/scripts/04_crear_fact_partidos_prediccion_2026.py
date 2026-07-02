import os
import re
from datetime import datetime

import gspread
import pandas as pd
from google.oauth2.service_account import Credentials


# =====================================================
# CONFIGURACIÓN
# =====================================================

SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
SERVICE_ACCOUNT_FILE = os.getenv(
    "GOOGLE_APPLICATION_CREDENTIALS",
    "service_account.json"
)

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
    "penales_pred_inicial_a",
    "penales_pred_inicial_b",
    "ganador_penales_pred_inicial",

    "goles_pred_vivo_a",
    "goles_pred_vivo_b",
    "ganador_pred_vivo",
    "confianza_pred_vivo",
    "penales_pred_vivo_a",
    "penales_pred_vivo_b",
    "ganador_penales_pred_vivo",

    "estado_partido",
    "goles_real_a",
    "goles_real_b",
    "penales_real_a",
    "penales_real_b",
    "ganador_real",

    "estado_usado",
    "goles_usados_a",
    "goles_usados_b",
    "penales_usados_a",
    "penales_usados_b",
    "ganador_usado",
    "etiqueta_visual",
    "es_penales",

    "ultima_actualizacion"
]


# =====================================================
# CONEXIÓN GOOGLE SHEETS
# =====================================================

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
            cols=max(len(df.columns) + 5, 40)
        )

    values = [df.columns.tolist()] + df.fillna("").astype(str).values.tolist()
    ws.update(values)


# =====================================================
# UTILIDADES
# =====================================================

def normalize_columns(df):
    df = df.copy()
    df.columns = [
        str(col)
        .strip()
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace(".", "")
        for col in df.columns
    ]
    return df


def find_col(df, options):
    for col in options:
        if col in df.columns:
            return col
    return None


def is_blank(value):
    if pd.isna(value):
        return True

    value = str(value).strip()

    return value == "" or value.lower() in ["nan", "none", "null"]


def cell(row, col, default=""):
    if col is None:
        return default

    if col not in row:
        return default

    value = row.get(col, default)

    if pd.isna(value):
        return default

    return value


def clean_id(value):
    value = str(value).strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value


def to_number(value):
    try:
        if is_blank(value):
            return None
        return float(value)
    except Exception:
        return None


def normalize_estado(value):
    estado = str(value).strip().upper()

    if estado in ["FINAL", "FINALIZADO", "COMPLETADO", "COMPLETE", "COMPLETED"]:
        return "FINAL"

    if estado in ["EN VIVO", "LIVE"]:
        return "EN VIVO"

    return "PENDIENTE"


def es_fase_eliminatoria(fase):
    fase = str(fase).strip().lower()

    palabras_eliminatoria = [
        "r32",
        "round of 32",
        "32",
        "octavos",
        "round of 16",
        "r16",
        "cuartos",
        "quarter",
        "semifinal",
        "semi",
        "final",
        "3er",
        "tercer",
        "third"
    ]

    return any(palabra in fase for palabra in palabras_eliminatoria)


# =====================================================
# DETECCIÓN DE COLUMNAS
# =====================================================

def detectar_columnas_base(df):
    cols = {
        "partido_id": find_col(df, [
            "partido_id",
            "match_id",
            "id_partido",
            "id_match",
            "id"
        ]),
        "fecha": find_col(df, [
            "fecha",
            "date",
            "match_date"
        ]),
        "hora": find_col(df, [
            "hora",
            "time",
            "match_time"
        ]),
        "fase": find_col(df, [
            "fase",
            "ronda",
            "round",
            "etapa"
        ]),
        "grupo": find_col(df, [
            "grupo",
            "group"
        ]),
        "sede": find_col(df, [
            "sede",
            "venue",
            "estadio",
            "stadium"
        ]),
        "equipo_a": find_col(df, [
            "equipo_a",
            "seleccion_a",
            "team_a",
            "local",
            "home_team",
            "pais_a"
        ]),
        "equipo_b": find_col(df, [
            "equipo_b",
            "seleccion_b",
            "team_b",
            "visitante",
            "away_team",
            "pais_b"
        ]),
        "goles_pred_a": find_col(df, [
            "goles_pred_a",
            "goles_a_pred",
            "pred_goles_a",
            "prediccion_goles_a",
            "goles_equipo_a",
            "goles_a",
            "score_a",
            "goles_esperados_a",
            "expected_goals_a",
            "xg_a"
        ]),
        "goles_pred_b": find_col(df, [
            "goles_pred_b",
            "goles_b_pred",
            "pred_goles_b",
            "prediccion_goles_b",
            "goles_equipo_b",
            "goles_b",
            "score_b",
            "goles_esperados_b",
            "expected_goals_b",
            "xg_b"
        ]),
        "ganador_predicho": find_col(df, [
            "ganador_predicho",
            "winner_pred",
            "predicted_winner",
            "ganador",
            "clasificado",
            "favorito"
        ]),
        "confianza": find_col(df, [
            "confianza",
            "nivel_confianza",
            "confidence",
            "prob_favorito"
        ]),
        "estado_partido": find_col(df, [
            "estado_partido",
            "estado",
            "status",
            "match_status"
        ]),
    }

    required = [
        "partido_id",
        "fase",
        "equipo_a",
        "equipo_b",
        "goles_pred_a",
        "goles_pred_b"
    ]

    missing = [col for col in required if cols[col] is None]

    if missing:
        raise ValueError(
            f"No se puede crear {OUTPUT_SHEET}. "
            f"Faltan columnas base en {SOURCE_SHEET}: {missing}. "
            f"Columnas disponibles: {list(df.columns)}"
        )

    print("Columnas detectadas:")
    print(f"partido_id: {cols['partido_id']}")
    print(f"fecha: {cols['fecha']}")
    print(f"fase: {cols['fase']}")
    print(f"grupo: {cols['grupo']}")
    print(f"equipo_a: {cols['equipo_a']}")
    print(f"equipo_b: {cols['equipo_b']}")
    print(f"goles_pred_a: {cols['goles_pred_a']}")
    print(f"goles_pred_b: {cols['goles_pred_b']}")
    print(f"ganador_predicho: {cols['ganador_predicho']}")
    print(f"confianza: {cols['confianza']}")
    print(f"estado_partido: {cols['estado_partido']}")

    return cols


# =====================================================
# CREACIÓN BASE
# =====================================================

def build_partido_id(row, idx, cols):
    existing_id = cell(row, cols["partido_id"])

    if not is_blank(existing_id):
        return str(existing_id).strip()

    fase = str(cell(row, cols["fase"])).strip()
    grupo = str(cell(row, cols["grupo"])).strip()
    equipo_a = str(cell(row, cols["equipo_a"])).strip()
    equipo_b = str(cell(row, cols["equipo_b"])).strip()

    base = f"{idx + 1}_{fase}_{grupo}_{equipo_a}_vs_{equipo_b}"
    return clean_id(base)


def calcular_ganador_simple(equipo_a, equipo_b, goles_a, goles_b, ganador_fuente):
    if not is_blank(ganador_fuente):
        return ganador_fuente

    num_a = to_number(goles_a)
    num_b = to_number(goles_b)

    if num_a is None or num_b is None:
        return ""

    if num_a > num_b:
        return equipo_a

    if num_b > num_a:
        return equipo_b

    return ""


def crear_base_partidos(df_source, cols):
    rows = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for idx, row in df_source.iterrows():
        partido_id = build_partido_id(row, idx, cols)

        equipo_a = cell(row, cols["equipo_a"])
        equipo_b = cell(row, cols["equipo_b"])

        goles_pred_a = cell(row, cols["goles_pred_a"])
        goles_pred_b = cell(row, cols["goles_pred_b"])

        ganador_fuente = cell(row, cols["ganador_predicho"])
        ganador_pred = calcular_ganador_simple(
            equipo_a,
            equipo_b,
            goles_pred_a,
            goles_pred_b,
            ganador_fuente
        )

        confianza = cell(row, cols["confianza"])
        estado = normalize_estado(cell(row, cols["estado_partido"], "PENDIENTE"))

        rows.append({
            "partido_id": partido_id,
            "fecha": cell(row, cols["fecha"]),
            "hora": cell(row, cols["hora"]),
            "fase": cell(row, cols["fase"]),
            "grupo": cell(row, cols["grupo"]),
            "sede": cell(row, cols["sede"]),
            "equipo_a": equipo_a,
            "equipo_b": equipo_b,

            "goles_pred_inicial_a": goles_pred_a,
            "goles_pred_inicial_b": goles_pred_b,
            "ganador_pred_inicial": ganador_pred,
            "confianza_pred_inicial": confianza,
            "penales_pred_inicial_a": "",
            "penales_pred_inicial_b": "",
            "ganador_penales_pred_inicial": "",

            "goles_pred_vivo_a": goles_pred_a,
            "goles_pred_vivo_b": goles_pred_b,
            "ganador_pred_vivo": ganador_pred,
            "confianza_pred_vivo": confianza,
            "penales_pred_vivo_a": "",
            "penales_pred_vivo_b": "",
            "ganador_penales_pred_vivo": "",

            "estado_partido": estado,
            "goles_real_a": "",
            "goles_real_b": "",
            "penales_real_a": "",
            "penales_real_b": "",
            "ganador_real": "",

            "estado_usado": "PRED",
            "goles_usados_a": goles_pred_a,
            "goles_usados_b": goles_pred_b,
            "penales_usados_a": "",
            "penales_usados_b": "",
            "ganador_usado": ganador_pred,
            "etiqueta_visual": "PRED",
            "es_penales": "NO",

            "ultima_actualizacion": now
        })

    df_base = pd.DataFrame(rows)
    df_base = df_base.drop_duplicates(subset=["partido_id"], keep="first")

    return df_base


# =====================================================
# MERGE CON TABLA EXISTENTE
# =====================================================

def partido_finalizado(row):
    estado = normalize_estado(row.get("estado_partido", ""))

    if estado == "FINAL":
        return True

    goles_real_a = row.get("goles_real_a", "")
    goles_real_b = row.get("goles_real_b", "")

    return not is_blank(goles_real_a) and not is_blank(goles_real_b)


def merge_con_tabla_existente(df_base, df_existing):
    if df_existing.empty:
        return df_base

    df_existing = normalize_columns(df_existing)

    for col in OUTPUT_COLUMNS:
        if col not in df_existing.columns:
            df_existing[col] = ""

    existing_map = {
        str(row["partido_id"]).strip(): row
        for _, row in df_existing.iterrows()
        if not is_blank(row.get("partido_id", ""))
    }

    merged_rows = []

    for _, base_row in df_base.iterrows():
        partido_id = str(base_row["partido_id"]).strip()
        new = base_row.to_dict()

        if partido_id not in existing_map:
            merged_rows.append(new)
            continue

        old = existing_map[partido_id].to_dict()

        # Mantener pronóstico inicial si ya existe.
        inicial_cols = [
            "goles_pred_inicial_a",
            "goles_pred_inicial_b",
            "ganador_pred_inicial",
            "confianza_pred_inicial",
            "penales_pred_inicial_a",
            "penales_pred_inicial_b",
            "ganador_penales_pred_inicial",
        ]

        for col in inicial_cols:
            if not is_blank(old.get(col, "")):
                new[col] = old.get(col, "")

        # Mantener resultados reales.
        real_cols = [
            "estado_partido",
            "goles_real_a",
            "goles_real_b",
            "penales_real_a",
            "penales_real_b",
            "ganador_real",
        ]

        for col in real_cols:
            if not is_blank(old.get(col, "")):
                new[col] = old.get(col, "")

        # Si el partido ya finalizó, no tocar pronóstico vivo existente.
        if partido_finalizado(old):
            vivo_cols = [
                "goles_pred_vivo_a",
                "goles_pred_vivo_b",
                "ganador_pred_vivo",
                "confianza_pred_vivo",
                "penales_pred_vivo_a",
                "penales_pred_vivo_b",
                "ganador_penales_pred_vivo",
            ]

            for col in vivo_cols:
                if not is_blank(old.get(col, "")):
                    new[col] = old.get(col, "")

        merged_rows.append(new)

    return pd.DataFrame(merged_rows)


# =====================================================
# RESULTADO USADO PARA DASHBOARD
# =====================================================

def resolver_ganador_real(row):
    ganador_real = row.get("ganador_real", "")

    if not is_blank(ganador_real):
        return ganador_real

    goles_a = to_number(row.get("goles_real_a", ""))
    goles_b = to_number(row.get("goles_real_b", ""))

    if goles_a is None or goles_b is None:
        return ""

    if goles_a > goles_b:
        return row.get("equipo_a", "")

    if goles_b > goles_a:
        return row.get("equipo_b", "")

    pen_a = to_number(row.get("penales_real_a", ""))
    pen_b = to_number(row.get("penales_real_b", ""))

    if pen_a is not None and pen_b is not None:
        if pen_a > pen_b:
            return row.get("equipo_a", "")
        if pen_b > pen_a:
            return row.get("equipo_b", "")

    return ""


def resolver_ganador_pred_vivo(row):
    ganador_pred = row.get("ganador_pred_vivo", "")

    if not is_blank(ganador_pred):
        return ganador_pred

    goles_a = to_number(row.get("goles_pred_vivo_a", ""))
    goles_b = to_number(row.get("goles_pred_vivo_b", ""))

    if goles_a is None or goles_b is None:
        return ""

    if goles_a > goles_b:
        return row.get("equipo_a", "")

    if goles_b > goles_a:
        return row.get("equipo_b", "")

    ganador_penales = row.get("ganador_penales_pred_vivo", "")

    if not is_blank(ganador_penales):
        return ganador_penales

    return ""


def aplicar_resultado_usado(df):
    df = df.copy()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for idx, row in df.iterrows():
        finalizado = partido_finalizado(row)

        if finalizado:
            pen_a = row.get("penales_real_a", "")
            pen_b = row.get("penales_real_b", "")
            tiene_penales = not is_blank(pen_a) and not is_blank(pen_b)

            ganador_real = resolver_ganador_real(row)

            df.at[idx, "estado_partido"] = "FINAL"
            df.at[idx, "estado_usado"] = "FINAL"
            df.at[idx, "goles_usados_a"] = row.get("goles_real_a", "")
            df.at[idx, "goles_usados_b"] = row.get("goles_real_b", "")
            df.at[idx, "penales_usados_a"] = pen_a if tiene_penales else ""
            df.at[idx, "penales_usados_b"] = pen_b if tiene_penales else ""
            df.at[idx, "ganador_usado"] = ganador_real
            df.at[idx, "ganador_real"] = ganador_real
            df.at[idx, "es_penales"] = "SI" if tiene_penales else "NO"
            df.at[idx, "etiqueta_visual"] = "FINAL / PEN" if tiene_penales else "FINAL"

        else:
            fase = row.get("fase", "")
            goles_a = row.get("goles_pred_vivo_a", "")
            goles_b = row.get("goles_pred_vivo_b", "")

            pen_a = row.get("penales_pred_vivo_a", "")
            pen_b = row.get("penales_pred_vivo_b", "")
            ganador_pen = row.get("ganador_penales_pred_vivo", "")

            goles_num_a = to_number(goles_a)
            goles_num_b = to_number(goles_b)

            empate_pred = (
                goles_num_a is not None
                and goles_num_b is not None
                and goles_num_a == goles_num_b
            )

            tiene_penales_pred = (
                es_fase_eliminatoria(fase)
                and empate_pred
                and (
                    not is_blank(pen_a)
                    or not is_blank(pen_b)
                    or not is_blank(ganador_pen)
                )
            )

            ganador_pred = resolver_ganador_pred_vivo(row)

            df.at[idx, "estado_partido"] = normalize_estado(
                row.get("estado_partido", "PENDIENTE")
            )
            df.at[idx, "estado_usado"] = "PRED"
            df.at[idx, "goles_usados_a"] = goles_a
            df.at[idx, "goles_usados_b"] = goles_b
            df.at[idx, "penales_usados_a"] = pen_a if tiene_penales_pred else ""
            df.at[idx, "penales_usados_b"] = pen_b if tiene_penales_pred else ""
            df.at[idx, "ganador_usado"] = ganador_pred
            df.at[idx, "es_penales"] = "SI" if tiene_penales_pred else "NO"
            df.at[idx, "etiqueta_visual"] = "PRED / PEN" if tiene_penales_pred else "PRED"

        df.at[idx, "ultima_actualizacion"] = now

    return df


# =====================================================
# MAIN
# =====================================================

def main():
    if not SPREADSHEET_ID:
        raise ValueError("Falta SPREADSHEET_ID en GitHub Secrets.")

    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        raise FileNotFoundError(
            f"No existe el archivo de credenciales: {SERVICE_ACCOUNT_FILE}"
        )

    client = get_client()
    spreadsheet = client.open_by_key(SPREADSHEET_ID)

    print(f"Leyendo hoja fuente: {SOURCE_SHEET}")
    df_source = read_sheet(spreadsheet, SOURCE_SHEET)

    if df_source.empty:
        raise ValueError(f"La hoja {SOURCE_SHEET} está vacía o no existe.")

    df_source = normalize_columns(df_source)

    print("Detectando columnas base...")
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
    penales = len(df_final[df_final["es_penales"] == "SI"])

    print("--------------------------------")
    print("Tabla actualizada correctamente")
    print(f"Hoja: {OUTPUT_SHEET}")
    print(f"Filas procesadas: {total}")
    print(f"Partidos con FINAL: {finalizados}")
    print(f"Partidos con PRED: {pred}")
    print(f"Partidos con PEN: {penales}")
    print("--------------------------------")


if __name__ == "__main__":
    main()
