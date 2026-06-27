"""
Cliente de Google Sheets para el proyecto Mundial 2026.

Este módulo permite:
- Conectarse a Google Sheets usando variables de entorno.
- Leer hojas como DataFrames.
- Sobrescribir hojas completas.
- Agregar filas a una hoja tipo histórico/snapshot.

No contiene credenciales reales.
"""

import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

from src.config import (
    SPREADSHEET_ID,
    GOOGLE_CLIENT_EMAIL,
    GOOGLE_PRIVATE_KEY,
    validar_configuracion,
)


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def crear_cliente_gspread():
    """
    Crea un cliente de gspread usando credenciales desde variables de entorno.
    """
    validar_configuracion()

    private_key = GOOGLE_PRIVATE_KEY.replace("\\n", "\n")

    service_account_info = {
        "type": "service_account",
        "project_id": "mundial-2026-pipeline",
        "private_key_id": "not_required_from_env",
        "private_key": private_key,
        "client_email": GOOGLE_CLIENT_EMAIL,
        "client_id": "not_required_from_env",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": "",
    }

    credentials = Credentials.from_service_account_info(
        service_account_info,
        scopes=SCOPES,
    )

    return gspread.authorize(credentials)


def abrir_spreadsheet():
    """
    Abre el Google Sheet principal del proyecto.
    """
    cliente = crear_cliente_gspread()
    return cliente.open_by_key(SPREADSHEET_ID)


def leer_hoja(nombre_hoja):
    """
    Lee una hoja de Google Sheets y devuelve un DataFrame.
    """
    sh = abrir_spreadsheet()
    ws = sh.worksheet(nombre_hoja)

    data = ws.get_all_records()
    df = pd.DataFrame(data)

    df.columns = [str(c).strip() for c in df.columns]

    return df


def asegurar_hoja(nombre_hoja, filas=1000, columnas=30):
    """
    Crea la hoja si no existe.
    """
    sh = abrir_spreadsheet()

    try:
        ws = sh.worksheet(nombre_hoja)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(
            title=nombre_hoja,
            rows=filas,
            cols=columnas,
        )

    return ws


def escribir_df_en_hoja(df, nombre_hoja):
    """
    Sobrescribe una hoja completa con el contenido del DataFrame.
    Se usará para fact_predicciones_2026.
    """
    ws = asegurar_hoja(
        nombre_hoja,
        filas=max(len(df) + 10, 1000),
        columnas=max(len(df.columns) + 5, 30),
    )

    ws.clear()

    valores = [df.columns.tolist()] + df.fillna("").astype(str).values.tolist()

    if len(valores) > 1:
        ws.update("A1", valores)
    else:
        ws.update("A1", [df.columns.tolist()])


def append_df_en_hoja(df, nombre_hoja):
    """
    Agrega filas nuevas al final de una hoja.
    Se usará para fact_predicciones_snapshot_2026.
    """
    if df.empty:
        print(f"No se agregaron filas a {nombre_hoja} porque el DataFrame está vacío.")
        return

    ws = asegurar_hoja(
        nombre_hoja,
        filas=max(len(df) + 1000, 1000),
        columnas=max(len(df.columns) + 5, 30),
    )

    existentes = ws.get_all_values()

    if not existentes:
        ws.update("A1", [df.columns.tolist()])
        ws.append_rows(
            df.fillna("").astype(str).values.tolist(),
            value_input_option="USER_ENTERED",
        )
        return

    encabezado_actual = existentes[0]
    encabezado_nuevo = encabezado_actual + [
        c for c in df.columns if c not in encabezado_actual
    ]

    if encabezado_nuevo != encabezado_actual:
        filas_anteriores = existentes[1:]
        filas_anteriores_ajustadas = [
            fila + [""] * (len(encabezado_nuevo) - len(fila))
            for fila in filas_anteriores
        ]

        ws.clear()
        ws.update("A1", [encabezado_nuevo] + filas_anteriores_ajustadas)
        encabezado_actual = encabezado_nuevo

    df_append = df.copy()

    for col in encabezado_actual:
        if col not in df_append.columns:
            df_append[col] = ""

    df_append = df_append[encabezado_actual]

    ws.append_rows(
        df_append.fillna("").astype(str).values.tolist(),
        value_input_option="USER_ENTERED",
    )
