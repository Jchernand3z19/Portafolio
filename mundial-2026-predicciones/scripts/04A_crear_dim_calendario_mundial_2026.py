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

SOURCE_SHEET = "Calendario Mundial 2026 - Data Matrix"
OUTPUT_SHEET = "dim_calendario_mundial_2026"
EXPECTED_MATCHES = int(os.getenv("EXPECTED_MATCHES", "104"))


OUTPUT_COLUMNS = [
    "partido_id",
    "fecha",
    "hora",
    "fase",
    "grupo",
    "sede",
    "ciudad",
    "pais_sede",
    "region_sede",

    "equipo_a",
    "codigo_a",
    "equipo_b",
    "codigo_b",
    "origen_equipo_a",
    "origen_equipo_b",
    "siguiente_partido_id",
    "slot_siguiente",

    "estado_partido",
    "goles_real_a",
    "goles_real_b",
    "penales_real_a",
    "penales_real_b",
    "ganador_real",

    "fixture_id_api",
    "ultima_revision_api",
    "api_estado",
    "api_orientacion",
    "ultima_actualizacion_resultado",
    "ultima_actualizacion_dim",
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
        worksheet = spreadsheet.worksheet(sheet_name)
        return pd.DataFrame(worksheet.get_all_records())
    except gspread.WorksheetNotFound:
        return pd.DataFrame()


def write_sheet(spreadsheet, sheet_name, df):
    try:
        worksheet = spreadsheet.worksheet(sheet_name)
        worksheet.clear()
        worksheet.resize(
            rows=max(len(df) + 50, 150),
            cols=max(len(df.columns) + 5, 40),
        )
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(
            title=sheet_name,
            rows=max(len(df) + 50, 150),
            cols=max(len(df.columns) + 5, 40),
        )

    values = [df.columns.tolist()] + df.fillna("").astype(str).values.tolist()
    worksheet.update(values)


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

    return value == "" or value.lower() in [
        "nan",
        "none",
        "null",
        "tbd",
        "por_definir",
    ]


def clean_text(value):
    if is_blank(value):
        return ""

    value = str(value).strip()
    value = re.sub(r"\s+", " ", value)

    return value


def clean_key(value):
    value = clean_text(value).lower()

    replacements = {
        "á": "a",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",
        "ü": "u",
        "ñ": "n",
        "ç": "c",
    }

    for old, new in replacements.items():
        value = value.replace(old, new)

    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")

    return value


def to_number(value):
    try:
        if is_blank(value):
            return None

        return float(str(value).replace(",", "."))
    except Exception:
        return None


def normalize_estado(value):
    estado = clean_text(value).lower()

    if estado in [
        "jugado",
        "final",
        "finalizado",
        "completado",
        "complete",
        "completed",
    ]:
        return "FINAL"

    if estado in [
        "en vivo",
        "live",
        "playing",
        "in progress",
    ]:
        return "EN VIVO"

    return "PENDIENTE"


def is_knockout_phase(fase):
    fase = clean_key(fase)

    return not ("grupo" in fase or "group" in fase)


def is_origin_code(value):
    value = clean_text(value).upper()

    return re.match(r"^[WL]\d+$", value) is not None


def extract_origin_from_team_name(team_name):
    text = clean_text(team_name)
    key = clean_key(text).upper()

    match = re.search(r"GANADOR_(\d+)", key)

    if match:
        return f"W{match.group(1)}"

    match = re.search(r"WINNER_(\d+)", key)

    if match:
        return f"W{match.group(1)}"

    match = re.search(r"PERDEDOR_(\d+)", key)

    if match:
        return f"L{match.group(1)}"

    match = re.search(r"LOSER_(\d+)", key)

    if match:
        return f"L{match.group(1)}"

    return ""


def get_team_and_origin(team_name, team_code):
    team_name = clean_text(team_name)
    team_code = clean_text(team_code).upper()

    if is_origin_code(team_code):
        return "", team_code

    origin_from_name = extract_origin_from_team_name(team_name)

    if origin_from_name:
        return "", origin_from_name

    return team_name, ""


# =====================================================
# DETECCIÓN DE COLUMNAS
# =====================================================

def detect_source_columns(df):
    cols = {
        "match_id": find_col(df, [
            "match_id",
            "partido_id",
            "id_partido",
            "id",
        ]),
        "fecha": find_col(df, [
            "fecha",
            "date",
            "match_date",
        ]),
        "hora": find_col(df, [
            "hora",
            "time",
            "match_time",
        ]),
        "fase": find_col(df, [
            "fase",
            "round",
            "ronda",
            "etapa",
        ]),
        "grupo": find_col(df, [
            "grupo",
            "group",
        ]),
        "equipo_a": find_col(df, [
            "equipo_a",
            "team_a",
            "seleccion_a",
            "local",
            "home_team",
        ]),
        "codigo_a": find_col(df, [
            "codigo_a",
            "code_a",
            "team_a_code",
            "codigo_equipo_a",
        ]),
        "equipo_b": find_col(df, [
            "equipo_b",
            "team_b",
            "seleccion_b",
            "visitante",
            "away_team",
        ]),
        "codigo_b": find_col(df, [
            "codigo_b",
            "code_b",
            "team_b_code",
            "codigo_equipo_b",
        ]),
        "sede": find_col(df, [
            "sede",
            "venue",
            "estadio",
            "stadium",
        ]),
        "ciudad": find_col(df, [
            "ciudad",
            "city",
        ]),
        "pais_sede": find_col(df, [
            "pais_sede",
            "host_country",
            "country_host",
        ]),
        "region_sede": find_col(df, [
            "region_sede",
            "region",
            "host_region",
        ]),
        "goles_a": find_col(df, [
            "goles_a",
            "score_a",
            "home_score",
            "goles_real_a",
        ]),
        "goles_b": find_col(df, [
            "goles_b",
            "score_b",
            "away_score",
            "goles_real_b",
        ]),
        "estado": find_col(df, [
            "estado",
            "estado_partido",
            "status",
            "match_status",
        ]),
        "fixture_id_api": find_col(df, [
            "fixture_id_api",
            "fixture_id",
            "api_fixture_id",
        ]),
        "ultima_revision_api": find_col(df, [
            "ultima_revision_api",
            "last_api_review",
        ]),
        "api_estado": find_col(df, [
            "api_estado",
            "api_status",
        ]),
        "api_orientacion": find_col(df, [
            "api_orientacion",
            "api_orientation",
        ]),
        "ultima_actualizacion_resultado": find_col(df, [
            "ultima_actualizacion_resultado",
            "last_result_update",
        ]),
    }

    required = [
        "match_id",
        "fecha",
        "fase",
        "equipo_a",
        "codigo_a",
        "equipo_b",
        "codigo_b",
        "estado",
    ]

    missing = [col for col in required if cols[col] is None]

    if missing:
        raise ValueError(
            f"No se puede crear {OUTPUT_SHEET}. "
            f"Faltan columnas en {SOURCE_SHEET}: {missing}. "
            f"Columnas disponibles: {list(df.columns)}"
        )

    print("Columnas fuente detectadas:")

    for key, value in cols.items():
        print(f"- {key}: {value}")

    return cols


# =====================================================
# GANADOR REAL
# =====================================================

def get_real_winner(row):
    if row.get("estado_partido") != "FINAL":
        return ""

    equipo_a = clean_text(row.get("equipo_a", ""))
    equipo_b = clean_text(row.get("equipo_b", ""))

    goles_a = to_number(row.get("goles_real_a", ""))
    goles_b = to_number(row.get("goles_real_b", ""))

    if goles_a is None or goles_b is None:
        return ""

    if goles_a > goles_b:
        return equipo_a

    if goles_b > goles_a:
        return equipo_b

    penales_a = to_number(row.get("penales_real_a", ""))
    penales_b = to_number(row.get("penales_real_b", ""))

    if penales_a is not None and penales_b is not None:
        if penales_a > penales_b:
            return equipo_a

        if penales_b > penales_a:
            return equipo_b

    return ""


def infer_winners_from_future_matches(rows):
    """
    Si un partido eliminatorio terminó empatado y no tenemos penales,
    inferimos el ganador cuando uno de los dos equipos aparece en una ronda posterior.

    Ejemplo:
    Alemania 1-1 Paraguay
    Si Paraguay aparece en Octavos, ganador_real = Paraguay.

    Esto no inventa marcador de penales.
    Solo completa ganador_real cuando es evidente por el calendario actualizado.
    """
    for idx, row in enumerate(rows):
        if row.get("estado_partido") != "FINAL":
            continue

        if not is_knockout_phase(row.get("fase", "")):
            continue

        if not is_blank(row.get("ganador_real", "")):
            continue

        goles_a = to_number(row.get("goles_real_a", ""))
        goles_b = to_number(row.get("goles_real_b", ""))

        if goles_a is None or goles_b is None:
            continue

        if goles_a != goles_b:
            continue

        equipo_a = clean_text(row.get("equipo_a", ""))
        equipo_b = clean_text(row.get("equipo_b", ""))

        if is_blank(equipo_a) or is_blank(equipo_b):
            continue

        try:
            partido_actual = int(row.get("partido_id", ""))
        except Exception:
            continue

        aparece_a = False
        aparece_b = False

        for other in rows:
            try:
                partido_futuro = int(other.get("partido_id", ""))
            except Exception:
                continue

            if partido_futuro <= partido_actual:
                continue

            futuros = {
                clean_text(other.get("equipo_a", "")),
                clean_text(other.get("equipo_b", "")),
            }

            if equipo_a in futuros:
                aparece_a = True

            if equipo_b in futuros:
                aparece_b = True

        if aparece_a and not aparece_b:
            rows[idx]["ganador_real"] = equipo_a

        if aparece_b and not aparece_a:
            rows[idx]["ganador_real"] = equipo_b

    return rows


# =====================================================
# CONSTRUCCIÓN DEL CALENDARIO NORMALIZADO
# =====================================================

def build_dim_calendar(df_source, cols):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = []

    for _, row in df_source.iterrows():
        partido_id = clean_text(row.get(cols["match_id"], ""))

        if is_blank(partido_id):
            continue

        equipo_a, origen_a = get_team_and_origin(
            row.get(cols["equipo_a"], ""),
            row.get(cols["codigo_a"], ""),
        )

        equipo_b, origen_b = get_team_and_origin(
            row.get(cols["equipo_b"], ""),
            row.get(cols["codigo_b"], ""),
        )

        estado_partido = normalize_estado(row.get(cols["estado"], ""))

        goles_real_a = ""
        goles_real_b = ""

        if estado_partido == "FINAL":
            goles_real_a = row.get(cols["goles_a"], "") if cols["goles_a"] else ""
            goles_real_b = row.get(cols["goles_b"], "") if cols["goles_b"] else ""

        output_row = {
            "partido_id": partido_id,
            "fecha": row.get(cols["fecha"], ""),
            "hora": row.get(cols["hora"], "") if cols["hora"] else "",
            "fase": row.get(cols["fase"], ""),
            "grupo": row.get(cols["grupo"], "") if cols["grupo"] else "",
            "sede": row.get(cols["sede"], "") if cols["sede"] else "",
            "ciudad": row.get(cols["ciudad"], "") if cols["ciudad"] else "",
            "pais_sede": row.get(cols["pais_sede"], "") if cols["pais_sede"] else "",
            "region_sede": row.get(cols["region_sede"], "") if cols["region_sede"] else "",

            "equipo_a": equipo_a,
            "codigo_a": row.get(cols["codigo_a"], "") if cols["codigo_a"] else "",
            "equipo_b": equipo_b,
            "codigo_b": row.get(cols["codigo_b"], "") if cols["codigo_b"] else "",
            "origen_equipo_a": origen_a,
            "origen_equipo_b": origen_b,
            "siguiente_partido_id": "",
            "slot_siguiente": "",

            "estado_partido": estado_partido,
            "goles_real_a": goles_real_a,
            "goles_real_b": goles_real_b,
            "penales_real_a": "",
            "penales_real_b": "",
            "ganador_real": "",

            "fixture_id_api": row.get(cols["fixture_id_api"], "") if cols["fixture_id_api"] else "",
            "ultima_revision_api": row.get(cols["ultima_revision_api"], "") if cols["ultima_revision_api"] else "",
            "api_estado": row.get(cols["api_estado"], "") if cols["api_estado"] else "",
            "api_orientacion": row.get(cols["api_orientacion"], "") if cols["api_orientacion"] else "",
            "ultima_actualizacion_resultado": row.get(cols["ultima_actualizacion_resultado"], "") if cols["ultima_actualizacion_resultado"] else "",
            "ultima_actualizacion_dim": now,
        }

        output_row["ganador_real"] = get_real_winner(output_row)

        rows.append(output_row)

    rows = infer_winners_from_future_matches(rows)

    df_output = pd.DataFrame(rows)

    for col in OUTPUT_COLUMNS:
        if col not in df_output.columns:
            df_output[col] = ""

    df_output = df_output[OUTPUT_COLUMNS]
    df_output = df_output.drop_duplicates(subset=["partido_id"], keep="first")

    df_output["_orden"] = pd.to_numeric(df_output["partido_id"], errors="coerce")
    df_output = df_output.sort_values(["_orden", "partido_id"]).drop(columns=["_orden"])

    return df_output


# =====================================================
# VALIDACIÓN
# =====================================================

def validate_calendar(df):
    total = len(df)

    if total != EXPECTED_MATCHES:
        raise ValueError(
            f"{OUTPUT_SHEET} quedó con {total} partidos. "
            f"Se esperaban {EXPECTED_MATCHES}."
        )

    ids = df["partido_id"].astype(str).str.strip()

    if ids.eq("").any():
        raise ValueError("Hay partido_id vacíos.")

    unique_ids = ids.nunique()

    if unique_ids != total:
        raise ValueError(
            f"Hay partido_id duplicados. "
            f"Filas: {total}, IDs únicos: {unique_ids}."
        )

    numeric_ids = pd.to_numeric(df["partido_id"], errors="coerce")

    min_id = numeric_ids.min()
    max_id = numeric_ids.max()

    if min_id != 1 or max_id != EXPECTED_MATCHES:
        raise ValueError(
            f"El calendario debe ir de 1 a {EXPECTED_MATCHES}. "
            f"MIN={min_id}, MAX={max_id}."
        )

    empty_dates = df["fecha"].astype(str).str.strip().eq("").sum()

    if empty_dates > 0:
        raise ValueError(f"Hay {empty_dates} partidos sin fecha.")

    empty_teams_group = df[
        df["fase"].astype(str).str.lower().str.contains("grupo", na=False)
        & (
            df["equipo_a"].astype(str).str.strip().eq("")
            | df["equipo_b"].astype(str).str.strip().eq("")
        )
    ]

    if len(empty_teams_group) > 0:
        raise ValueError(
            f"Hay {len(empty_teams_group)} partidos de fase de grupos sin equipos."
        )


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

    print("Detectando columnas fuente...")
    cols = detect_source_columns(df_source)

    print("Construyendo dim_calendario_mundial_2026...")
    df_output = build_dim_calendar(df_source, cols)

    print("Validando calendario normalizado...")
    validate_calendar(df_output)

    print(f"Escribiendo hoja destino: {OUTPUT_SHEET}")
    write_sheet(spreadsheet, OUTPUT_SHEET, df_output)

    total = len(df_output)
    finalizados = len(df_output[df_output["estado_partido"] == "FINAL"])
    pendientes = len(df_output[df_output["estado_partido"] == "PENDIENTE"])
    en_vivo = len(df_output[df_output["estado_partido"] == "EN VIVO"])

    origenes = len(
        df_output[
            (df_output["origen_equipo_a"].astype(str).str.strip() != "")
            | (df_output["origen_equipo_b"].astype(str).str.strip() != "")
        ]
    )

    ganadores_reales = len(
        df_output[df_output["ganador_real"].astype(str).str.strip() != ""]
    )

    print("--------------------------------")
    print("Calendario normalizado correctamente")
    print(f"Hoja fuente: {SOURCE_SHEET}")
    print(f"Hoja destino: {OUTPUT_SHEET}")
    print(f"Partidos totales: {total}")
    print(f"Finalizados: {finalizados}")
    print(f"Pendientes: {pendientes}")
    print(f"En vivo: {en_vivo}")
    print(f"Partidos con origen W/L: {origenes}")
    print(f"Partidos con ganador_real: {ganadores_reales}")
    print("--------------------------------")


if __name__ == "__main__":
    main()
