# Precios de Supermercados de San Pedro Sula

Fundación técnica para recolectar, normalizar, validar y conservar cambios relevantes de precios y disponibilidad de supermercados con alcance inicial en San Pedro Sula.

## Estado

**Ingeniería offline implementada; live globalmente bloqueado.**

El proyecto contiene extractor, crawler, diagnósticos y simuladores de seguridad,
pero todos los transportes reales y jobs live permanecen fail-closed. No declara
completo el catálogo live ni confirma el contexto técnico SPS. La fuente de verdad
actual es [`docs/arquitectura.md`](docs/arquitectura.md).

## Contratos

- `RawProduct`: observación fiel a la fuente.
- `NormalizedOffer`: formato común que permite campos normalizados pendientes sin inventar datos.
- `ValidatedOffer`: hash, revisión y eventos de calidad antes de persistir.

Una oferta `in_stock` exige `current_price > 0`. Los estados `out_of_stock`, `not_listed` y `unknown` pueden conservar precio nulo. Marca, categoría, subcategoría y presentación pueden quedar pendientes con `review_status = needs_review`.

## Nomenclatura oficial

Se utilizan consistentemente:

- `current_price`
- `reported_regular_price`
- `scrape_run_id`
- `availability`
- `run_status`

## Identidad

ID interno, SKU, barcode e ID de API conservan el caso exacto y solo eliminan espacios externos. Las URLs eliminan únicamente tracking inequívoco. El precio nunca forma parte de la identidad.

## Seguridad comercial

Una extracción incompleta no se interpreta como un nuevo estado de mercado. Las ejecuciones `rejected`, `failed` o `abandoned` registran métricas y eventos, pero no actualizan precios, disponibilidad ni historial.

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

## Pruebas

Desde la raíz del monorepositorio:

```bash
python -m compileall precios-supermercados-sps/src
pytest precios-supermercados-sps/tests
```

## Fuera de alcance actual

- tráfico live sin autorización nueva;
- evidencia productiva de GATE-17;
- declaración de catálogo live completo;
- confirmación técnica SPS;
- conexión a Google Sheets;
- scraping diario;
- Power BI;
- BigQuery o Cloud Run;
- tarjeta pública del proyecto.

Los contratos completos están en [`docs/modelo-datos.md`](docs/modelo-datos.md).
