# Precios de Supermercados de San Pedro Sula

Fundación técnica para recolectar, normalizar, validar y conservar cambios relevantes de precios y disponibilidad de supermercados con alcance inicial en San Pedro Sula.

## Estado

**En desarrollo — fase de fundación.**

Esta entrega define contratos, identificadores, reglas históricas, documentación y pruebas. No contiene un scraper real ni datos de supermercados.

## Problema

Los supermercados publican nombres, presentaciones, precios, promociones, disponibilidad y ubicaciones con estructuras distintas. Compararlos requiere separar fielmente la observación fuente de la normalización y mantener historial sin duplicar periodos idénticos.

## Objetivo

Establecer una base común que todos los extractores futuros deberán respetar y que pueda alimentar inicialmente Google Sheets y, cuando el proceso sea estable, BigQuery y Cloud Run. Power BI será el único dashboard.

## Alcance de esta fase

Incluye:

- contratos `RawProduct`, `NormalizedOffer` y `ValidatedOffer`;
- enums para disponibilidad, ubicación y tipo de llave fuente;
- identificadores deterministas;
- `state_hash` para detectar cambios históricos relevantes;
- contrato documental de ocho tabs futuras de Google Sheets;
- pruebas locales y GitHub Actions.

No incluye análisis de un supermercado, scraping, conexión a Google Sheets, ejecución diaria, BigQuery, Cloud Run, Power BI ni publicación de una tarjeta en el portafolio.

## Arquitectura aprobada

1. GitHub conserva código, documentación y cambios mediante Pull Request.
2. GitHub Actions ejecuta pruebas y, en fases futuras, los procesos programados.
3. Python realiza extracción, estandarización, validación y detección de cambios.
4. Google Sheets será almacenamiento temporal estructurado.
5. Power BI será el único dashboard.
6. BigQuery y Cloud Run se incorporarán después de estabilizar el proceso.

La IA puede ayudar a diagnosticar cambios estructurales, pero no modifica producción automáticamente.

## Estructura

```text
precios-supermercados-sps/
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── docs/
│   ├── arquitectura.md
│   ├── modelo-datos.md
│   └── decisiones-tecnicas.md
├── src/precios_supermercados/
│   ├── __init__.py
│   ├── enums.py
│   ├── identifiers.py
│   └── models.py
└── tests/
    ├── conftest.py
    ├── test_identifiers.py
    └── test_models.py
```

El workflow ejecutable vive en `.github/workflows/precios-supermercados-sps-tests.yml` por requisito de GitHub Actions.

## Contratos

- `RawProduct`: captura original y evidencia de ubicación sin normalizar.
- `NormalizedOffer`: identidad, producto normalizado, precio, disponibilidad y auditoría bajo un esquema común.
- `ValidatedOffer`: oferta normalizada, hash de estado y eventos de calidad, lista para persistencia.

Los detalles completos están en [`docs/modelo-datos.md`](docs/modelo-datos.md).

## Instalación y ejecución

Requiere Python 3.12 o superior.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r precios-supermercados-sps/requirements.txt
```

En Windows PowerShell, activa el entorno con:

```powershell
.venv\Scripts\Activate.ps1
```

## Pruebas

Desde la raíz del monorepositorio:

```bash
python -m compileall precios-supermercados-sps/src
pytest precios-supermercados-sps/tests
```

## Seguridad y privacidad

- `.env.example` contiene únicamente nombres de variables.
- `.env`, cuentas de servicio, llaves, cookies y credenciales están excluidas o prohibidas por la política del proyecto.
- No se incluyen datos personales ni empresariales privados.
- Los valores fuente de productos futuros deberán limitarse a datos públicos necesarios para auditoría.

## Resultados de esta fase

Se entrega la fundación técnica reproducible. No se reportan precios, supermercados cubiertos, métricas de extracción ni resultados de negocio porque todavía no existen.

## Limitaciones y próximos pasos

El siguiente chat deberá seleccionar un único supermercado, analizar técnicamente su sitio y decidir si la extracción automatizada es viable antes de programar el primer adaptador.
