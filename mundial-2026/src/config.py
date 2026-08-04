"""
Configuración del proyecto Mundial 2026.

Este archivo lee variables de entorno.
No colocar credenciales reales dentro del código.
"""

import os


# ============================================================
# VARIABLES DE ENTORNO / CREDENCIALES
# ============================================================

SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID", "")

GOOGLE_CLIENT_EMAIL = os.environ.get("GOOGLE_CLIENT_EMAIL", "")
GOOGLE_PRIVATE_KEY = os.environ.get("GOOGLE_PRIVATE_KEY", "")

MODEL_VERSION = os.environ.get("MODEL_VERSION", "v1.1")
ENVIRONMENT = os.environ.get("ENVIRONMENT", "development")


# ============================================================
# TABLAS DE ENTRADA
# ============================================================

TAB_CALENDARIO = "Calendario Mundial 2026 - Data Matrix"
TAB_RANKING = "dim_ranking_equipos"
TAB_RESULTADOS = "fact_resultados_recientes"
TAB_EQUIVALENCIAS = "dim_equivalencias_selecciones"


# ============================================================
# TABLAS DE SALIDA - PREDICCIÓN DINÁMICA
# ============================================================

TAB_SALIDA = "fact_predicciones_2026"
TAB_SNAPSHOT = "fact_predicciones_snapshot_2026"
TAB_VALIDACION = "fact_validacion_predicciones_2026"


# ============================================================
# TABLAS DE SALIDA - PREDICCIÓN COMPLETA BASE
# ============================================================

TAB_PREDICCION_COMPLETA = "fact_prediccion_completa_2026"
TAB_TABLA_GRUPOS_PREDICHA = "fact_tabla_grupos_predicha_2026"
TAB_CAMINO_PREDICHO = "fact_camino_predicho_2026"


# ============================================================
# TABLAS DE CONTROL / LOGS
# ============================================================

TAB_LOGS = "_logs_mundial_2026"


# ============================================================
# MODELO
# ============================================================

MODELO_NOMBRE = (
    "Poisson ajustado por ranking FIFA, Elo, forma reciente "
    "y partidos jugados del Mundial 2026"
)


# ============================================================
# VALIDACIÓN DE CONFIGURACIÓN
# ============================================================

def validar_configuracion():
    """
    Valida que existan las variables necesarias para ejecutar el pipeline.
    """
    faltantes = []

    if not SPREADSHEET_ID:
        faltantes.append("SPREADSHEET_ID")

    if not GOOGLE_CLIENT_EMAIL:
        faltantes.append("GOOGLE_CLIENT_EMAIL")

    if not GOOGLE_PRIVATE_KEY:
        faltantes.append("GOOGLE_PRIVATE_KEY")

    if faltantes:
        raise ValueError(
            "Faltan variables de entorno requeridas: "
            + ", ".join(faltantes)
        )
