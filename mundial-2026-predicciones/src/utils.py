"""
Funciones auxiliares para limpieza y validación de datos
del proyecto Mundial 2026.
"""

import numpy as np
import pandas as pd


def limpiar_columnas(df):
    """
    Normaliza nombres de columnas:
    - quita espacios
    - convierte a minúsculas
    - reemplaza espacios por guiones bajos
    """
    df = df.copy()
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_", regex=False)
    )
    return df


def texto_limpio(x):
    """
    Convierte un valor a texto limpio.
    """
    if pd.isna(x):
        return ""
    return str(x).strip()


def numero(x, default=np.nan):
    """
    Convierte un valor a número decimal.
    """
    if pd.isna(x) or str(x).strip() == "":
        return default

    try:
        return float(str(x).replace(",", "").strip())
    except Exception:
        return default


def entero(x, default=np.nan):
    """
    Convierte un valor a entero.
    """
    val = numero(x, default)

    if pd.isna(val):
        return default

    return int(val)


def fecha_yyyy_mm_dd(x):
    """
    Convierte una fecha a formato datetime de pandas.
    """
    if pd.isna(x) or str(x).strip() == "":
        return pd.NaT

    return pd.to_datetime(x, errors="coerce")


def codigo_valido(codigo):
    """
    Valida si un código de selección es usable para predicción.
    """
    codigo = texto_limpio(codigo).upper()

    invalidos = [
        "",
        "TBD",
        "PENDIENTE",
        "GANADOR",
        "SEGUNDO",
        "TERCERO",
        "WINNER",
        "RUNNER",
        "3RD",
        "1ST",
        "2ND",
    ]

    if codigo in invalidos:
        return False

    if "TBD" in codigo:
        return False

    return True


def equipo_valido(nombre):
    """
    Valida si el nombre de un equipo ya está definido.
    """
    nombre = texto_limpio(nombre).upper()

    invalidos = [
        "",
        "TBD",
        "PENDIENTE",
        "GANADOR",
        "SEGUNDO",
        "TERCERO",
        "WINNER",
        "RUNNER",
        "3RD",
        "1ST",
        "2ND",
    ]

    if nombre in invalidos:
        return False

    if "TBD" in nombre:
        return False

    if "GANADOR" in nombre:
        return False

    if "TERCERO" in nombre:
        return False

    if "SEGUNDO" in nombre:
        return False

    return True


def normalizar_estado_partido(estado):
    """
    Normaliza estados de partido a:
    - Jugado
    - Programado
    - En vivo
    - Pendiente
    """
    estado_raw = texto_limpio(estado)
    estado_lower = estado_raw.lower().strip()

    if estado_lower in [
        "jugado",
        "finalizado",
        "finalizado ✅",
        "terminado",
        "complete",
        "completed",
        "finished",
        "final",
        "completo",
        "ft",
        "full time",
        "finalizado.",
        "terminado.",
    ]:
        return "Jugado"

    if estado_lower in [
        "en vivo",
        "live",
        "in progress",
        "jugando",
        "en juego",
        "1t",
        "2t",
        "primer tiempo",
        "segundo tiempo",
        "halftime",
        "medio tiempo",
    ]:
        return "En vivo"

    if estado_lower in [
        "programado",
        "scheduled",
        "fixture",
        "por jugar",
    ]:
        return "Programado"

    if estado_lower in [
        "pendiente",
        "pending",
        "tbd",
        "por definir",
    ]:
        return "Pendiente"

    return estado_raw


def detectar_estado_partido(row):
    """
    Detecta el estado del partido usando:
    - estado_partido si existe
    - estado si existe
    - status si existe
    - goles_a y goles_b si ya hay marcador
    - equipos/códigos definidos si está programado

    Nota:
    En el calendario actual del proyecto, la columna se llama 'estado'.
    Por eso esta función revisa 'estado_partido' y también 'estado'.
    """
    estado = texto_limpio(row.get("estado_partido", ""))

    if estado == "":
        estado = texto_limpio(row.get("estado", ""))

    if estado == "":
        estado = texto_limpio(row.get("status", ""))

    if estado != "":
        return normalizar_estado_partido(estado)

    goles_a = row.get("goles_a", "")
    goles_b = row.get("goles_b", "")

    tiene_goles = (
        texto_limpio(goles_a) != ""
        and texto_limpio(goles_b) != ""
    )

    if tiene_goles:
        return "Jugado"

    equipo_a = texto_limpio(row.get("equipo_a", ""))
    equipo_b = texto_limpio(row.get("equipo_b", ""))
    codigo_a = texto_limpio(row.get("codigo_a", ""))
    codigo_b = texto_limpio(row.get("codigo_b", ""))

    if (
        equipo_valido(equipo_a)
        and equipo_valido(equipo_b)
        and codigo_valido(codigo_a)
        and codigo_valido(codigo_b)
    ):
        return "Programado"

    return "Pendiente"
