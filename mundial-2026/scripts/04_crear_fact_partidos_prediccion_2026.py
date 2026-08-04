import math
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

CALENDAR_SHEET = "dim_calendario_mundial_2026"
RANKING_SHEET = "dim_ranking_equipos"
RECENT_RESULTS_SHEET = "fact_resultados_recientes"
EQUIVALENCES_SHEET = "dim_equivalencias_selecciones"
OUTPUT_SHEET = "fact_partidos_prediccion_2026"

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

    "ultima_actualizacion",
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
            cols=max(len(df.columns) + 5, 50),
        )
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(
            title=sheet_name,
            rows=max(len(df) + 50, 150),
            cols=max(len(df.columns) + 5, 50),
        )

    values = [df.columns.tolist()] + df.fillna("").astype(str).values.tolist()
    worksheet.update(values)


# =====================================================
# UTILIDADES GENERALES
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
    estado = clean_text(value).upper()

    if estado in [
        "FINAL",
        "FINALIZADO",
        "JUGADO",
        "COMPLETADO",
        "COMPLETE",
        "COMPLETED",
    ]:
        return "FINAL"

    if estado in [
        "EN VIVO",
        "LIVE",
        "PLAYING",
        "IN PROGRESS",
    ]:
        return "EN VIVO"

    return "PENDIENTE"


def es_fase_grupos(fase):
    fase = clean_key(fase)
    return "grupo" in fase or "group" in fase


def es_fase_eliminatoria(fase):
    return not es_fase_grupos(fase)


def is_tbd(value):
    if is_blank(value):
        return True

    value = clean_text(value).lower()

    return value in [
        "tbd",
        "por definir",
        "pendiente",
        "winner",
        "ganador",
        "loser",
        "perdedor",
        "-",
    ]


def looks_like_origin_text(value):
    value = clean_text(value)

    if is_blank(value):
        return False

    value_upper = value.upper()
    value_key = clean_key(value).upper()

    if re.match(r"^[WL]\d+$", value_upper):
        return True

    if re.match(r"^GANADOR_\d+$", value_key):
        return True

    if re.match(r"^PERDEDOR_\d+$", value_key):
        return True

    if re.match(r"^WINNER_\d+$", value_key):
        return True

    if re.match(r"^LOSER_\d+$", value_key):
        return True

    return False


def origin_from_text(value):
    value = clean_text(value)
    value_upper = value.upper()
    value_key = clean_key(value).upper()

    if re.match(r"^[WL]\d+$", value_upper):
        return value_upper

    match = re.search(r"GANADOR_(\d+)", value_key)
    if match:
        return f"W{match.group(1)}"

    match = re.search(r"WINNER_(\d+)", value_key)
    if match:
        return f"W{match.group(1)}"

    match = re.search(r"PERDEDOR_(\d+)", value_key)
    if match:
        return f"L{match.group(1)}"

    match = re.search(r"LOSER_(\d+)", value_key)
    if match:
        return f"L{match.group(1)}"

    return ""


# =====================================================
# DETECCIÓN DE COLUMNAS DEL CALENDARIO
# =====================================================

def detect_calendar_columns(df):
    cols = {
        "partido_id": find_col(df, [
            "partido_id",
            "match_id",
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
            "ronda",
            "round",
            "etapa",
        ]),
        "grupo": find_col(df, [
            "grupo",
            "group",
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
            "host_region",
            "region",
        ]),
        "equipo_a": find_col(df, [
            "equipo_a",
            "seleccion_a",
            "team_a",
            "local",
            "home_team",
            "pais_a",
        ]),
        "codigo_a": find_col(df, [
            "codigo_a",
            "code_a",
            "team_a_code",
            "codigo_equipo_a",
        ]),
        "equipo_b": find_col(df, [
            "equipo_b",
            "seleccion_b",
            "team_b",
            "visitante",
            "away_team",
            "pais_b",
        ]),
        "codigo_b": find_col(df, [
            "codigo_b",
            "code_b",
            "team_b_code",
            "codigo_equipo_b",
        ]),
        "origen_equipo_a": find_col(df, [
            "origen_equipo_a",
            "source_a",
            "slot_a",
            "clasificacion_a",
        ]),
        "origen_equipo_b": find_col(df, [
            "origen_equipo_b",
            "source_b",
            "slot_b",
            "clasificacion_b",
        ]),
        "siguiente_partido_id": find_col(df, [
            "siguiente_partido_id",
            "next_match_id",
            "partido_siguiente",
        ]),
        "slot_siguiente": find_col(df, [
            "slot_siguiente",
            "next_slot",
            "slot_next",
        ]),
        "estado_partido": find_col(df, [
            "estado_partido",
            "estado",
            "status",
            "match_status",
        ]),
        "goles_real_a": find_col(df, [
            "goles_real_a",
            "goles_a",
            "score_a",
            "home_score",
        ]),
        "goles_real_b": find_col(df, [
            "goles_real_b",
            "goles_b",
            "score_b",
            "away_score",
        ]),
        "penales_real_a": find_col(df, [
            "penales_real_a",
            "penales_a",
            "pens_a",
        ]),
        "penales_real_b": find_col(df, [
            "penales_real_b",
            "penales_b",
            "pens_b",
        ]),
        "ganador_real": find_col(df, [
            "ganador_real",
            "winner",
            "ganador",
            "winner_real",
        ]),
    }

    required = [
        "partido_id",
        "fecha",
        "fase",
        "equipo_a",
        "equipo_b",
    ]

    missing = [col for col in required if cols[col] is None]

    if missing:
        raise ValueError(
            f"No se puede usar {CALENDAR_SHEET}. "
            f"Faltan columnas: {missing}. "
            f"Columnas disponibles: {list(df.columns)}"
        )

    print("Columnas calendario detectadas:")

    for key, value in cols.items():
        print(f"- {key}: {value}")

    return cols


# =====================================================
# EQUIVALENCIAS DE NOMBRES
# =====================================================

def build_equivalence_map(df_equiv):
    mapping = {}

    if df_equiv.empty:
        return mapping

    df_equiv = normalize_columns(df_equiv)

    canonical_col = find_col(df_equiv, [
        "seleccion",
        "equipo",
        "nombre_estandar",
        "nombre_normalizado",
        "canonical",
        "pais",
    ])

    if canonical_col is None:
        return mapping

    for _, row in df_equiv.iterrows():
        canonical = clean_text(row.get(canonical_col, ""))

        if is_blank(canonical):
            continue

        for col in df_equiv.columns:
            value = clean_text(row.get(col, ""))

            if not is_blank(value):
                mapping[clean_key(value)] = canonical

    return mapping


def canonical_team(value, equivalences):
    value = clean_text(value)

    if is_blank(value) or is_tbd(value):
        return ""

    return equivalences.get(clean_key(value), value)


# =====================================================
# CALENDARIO BASE
# =====================================================

def get_real_winner(row):
    ganador_real = clean_text(row.get("ganador_real", ""))

    if not is_blank(ganador_real):
        return ganador_real

    goles_a = to_number(row.get("goles_real_a", ""))
    goles_b = to_number(row.get("goles_real_b", ""))

    if goles_a is None or goles_b is None:
        return ""

    if goles_a > goles_b:
        return clean_text(row.get("equipo_a", ""))

    if goles_b > goles_a:
        return clean_text(row.get("equipo_b", ""))

    penales_a = to_number(row.get("penales_real_a", ""))
    penales_b = to_number(row.get("penales_real_b", ""))

    if penales_a is not None and penales_b is not None:
        if penales_a > penales_b:
            return clean_text(row.get("equipo_a", ""))

        if penales_b > penales_a:
            return clean_text(row.get("equipo_b", ""))

    return ""


def build_calendar(df_calendar, cols, equivalences):
    rows = []

    for _, row in df_calendar.iterrows():
        partido_id = clean_text(row.get(cols["partido_id"], ""))

        raw_equipo_a = clean_text(row.get(cols["equipo_a"], ""))
        raw_equipo_b = clean_text(row.get(cols["equipo_b"], ""))

        codigo_a = clean_text(row.get(cols["codigo_a"], "")) if cols["codigo_a"] else ""
        codigo_b = clean_text(row.get(cols["codigo_b"], "")) if cols["codigo_b"] else ""

        origen_a = clean_text(row.get(cols["origen_equipo_a"], "")) if cols["origen_equipo_a"] else ""
        origen_b = clean_text(row.get(cols["origen_equipo_b"], "")) if cols["origen_equipo_b"] else ""

        if is_blank(origen_a) and looks_like_origin_text(raw_equipo_a):
            origen_a = origin_from_text(raw_equipo_a)
            equipo_a = ""
        elif is_blank(origen_a) and looks_like_origin_text(codigo_a):
            origen_a = origin_from_text(codigo_a)
            equipo_a = ""
        else:
            equipo_a = canonical_team(raw_equipo_a, equivalences)

        if is_blank(origen_b) and looks_like_origin_text(raw_equipo_b):
            origen_b = origin_from_text(raw_equipo_b)
            equipo_b = ""
        elif is_blank(origen_b) and looks_like_origin_text(codigo_b):
            origen_b = origin_from_text(codigo_b)
            equipo_b = ""
        else:
            equipo_b = canonical_team(raw_equipo_b, equivalences)

        estado_partido = normalize_estado(
            row.get(cols["estado_partido"], "PENDIENTE")
        ) if cols["estado_partido"] else "PENDIENTE"

        goles_real_a = row.get(cols["goles_real_a"], "") if cols["goles_real_a"] else ""
        goles_real_b = row.get(cols["goles_real_b"], "") if cols["goles_real_b"] else ""
        penales_real_a = row.get(cols["penales_real_a"], "") if cols["penales_real_a"] else ""
        penales_real_b = row.get(cols["penales_real_b"], "") if cols["penales_real_b"] else ""
        ganador_real = row.get(cols["ganador_real"], "") if cols["ganador_real"] else ""

        if estado_partido != "FINAL":
            goles_real_a = ""
            goles_real_b = ""
            penales_real_a = ""
            penales_real_b = ""
            ganador_real = ""

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
            "codigo_a": codigo_a,
            "equipo_b": equipo_b,
            "codigo_b": codigo_b,
            "origen_equipo_a": origen_a,
            "origen_equipo_b": origen_b,
            "siguiente_partido_id": row.get(cols["siguiente_partido_id"], "") if cols["siguiente_partido_id"] else "",
            "slot_siguiente": row.get(cols["slot_siguiente"], "") if cols["slot_siguiente"] else "",

            "estado_partido": estado_partido,
            "goles_real_a": goles_real_a,
            "goles_real_b": goles_real_b,
            "penales_real_a": penales_real_a,
            "penales_real_b": penales_real_b,
            "ganador_real": ganador_real,
        }

        output_row["ganador_real"] = get_real_winner(output_row)

        rows.append(output_row)

    df = pd.DataFrame(rows)
    df = df.drop_duplicates(subset=["partido_id"], keep="first")

    df["_orden"] = pd.to_numeric(df["partido_id"], errors="coerce")
    df = df.sort_values(["_orden", "partido_id"]).drop(columns=["_orden"])

    return df


def validate_calendar(df_calendar):
    total = len(df_calendar)

    if total != EXPECTED_MATCHES:
        raise ValueError(
            f"{CALENDAR_SHEET} tiene {total} partidos. "
            f"Se esperaban {EXPECTED_MATCHES}. "
            "No se crea la predicción viva hasta tener el calendario completo."
        )

    ids = df_calendar["partido_id"].astype(str).str.strip()

    if ids.eq("").any():
        raise ValueError("Hay partido_id vacíos en el calendario.")

    unique_ids = ids.nunique()

    if unique_ids != total:
        raise ValueError(
            f"Hay partido_id duplicados. "
            f"Filas: {total}, IDs únicos: {unique_ids}."
        )

    min_id = pd.to_numeric(df_calendar["partido_id"], errors="coerce").min()
    max_id = pd.to_numeric(df_calendar["partido_id"], errors="coerce").max()

    if min_id != 1 or max_id != EXPECTED_MATCHES:
        raise ValueError(
            f"El calendario debe ir de 1 a {EXPECTED_MATCHES}. "
            f"MIN={min_id}, MAX={max_id}."
        )


# =====================================================
# RANKING
# =====================================================

def detect_ranking_columns(df):
    team_col = find_col(df, [
        "seleccion",
        "equipo",
        "pais",
        "team",
        "country",
        "nombre",
    ])

    code_col = find_col(df, [
        "codigo",
        "code",
        "team_code",
        "codigo_fifa",
    ])

    rating_col = find_col(df, [
        "elo",
        "elo_rating",
        "ranking_elo",
        "rating",
        "puntos_fifa",
        "puntos",
        "score",
        "fuerza",
        "power_score",
        "strength",
    ])

    rank_col = find_col(df, [
        "ranking_fifa",
        "ranking",
        "rank",
        "posicion",
        "posicion_ranking",
    ])

    if team_col is None and code_col is None:
        raise ValueError(
            f"No se puede usar {RANKING_SHEET}. "
            f"Falta columna de equipo o código. "
            f"Columnas disponibles: {list(df.columns)}"
        )

    if rating_col is None and rank_col is None:
        raise ValueError(
            f"No se puede usar {RANKING_SHEET}. "
            f"Falta columna de fuerza/rating o ranking. "
            f"Columnas disponibles: {list(df.columns)}"
        )

    return team_col, code_col, rating_col, rank_col


def build_ranking_strength(df_ranking, equivalences):
    if df_ranking.empty:
        raise ValueError(f"La hoja {RANKING_SHEET} está vacía o no existe.")

    df_ranking = normalize_columns(df_ranking)
    team_col, code_col, rating_col, rank_col = detect_ranking_columns(df_ranking)

    raw = []

    for _, row in df_ranking.iterrows():
        team = canonical_team(row.get(team_col, ""), equivalences) if team_col else ""
        code = clean_text(row.get(code_col, "")) if code_col else ""

        if is_blank(team) and not is_blank(code):
            team = equivalences.get(clean_key(code), code)

        if is_blank(team):
            continue

        rating = to_number(row.get(rating_col, "")) if rating_col else None
        rank = to_number(row.get(rank_col, "")) if rank_col else None

        raw.append({
            "equipo": team,
            "codigo": code,
            "rating": rating,
            "rank": rank,
        })

    df = pd.DataFrame(raw)

    if df.empty:
        raise ValueError(f"No se pudo construir ranking desde {RANKING_SHEET}.")

    if df["rating"].notna().any():
        min_rating = df["rating"].min()
        max_rating = df["rating"].max()
        span = max(max_rating - min_rating, 1)

        df["strength"] = 50 + ((df["rating"] - min_rating) / span) * 50
    else:
        max_rank = max(df["rank"].max(), 1)

        df["strength"] = 100 - ((df["rank"] - 1) / max(max_rank - 1, 1)) * 50

    strength = {}

    for _, row in df.iterrows():
        team = clean_text(row["equipo"])
        code = clean_text(row["codigo"])

        strength[team] = float(row["strength"])

        if not is_blank(code):
            strength[code] = float(row["strength"])

    return strength


# =====================================================
# RESULTADOS RECIENTES
# =====================================================

def detect_recent_result_columns(df):
    return {
        "equipo_a": find_col(df, [
            "equipo_a",
            "seleccion_a",
            "team_a",
            "local",
            "home_team",
            "pais_a",
        ]),
        "equipo_b": find_col(df, [
            "equipo_b",
            "seleccion_b",
            "team_b",
            "visitante",
            "away_team",
            "pais_b",
        ]),
        "goles_a": find_col(df, [
            "goles_a",
            "score_a",
            "goles_equipo_a",
            "home_score",
            "gf_a",
        ]),
        "goles_b": find_col(df, [
            "goles_b",
            "score_b",
            "goles_equipo_b",
            "away_score",
            "gf_b",
        ]),
    }


def build_recent_form(df_results, equivalences):
    if df_results.empty:
        print(f"Advertencia: {RECENT_RESULTS_SHEET} está vacía. Se usará solo ranking.")
        return {}

    df_results = normalize_columns(df_results)
    cols = detect_recent_result_columns(df_results)

    if not all(cols.values()):
        print(
            f"Advertencia: {RECENT_RESULTS_SHEET} no tiene columnas suficientes. "
            "Se ignora forma reciente."
        )
        return {}

    stats = {}

    for _, row in df_results.iterrows():
        equipo_a = canonical_team(row.get(cols["equipo_a"], ""), equivalences)
        equipo_b = canonical_team(row.get(cols["equipo_b"], ""), equivalences)
        goles_a = to_number(row.get(cols["goles_a"], ""))
        goles_b = to_number(row.get(cols["goles_b"], ""))

        if (
            is_blank(equipo_a)
            or is_blank(equipo_b)
            or goles_a is None
            or goles_b is None
        ):
            continue

        for equipo in [equipo_a, equipo_b]:
            if equipo not in stats:
                stats[equipo] = {
                    "pj": 0,
                    "pts": 0,
                    "gd": 0,
                }

        if goles_a > goles_b:
            pts_a, pts_b = 3, 0
        elif goles_b > goles_a:
            pts_a, pts_b = 0, 3
        else:
            pts_a, pts_b = 1, 1

        stats[equipo_a]["pj"] += 1
        stats[equipo_a]["pts"] += pts_a
        stats[equipo_a]["gd"] += goles_a - goles_b

        stats[equipo_b]["pj"] += 1
        stats[equipo_b]["pts"] += pts_b
        stats[equipo_b]["gd"] += goles_b - goles_a

    form = {}

    for equipo, values in stats.items():
        if values["pj"] == 0:
            continue

        pts_ppg = values["pts"] / values["pj"]
        gd_ppg = values["gd"] / values["pj"]

        form[equipo] = (pts_ppg - 1.2) * 4 + gd_ppg * 2

    return form


# =====================================================
# MODELO DE PREDICCIÓN
# =====================================================

def get_strength(team, ranking_strength, recent_form):
    if is_blank(team):
        return None

    base = ranking_strength.get(team)

    if base is None:
        base = ranking_strength.get(clean_text(team).upper())

    if base is None:
        base = 55.0

    form = recent_form.get(team, 0.0)

    return base + form


def predict_match(equipo_a, equipo_b, fase, ranking_strength, recent_form):
    if is_blank(equipo_a) or is_blank(equipo_b):
        return {
            "goles_a": "",
            "goles_b": "",
            "ganador": "",
            "confianza": "",
            "penales_a": "",
            "penales_b": "",
            "ganador_penales": "",
        }

    strength_a = get_strength(equipo_a, ranking_strength, recent_form)
    strength_b = get_strength(equipo_b, ranking_strength, recent_form)

    diff = strength_a - strength_b

    goles_a = max(0.15, min(4.25, 1.25 + diff / 35))
    goles_b = max(0.15, min(4.25, 1.25 - diff / 35))

    goles_a = round(goles_a, 3)
    goles_b = round(goles_b, 3)

    if goles_a > goles_b:
        ganador = equipo_a
    elif goles_b > goles_a:
        ganador = equipo_b
    else:
        ganador = equipo_a if strength_a >= strength_b else equipo_b

    prob_fav = 1 / (1 + math.exp(-abs(diff) / 12))

    if prob_fav >= 0.72:
        confianza = "Alta"
    elif prob_fav >= 0.60:
        confianza = "Media"
    else:
        confianza = "Baja"

    penales_a = ""
    penales_b = ""
    ganador_penales = ""

    if es_fase_eliminatoria(fase) and goles_a == goles_b:
        ganador_penales = ganador

        if ganador == equipo_a:
            penales_a, penales_b = 4, 3
        else:
            penales_a, penales_b = 3, 4

    return {
        "goles_a": goles_a,
        "goles_b": goles_b,
        "ganador": ganador,
        "confianza": confianza,
        "penales_a": penales_a,
        "penales_b": penales_b,
        "ganador_penales": ganador_penales,
    }


# =====================================================
# CONSERVAR DATOS EXISTENTES
# =====================================================

def partido_finalizado(row):
    estado = normalize_estado(row.get("estado_partido", ""))

    if estado == "FINAL":
        return True

    goles_real_a = row.get("goles_real_a", "")
    goles_real_b = row.get("goles_real_b", "")

    return not is_blank(goles_real_a) and not is_blank(goles_real_b)


def existing_table_is_complete(df_existing):
    if df_existing.empty:
        return False

    df_existing = normalize_columns(df_existing)

    if "partido_id" not in df_existing.columns:
        return False

    ids = df_existing["partido_id"].astype(str).str.strip()
    ids = ids[ids != ""]

    return ids.nunique() == EXPECTED_MATCHES


def merge_existing(df_base, df_existing):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for col in OUTPUT_COLUMNS:
        if col not in df_base.columns:
            df_base[col] = ""

    preserve_initial_predictions = existing_table_is_complete(df_existing)

    if df_existing.empty:
        df_base["ultima_actualizacion"] = now
        return df_base[OUTPUT_COLUMNS]

    df_existing = normalize_columns(df_existing)

    for col in OUTPUT_COLUMNS:
        if col not in df_existing.columns:
            df_existing[col] = ""

    existing_map = {
        clean_text(row.get("partido_id", "")): row.to_dict()
        for _, row in df_existing.iterrows()
        if not is_blank(row.get("partido_id", ""))
    }

    if preserve_initial_predictions:
        print("Tabla existente completa: se conservan pronósticos iniciales.")
    else:
        print(
            "Tabla existente incompleta: NO se conservan pronósticos iniciales "
            "para evitar arrastrar una corrida vieja incompleta."
        )

    preserve_initial = [
        "goles_pred_inicial_a",
        "goles_pred_inicial_b",
        "ganador_pred_inicial",
        "confianza_pred_inicial",
        "penales_pred_inicial_a",
        "penales_pred_inicial_b",
        "ganador_penales_pred_inicial",
    ]

    preserve_real = [
        "estado_partido",
        "goles_real_a",
        "goles_real_b",
        "penales_real_a",
        "penales_real_b",
        "ganador_real",
    ]

    preserve_vivo_if_final = [
        "goles_pred_vivo_a",
        "goles_pred_vivo_b",
        "ganador_pred_vivo",
        "confianza_pred_vivo",
        "penales_pred_vivo_a",
        "penales_pred_vivo_b",
        "ganador_penales_pred_vivo",
    ]

    rows = []

    for _, base_row in df_base.iterrows():
        partido_id = clean_text(base_row.get("partido_id", ""))
        new = base_row.to_dict()

        if partido_id in existing_map:
            old = existing_map[partido_id]

            if preserve_initial_predictions:
                for col in preserve_initial:
                    if not is_blank(old.get(col, "")):
                        new[col] = old.get(col, "")

            for col in preserve_real:
                if not is_blank(old.get(col, "")):
                    new[col] = old.get(col, "")

            if partido_finalizado(old):
                for col in preserve_vivo_if_final:
                    if not is_blank(old.get(col, "")):
                        new[col] = old.get(col, "")

        if is_blank(new.get("estado_partido", "")):
            new["estado_partido"] = "PENDIENTE"

        new["ultima_actualizacion"] = now

        rows.append(new)

    return pd.DataFrame(rows)[OUTPUT_COLUMNS]


# =====================================================
# TABLA DE GRUPOS
# =====================================================

def init_standings():
    return {}


def ensure_team_standing(standings, group, team):
    if is_blank(group) or is_blank(team):
        return

    group = clean_text(group).upper()

    if group not in standings:
        standings[group] = {}

    if team not in standings[group]:
        standings[group][team] = {
            "pj": 0,
            "pts": 0,
            "gf": 0.0,
            "gc": 0.0,
            "gd": 0.0,
        }


def add_group_result(standings, group, equipo_a, equipo_b, goles_a, goles_b):
    goles_a = to_number(goles_a)
    goles_b = to_number(goles_b)

    if goles_a is None or goles_b is None:
        return

    ensure_team_standing(standings, group, equipo_a)
    ensure_team_standing(standings, group, equipo_b)

    group = clean_text(group).upper()

    if goles_a > goles_b:
        pts_a, pts_b = 3, 0
    elif goles_b > goles_a:
        pts_a, pts_b = 0, 3
    else:
        pts_a, pts_b = 1, 1

    standings[group][equipo_a]["pj"] += 1
    standings[group][equipo_a]["pts"] += pts_a
    standings[group][equipo_a]["gf"] += goles_a
    standings[group][equipo_a]["gc"] += goles_b
    standings[group][equipo_a]["gd"] += goles_a - goles_b

    standings[group][equipo_b]["pj"] += 1
    standings[group][equipo_b]["pts"] += pts_b
    standings[group][equipo_b]["gf"] += goles_b
    standings[group][equipo_b]["gc"] += goles_a
    standings[group][equipo_b]["gd"] += goles_b - goles_a


# =====================================================
# RESOLUCIÓN DE ORÍGENES
# =====================================================

def get_match_by_id(processed_rows, partido_id):
    partido_id = clean_text(partido_id)

    for row in processed_rows:
        if clean_text(row.get("partido_id", "")) == partido_id:
            return row

    return None


def get_loser(row):
    if row is None:
        return ""

    ganador = clean_text(row.get("ganador_usado", ""))
    equipo_a = clean_text(row.get("equipo_a", ""))
    equipo_b = clean_text(row.get("equipo_b", ""))

    if is_blank(ganador):
        return ""

    if clean_key(ganador) == clean_key(equipo_a):
        return equipo_b

    if clean_key(ganador) == clean_key(equipo_b):
        return equipo_a

    return ""


def parse_match_reference(origin):
    text = clean_text(origin)

    patterns = [
        r"\b[Ww](\d+)\b",
        r"winner\s*(?:of)?\s*(\d+)",
        r"ganador\s*(?:del|de)?\s*(?:partido)?\s*(\d+)",
        r"\b[Ll](\d+)\b",
        r"loser\s*(?:of)?\s*(\d+)",
        r"perdedor\s*(?:del|de)?\s*(?:partido)?\s*(\d+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)

        if match:
            is_loser = (
                "loser" in text.lower()
                or "perdedor" in text.lower()
                or re.search(r"\b[Ll]\d+\b", text) is not None
            )

            return "L" if is_loser else "W", match.group(1)

    return "", ""


def resolve_origin(origin, processed_rows):
    if is_blank(origin):
        return ""

    ref_type, match_id = parse_match_reference(origin)

    if not ref_type or not match_id:
        return ""

    match = get_match_by_id(processed_rows, match_id)

    if match is None:
        return ""

    if ref_type == "W":
        return clean_text(match.get("ganador_usado", ""))

    return get_loser(match)


# =====================================================
# RESULTADO USADO
# =====================================================

def apply_used_result(row):
    row = dict(row)

    if partido_finalizado(row):
        penales_a = row.get("penales_real_a", "")
        penales_b = row.get("penales_real_b", "")
        has_pens = not is_blank(penales_a) and not is_blank(penales_b)

        winner = get_real_winner(row)

        row["estado_partido"] = "FINAL"
        row["estado_usado"] = "FINAL"
        row["goles_usados_a"] = row.get("goles_real_a", "")
        row["goles_usados_b"] = row.get("goles_real_b", "")
        row["penales_usados_a"] = penales_a if has_pens else ""
        row["penales_usados_b"] = penales_b if has_pens else ""
        row["ganador_usado"] = winner
        row["ganador_real"] = winner
        row["es_penales"] = "SI" if has_pens else "NO"
        row["etiqueta_visual"] = "FINAL / PEN" if has_pens else "FINAL"

        return row

    penales_a = row.get("penales_pred_vivo_a", "")
    penales_b = row.get("penales_pred_vivo_b", "")
    has_pens = not is_blank(penales_a) and not is_blank(penales_b)

    row["estado_partido"] = normalize_estado(row.get("estado_partido", "PENDIENTE"))
    row["estado_usado"] = "PRED"
    row["goles_usados_a"] = row.get("goles_pred_vivo_a", "")
    row["goles_usados_b"] = row.get("goles_pred_vivo_b", "")
    row["penales_usados_a"] = penales_a if has_pens else ""
    row["penales_usados_b"] = penales_b if has_pens else ""
    row["ganador_usado"] = row.get("ganador_pred_vivo", "")
    row["es_penales"] = "SI" if has_pens else "NO"
    row["etiqueta_visual"] = "PRED / PEN" if has_pens else "PRED"

    return row


# =====================================================
# CÁLCULO PRINCIPAL
# =====================================================

def calculate_predictions(df, ranking_strength, recent_form):
    standings = init_standings()
    processed_rows = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for _, source_row in df.iterrows():
        row = source_row.to_dict()

        equipo_a = clean_text(row.get("equipo_a", ""))
        equipo_b = clean_text(row.get("equipo_b", ""))

        if is_tbd(equipo_a):
            equipo_a = resolve_origin(
                row.get("origen_equipo_a", ""),
                processed_rows,
            )

        if is_tbd(equipo_b):
            equipo_b = resolve_origin(
                row.get("origen_equipo_b", ""),
                processed_rows,
            )

        row["equipo_a"] = equipo_a
        row["equipo_b"] = equipo_b

        final = partido_finalizado(row)

        pred = predict_match(
            equipo_a,
            equipo_b,
            row.get("fase", ""),
            ranking_strength,
            recent_form,
        )

        if is_blank(row.get("goles_pred_inicial_a", "")):
            row["goles_pred_inicial_a"] = pred["goles_a"]
            row["goles_pred_inicial_b"] = pred["goles_b"]
            row["ganador_pred_inicial"] = pred["ganador"]
            row["confianza_pred_inicial"] = pred["confianza"]
            row["penales_pred_inicial_a"] = pred["penales_a"]
            row["penales_pred_inicial_b"] = pred["penales_b"]
            row["ganador_penales_pred_inicial"] = pred["ganador_penales"]

        if final:
            if is_blank(row.get("goles_pred_vivo_a", "")):
                row["goles_pred_vivo_a"] = pred["goles_a"]
                row["goles_pred_vivo_b"] = pred["goles_b"]
                row["ganador_pred_vivo"] = pred["ganador"]
                row["confianza_pred_vivo"] = pred["confianza"]
                row["penales_pred_vivo_a"] = pred["penales_a"]
                row["penales_pred_vivo_b"] = pred["penales_b"]
                row["ganador_penales_pred_vivo"] = pred["ganador_penales"]
        else:
            row["goles_pred_vivo_a"] = pred["goles_a"]
            row["goles_pred_vivo_b"] = pred["goles_b"]
            row["ganador_pred_vivo"] = pred["ganador"]
            row["confianza_pred_vivo"] = pred["confianza"]
            row["penales_pred_vivo_a"] = pred["penales_a"]
            row["penales_pred_vivo_b"] = pred["penales_b"]
            row["ganador_penales_pred_vivo"] = pred["ganador_penales"]

        row = apply_used_result(row)
        row["ultima_actualizacion"] = now

        processed_rows.append(row)

        if es_fase_grupos(row.get("fase", "")):
            add_group_result(
                standings,
                row.get("grupo", ""),
                row.get("equipo_a", ""),
                row.get("equipo_b", ""),
                row.get("goles_usados_a", ""),
                row.get("goles_usados_b", ""),
            )

    return pd.DataFrame(processed_rows)


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

    print(f"Leyendo calendario oficial normalizado: {CALENDAR_SHEET}")
    df_calendar_raw = read_sheet(spreadsheet, CALENDAR_SHEET)

    if df_calendar_raw.empty:
        raise ValueError(
            f"No existe o está vacía la hoja {CALENDAR_SHEET}. "
            "Primero se debe crear dim_calendario_mundial_2026 desde "
            "Calendario Mundial 2026 - Data Matrix."
        )

    df_calendar_raw = normalize_columns(df_calendar_raw)
    calendar_cols = detect_calendar_columns(df_calendar_raw)

    print(f"Leyendo equivalencias: {EQUIVALENCES_SHEET}")
    df_equiv = read_sheet(spreadsheet, EQUIVALENCES_SHEET)
    equivalences = build_equivalence_map(df_equiv)

    print("Construyendo calendario base...")
    df_calendar = build_calendar(df_calendar_raw, calendar_cols, equivalences)

    print("Validando calendario base...")
    validate_calendar(df_calendar)

    print(f"Leyendo ranking: {RANKING_SHEET}")
    df_ranking = read_sheet(spreadsheet, RANKING_SHEET)
    ranking_strength = build_ranking_strength(df_ranking, equivalences)

    print(f"Leyendo resultados recientes: {RECENT_RESULTS_SHEET}")
    df_recent = read_sheet(spreadsheet, RECENT_RESULTS_SHEET)
    recent_form = build_recent_form(df_recent, equivalences)

    print(f"Leyendo tabla existente: {OUTPUT_SHEET}")
    df_existing = read_sheet(spreadsheet, OUTPUT_SHEET)

    print("Uniendo calendario con datos existentes conservados...")
    df_work = merge_existing(df_calendar, df_existing)

    print("Calculando predicción inicial/viva desde calendario + ranking + resultados recientes...")
    df_final = calculate_predictions(
        df_work,
        ranking_strength,
        recent_form,
    )

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

    unresolved = len(
        df_final[
            (df_final["equipo_a"].astype(str).str.strip() == "")
            | (df_final["equipo_b"].astype(str).str.strip() == "")
        ]
    )

    print("--------------------------------")
    print("Tabla actualizada correctamente")
    print(f"Hoja: {OUTPUT_SHEET}")
    print(f"Filas procesadas: {total}")
    print(f"Partidos con FINAL: {finalizados}")
    print(f"Partidos con PRED: {pred}")
    print(f"Partidos con PEN: {penales}")
    print(f"Partidos con equipos no resueltos: {unresolved}")
    print("--------------------------------")


if __name__ == "__main__":
    main()
