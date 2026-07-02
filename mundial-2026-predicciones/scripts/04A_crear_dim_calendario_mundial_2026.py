import os
import re
from datetime import datetime

import gspread
import pandas as pd
from google.oauth2.service_account import Credentials


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
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(
            title=sheet_name,
            rows=max(len(df) + 50, 150),
            cols=max(len(df.columns) + 5, 40),
        )

    values = [df.columns.tolist()] + df.fillna("").astype(str).values.tolist()
    worksheet.update(values)


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


def is_blank(value):
    if pd.isna(value):
        return True

    value = str(value).strip()

    return value == "" or value.lower() in ["nan", "none", "null"]


def clean_text(value):
    if is_blank(value):
        return ""

    value = str(value).strip()
    value = re.sub(r"\s+", " ", value)

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


def is_origin_code(value):
    value = clean_text(value).upper()

    if re.match(r"^[WL]\d+$", value):
        return True

    return False


def is_knockout_phase(fase):
    fase = clean_text(fase).lower()

    return not ("grupo" in fase or "group" in fase)


def get_team_or_origin(team_knockout_phase(fase):
    fase = clean_text(fase).lower()

    return not ("_name, code):
    team_name = clean_text(team_name)
    code = clean_text(code).upper()

    if is_origin_code(code):
        return "", code

    if team_name.lower().startswith("ganador "):
        return "", "W" + re.sub(r"\D+", "", team_name)

    if team_name.lower().startswith("perdedor "):
        return "", "L" + re.sub(r"\D+", "", team_name)

    return team_name, ""


def get_real_winner(row):
    estado = row.get("estado_partido", "")

    if estado != "FINAL":
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

    return ""


def infer_winner_from_future_matches(rows):
    """
    Si un partido eliminatorio terminó empatado y la hoja no trae penales,
    intentamos inferir quién avanzó viendo quién aparece en partidos posteriores.
    No inventa penales; solo completa ganador_real cuando es evidente.
    """
    future_teams_by_match = {}

    for row in rows:
        partido_id = str(row["partido_id"]).strip()
        teams = set()

        for col in ["equipo_a", "equipo_b"]:
            team = clean_text(row.get(col, ""))

            if team:
                teams.add(team)

        future_teams_by_match[partido_id] = teams

    for idx, row in enumerate(rows):
        if row.get("estado_partido") != "FINAL":
            continue

        if not is_knockout_phase(row.get("fase", "")):
            continue

        if clean_text(row.get("ganador_real", "")):
            continue

        equipo_a = clean_text(row.get("equipo_a", ""))
        equipo_b = clean_text(row.get("equipo_b", ""))

        goles_a = to_number(row.get("goles_real_a", ""))
        goles_b = to_number(row.get("goles_real_b", ""))

        if goles_a is None or goles_b is None:
            continue

        if goles_a != goles_b:
            continue

        partido_actual = int(row["partido_id"])

        aparece_a = False
        aparece_b = False

        for other in rows:
            try:
                partido_futuro = int(other["partido_id"])
            except Exception:
                continue

            if partido_futuro <= partido_actual:
                continue

            equipos_futuros = {
                clean_text(other.get("equipo_a", "")),
                clean_text(other.get("equipo_b", "")),
            }

            if equipo_a in equipos_futuros:
                aparece_a = True

            if equipo_b in equipos_futuros:
                aparece_b = True

        if aparece_a and not aparece_b:
            rows[idx]["ganador_real"] = equipo_a

        if aparece_b and not aparece_a:
            rows[idx]["ganador_real"] = equipo_b

    return rows


def build_dim_calendar(df_source):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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

    missing = [col for col in required if col not in df_source.columns]

    if missing:
        raise ValueError(
            f"No se puede crear {OUTPUT_SHEET}. "
            f"Faltan columnas en {SOURCE_SHEET}: {missing}. "
            f"Columnas disponibles: {list(df_source.columns)}"
        )

    rows = []

    for _, row in df_source.iterrows():
        partido_id = clean_text(row.get("match_id", ""))

        if is_blank(partido_id):
            continue

        equipo_a, origen_a = get_team_or_origin(
            row.get("equipo_a", ""),
            row.get("codigo_a", ""),
        )

        equipo_b, origen_b = get_team_or_origin(
            row.get("equipo_b", ""),
            row.get("codigo_b", ""),
        )

        estado_partido = normalize_estado(row.get("estado", ""))

        goles_real_a = ""
        goles_real_b = ""

        if estado_partido == "FINAL":
            goles_real_a = row.get("goles_a", "")
            goles_real_b = row.get("goles_b", "")

        output_row = {
            "partido_id": partido_id,
            "fecha": row.get("fecha", ""),
            "hora": row.get("hora", ""),
            "fase": row.get("fase", ""),
            "grupo": row.get("grupo", ""),
            "sede": row.get("sede", ""),
            "ciudad": row.get("ciudad", ""),
            "pais_sede": row.get("pais_sede", ""),
            "region_sede": row.get("region_sede", ""),
            "equipo_a": equipo_a,
            "codigo_a": row.get("codigo_a", ""),
            "equipo_b": equipo_b,
            "codigo_b": row.get("codigo_b", ""),
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
            "fixture_id_api": row.get("fixture_id_api", ""),
            "ultima_revision_api": row.get("ultima_revision_api", ""),
            "api_estado": row.get("api_estado", ""),
            "api_orientacion": row.get("api_orientacion", ""),
            "ultima_actualizacion_resultado": row.get("ultima_actualizacion_resultado", ""),
            "ultima_actualizacion_dim": now,
        }

        output_row["ganador_real"] = get_real_winner(output_row)

        rows.append(output_row)

    rows = infer_winner_from_future_matches(rows)

    df_output = pd.DataFrame(rows)

    for col in OUTPUT_COLUMNS:
        if col not in df_output.columns:
            df_output[col] = ""

    df_output = df_output[OUTPUT_COLUMNS]
    df_output = df_output.drop_duplicates(subset=["partido_id"], keep="first")

    return df_output


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
            f"Hay partido_id duplicados. Filas: {total}, IDs únicos: {unique_ids}."
        )

    min_id = pd.to_numeric(df["partido_id"], errors="coerce").min()
    max_id = pd.to_numeric(df["partido_id"], errors="coerce").max()

    if min_id != 1 or max_id != EXPECTED_MATCHES:
        raise ValueError(
            f"El calendario debe ir de 1 a {EXPECTED_MATCHES}. "
            f"MIN={min_id}, MAX={max_id}."
        )


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

    print("Construyendo dim_calendario_mundial_2026...")
    df_output = build_dim_calendar(df_source)

    print("Validando calendario...")
    validate_calendar(df_output)

    print(f"Escribiendo hoja: {OUTPUT_SHEET}")
    write_sheet(spreadsheet, OUTPUT_SHEET, df_output)

    finalizados = len(df_output[df_output["estado_partido"] == "FINAL"])
    pendientes = len(df_output[df_output["estado_partido"] == "PENDIENTE"])
    en_vivo = len(df_output[df_output["estado_partido"] == "EN VIVO"])

    print("--------------------------------")
    print("Calendario normalizado correctamente")
    print(f"Hoja fuente: {SOURCE_SHEET}")
    print(f"Hoja destino: {OUTPUT_SHEET}")
    print(f"Partidos totales: {len(df_output)}")
    print(f"Finalizados: {finalizados}")
    print(f"Pendientes: {pendientes}")
    print(f"En vivo: {en_vivo}")
    print("--------------------------------")


if __name__ == "__main__":
    main()
