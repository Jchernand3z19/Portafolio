# Mundial 2026: análisis histórico y predicción

Proyecto de datos que combina análisis histórico, modelado predictivo, automatización y publicación web para explorar el Mundial 2026 desde una sola experiencia.

## Estado

**Publicado y operativo.** El repositorio conserva el código técnico, mientras que el dashboard se ejecuta como una aplicación web de Google Apps Script.

- [Abrir dashboard interactivo](https://script.google.com/macros/s/AKfycbzE26z7tcEbnwLPKSLLW8H_rK7UqwKV17rV8YBJVT4lB4slY0qorsf8cL4cnsys5ShGhw/exec)
- [Ver presentación dentro del portafolio](https://jchernand3z19.github.io/Portafolio/#proyectos)

## Problema abordado

La información histórica de los mundiales, el calendario de 2026, los rankings, la forma reciente y los resultados reales provienen de estructuras diferentes. Sin una capa común, comparar selecciones, actualizar predicciones y publicar resultados exige trabajo manual y genera riesgo de inconsistencias.

## Solución

El proyecto construye un flujo reproducible que:

1. Integra las fuentes históricas y actuales.
2. Limpia, homologa y valida los campos.
3. Calcula fortalezas y probabilidades de partido.
4. Genera predicciones iniciales y actualizaciones vivas.
5. Consolida las tablas utilizadas por el dashboard.
6. Publica una experiencia interactiva con vistas históricas y predictivas.

## Alcance analítico

- 7 ediciones históricas.
- 448 partidos.
- 69 selecciones.
- 3,953 jugadores.
- 1,136 goles.
- Indicadores de resultados, disciplina y rendimiento.
- Predicción inicial y predicción viva para 2026.

## Arquitectura

```text
Fuentes históricas y actuales
            ↓
Python: limpieza, validación y predicción
            ↓
Google Sheets: tablas y snapshots
            ↓
Google Apps Script: servicio y aplicación web
            ↓
Chart.js: indicadores y visualizaciones
```

## Estructura del proyecto

```text
mundial-2026-predicciones/
├── README.md
├── requirements.txt
├── scripts/             # Procesos ejecutables y tablas finales
├── src/                 # Configuración y componentes reutilizables
└── data/                # Datos locales permitidos o muestras, cuando aplique
```

La automatización se administra fuera de esta carpeta:

```text
.github/workflows/prediccion_viva_mundial_2026.yml
```

## Componentes principales

### Predicción

`01_prediccion_dinamica_2026.py` carga calendario, ranking y estadísticas para estimar fortalezas, goles esperados y probabilidades de los partidos.

### Tabla maestra

`04_crear_fact_partidos_prediccion_2026.py` integra calendario, predicción inicial, predicción viva y resultados reales en una estructura común.

### Configuración

`src/config.py` centraliza nombres de tablas, versión del modelo y variables requeridas por el pipeline.

### Acceso a Google Sheets

`src/sheets_client.py` encapsula autenticación y operaciones de lectura, escritura y anexado de DataFrames.

### Ejecución programada

El workflow `prediccion_viva_mundial_2026.yml` utiliza Python 3.11 y ejecuta la actualización diaria a las **6:30 a. m. de Honduras**. También puede iniciarse manualmente desde GitHub Actions.

## Configuración local

### 1. Crear un entorno virtual

```bash
python -m venv .venv
source .venv/bin/activate
```

En Windows:

```powershell
.venv\Scripts\activate
```

### 2. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 3. Definir variables de entorno

El proyecto utiliza variables como:

```text
SPREADSHEET_ID
GOOGLE_CLIENT_EMAIL
GOOGLE_PRIVATE_KEY
GOOGLE_APPLICATION_CREDENTIALS
MODEL_VERSION
ENVIRONMENT
```

Las credenciales reales no deben almacenarse en el repositorio.

### 4. Ejecutar los procesos

```bash
python scripts/04A_crear_dim_calendario_mundial_2026.py
python scripts/04_crear_fact_partidos_prediccion_2026.py
```

Cuando el proceso final esté disponible:

```bash
python scripts/05_crear_fact_prediccion_viva_2026.py
```

## Seguridad

- Las credenciales se leen desde variables de entorno o GitHub Secrets.
- Los IDs privados son sustituidos en los ejemplos publicados.
- El código mostrado en el portafolio utiliza versiones saneadas.
- `service_account.json` se crea únicamente durante la ejecución y no debe confirmarse en Git.

## Resultado

El proyecto demuestra un ciclo completo de datos: integración, transformación, análisis, modelado, automatización y publicación de una aplicación consumible por usuarios no técnicos.
