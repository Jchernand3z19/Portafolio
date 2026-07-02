Estamos trabajando en el proyecto Mundial 2026.

Necesito crear el script:

scripts/04_crear_fact_partidos_prediccion_2026.py

Objetivo:
Crear o actualizar la hoja de Google Sheets:

fact_partidos_prediccion_2026

Esta tabla será la tabla maestra para el nuevo tab "Predicción Viva 2026".

La tabla debe tener una fila por partido del calendario 2026 y debe conservar separados:

1. Pronóstico inicial:
- goles_pred_inicial_a
- goles_pred_inicial_b
- ganador_pred_inicial
- confianza_pred_inicial

Este bloque se calcula una vez y NO debe sobrescribirse si ya existe.

2. Pronóstico vivo:
- goles_pred_vivo_a
- goles_pred_vivo_b
- ganador_pred_vivo
- confianza_pred_vivo

Este bloque se recalcula diariamente SOLO para partidos pendientes.

3. Resultado real:
- estado_partido
- goles_real_a
- goles_real_b
- penales_real_a
- penales_real_b
- ganador_real

Este bloque NO debe borrarse ni sobrescribirse si ya tiene datos.

4. Resultado usado para dashboard:
- estado_usado
- goles_usados_a
- goles_usados_b
- ganador_usado
- etiqueta_visual
- es_penales

Regla:
Si estado_partido es FINAL:
usar resultado real.
estado_usado = FINAL.
etiqueta_visual = FINAL o FINAL / PEN si hubo penales.

Si estado_partido no es FINAL:
usar pronóstico vivo.
Si no existe pronóstico vivo, usar pronóstico inicial.
estado_usado = PRED.
etiqueta_visual = PRED o PRED / PEN si es eliminatoria y hay empate definido por penales.

El script debe leer:
- fact_predicciones_2026
- ranking_equipos
- fact_resultados_recientes
- dim_equivalencias_selecciones

La fuente inicial de partidos debe ser fact_predicciones_2026, siempre que tenga columnas equivalentes a:
- partido_id
- fecha
- fase
- grupo
- equipo_a
- equipo_b
- goles_pred_a / goles_pred_b o columnas similares
- ganador_predicho
- confianza

Si fact_predicciones_2026 no tiene columnas suficientes para crear calendario por partido, el script debe detenerse y mostrar un error claro indicando qué columnas faltan.

Importante:
No borrar la hoja completa si ya existe con resultados reales.
Debe leer la hoja existente fact_partidos_prediccion_2026, preservar columnas reales y pronóstico inicial, y actualizar solo:
- pronóstico vivo de partidos pendientes
- estado_usado
- goles_usados
- ganador_usado
- etiqueta_visual
- ultima_actualizacion

Crear funciones limpias:
- get_client()
- read_sheet()
- write_sheet()
- normalize_columns()
- detectar_columnas_base()
- crear_base_partidos()
- merge_con_tabla_existente()
- recalcular_pronostico_vivo()
- aplicar_resultado_usado()
- main()

Usar pandas, gspread y google.oauth2.service_account.

Variables:
SPREADSHEET_ID desde variable de entorno.
GOOGLE_APPLICATION_CREDENTIALS desde variable de entorno o service_account.json.

Al finalizar imprimir:
- filas procesadas
- partidos pendientes
- partidos finalizados
- partidos con PRED
- partidos con FINAL
- hoja actualizada
