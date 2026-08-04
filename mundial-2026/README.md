# Mundial 2026: análisis histórico y predicción

Proyecto de datos que combina análisis histórico, modelado predictivo, automatización y publicación web para explorar el Mundial 2026 desde una sola experiencia.

## Estado

**Publicado y operativo.** El dashboard se ejecuta como una aplicación web de Google Apps Script y el código técnico se conserva en esta carpeta.

- [Abrir dashboard interactivo](https://script.google.com/macros/s/AKfycbzE26z7tcEbnwLPKSLLW8H_rK7UqwKV17rV8YBJVT4lB4slY0qorsf8cL4cnsys5ShGhw/exec)
- [Ver presentación en el portafolio](https://jchernand3z19.github.io/Portafolio/#proyectos)

## Problema abordado

La información histórica de los mundiales, el calendario de 2026, los rankings, la forma reciente y los resultados reales provienen de estructuras diferentes. El proyecto los integra, normaliza y conecta con un modelo predictivo y una experiencia web.

## Solución

1. Integra fuentes históricas y actuales.
2. Limpia, homologa y valida campos.
3. Calcula fortalezas y probabilidades de partido.
4. Genera predicciones iniciales y actualizaciones vivas.
5. Consolida las tablas utilizadas por el dashboard.
6. Publica vistas históricas y predictivas.

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

## Estructura

```text
mundial-2026/
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── portfolio/
│   ├── mundial-2026.js
│   ├── mundial-2026.css
│   └── assets/
│       ├── mundial-dashboard-preview.svg
│       └── dashboard/
├── dashboard/
│   └── apps-script/
├── scripts/
│   ├── 01_prediccion_dinamica_2026.py
│   ├── 02_validacion_predicciones_2026.py
│   ├── 03_prediccion_completa_2026.py
│   ├── 04A_crear_dim_calendario_mundial_2026.py
│   └── 04_crear_fact_partidos_prediccion_2026.py
└── src/
    ├── config.py
    ├── modelo_poisson.py
    ├── sheets_client.py
    └── utils.py
```

Los workflows ejecutables permanecen en `.github/workflows/` porque GitHub exige esa ubicación:

- `mundial-2026-prediccion-diaria.yml`
- `mundial-2026-prediccion-completa.yml`
- `mundial-2026-prediccion-viva.yml`

## Configuración local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

En Windows:

```powershell
.venv\Scripts\activate
pip install -r requirements.txt
```

Variables utilizadas:

```text
SPREADSHEET_ID
GOOGLE_CLIENT_EMAIL
GOOGLE_PRIVATE_KEY
GOOGLE_APPLICATION_CREDENTIALS
MODEL_VERSION
ENVIRONMENT
```

Las credenciales reales no deben almacenarse en Git.

## Ejecución

```bash
python scripts/01_prediccion_dinamica_2026.py
python scripts/02_validacion_predicciones_2026.py
python scripts/03_prediccion_completa_2026.py
python scripts/04A_crear_dim_calendario_mundial_2026.py
python scripts/04_crear_fact_partidos_prediccion_2026.py
```

## Seguridad

- Las credenciales se leen desde variables de entorno o GitHub Secrets.
- Los IDs privados se sustituyen en los ejemplos publicados.
- El código de Apps Script mostrado en el portafolio está saneado.
- `service_account.json` se genera únicamente durante la ejecución.
