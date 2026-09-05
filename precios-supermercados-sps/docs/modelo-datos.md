# Modelo común de datos y almacenamiento

Este documento describe el modelo físico productivo actual y las capas derivadas de homologación/publicación. El estado operativo mutable vive en [`PROJECT_STATE.md`](PROJECT_STATE.md).

## 1. Backend productivo

El backend persistente principal es **Turso/libSQL**, con SQLite como equivalente local/reproducible. Componentes históricos de BigQuery y Google Sheets permanecen en el repositorio, pero no definen la ruta productiva vigente.

La base es única para todas las cadenas y ubicaciones.

## 2. Identidades

```text
supermarket_id    = cadena
location_id       = ubicación/contexto comercial demostrado
source_key        = identidad estable entregada por la fuente
product_id        = PK interna de un producto fuente persistido
canonical_gtin    = GTIN validado/canonizado cuando existe
canonical_product_id = identidad derivada fuerte usada por homologación
scrape_run_id     = ejecución persistida
```

Precio, promoción, disponibilidad y timestamps no forman parte de la identidad estable del producto.

`canonical_product_id` no sustituye `product_id`: una identidad canónica puede agrupar perfiles de varios supermercados únicamente cuando la evidencia lo permite.

## 3. Relaciones físicas principales

```text
supermarkets 1 ─── N locations
supermarkets 1 ─── N products
products     1 ─── N price_history
locations    1 ─── N price_history
scrape_runs  1 ─── N periodos originados/confirmados
products     1 ─── 0..1 product_homologation_profiles   # derivada
```

La ciudad pertenece a `locations`. Un producto fuente puede observarse en varias ubicaciones sin duplicar su identidad descriptiva.

## 4. `supermarkets`

**Grain:** una fila por cadena.

Responsabilidad: catálogo de retailers y atributos mínimos de identidad. No contiene precios ni reglas específicas de scraping.

## 5. `locations`

**Grain:** una fila por ubicación/contexto comercial persistible.

Responsabilidad:

- relación con `supermarket_id`;
- ciudad/contexto;
- identidad fuente de la tienda/club cuando existe;
- alcance operativo.

La existencia de una fila no implica que un run concreto haya demostrado esa ubicación. Esa evidencia pertenece al snapshot/run.

## 6. `products`

**Grain:** una identidad fuente estable de producto dentro de un supermercado.

Campos relevantes del contrato productivo incluyen:

```text
product_id
supermarket_id
source_key_type
source_key
source_sku / IDs fuente disponibles
name
brand
presentation
category
ean / referencia equivalente cuando la fuente la provee
```

Reglas:

- no contiene ciudad ni precio;
- el nombre no es una clave;
- marca + presentación no forman una clave cross-source;
- atributos descriptivos pueden actualizarse sin reemplazar la identidad estable del producto fuente.

## 7. `price_history`

**Grain:** un periodo comercial por `product_id + location_id`.

Campos conceptuales:

```text
product_id
supermarket_id
location_id
current_price_minor
reported_regular_price_minor
is_promotion / promotion evidence
availability
currency
valid_from_utc
valid_to_utc
scrape_run_id
```

### Estado actual

```text
valid_to_utc IS NULL
```

representa el periodo vigente. No existe necesidad de una segunda tabla `current` que pueda divergir del histórico.

### Regla de cambio

Si el nuevo estado comercial aceptado es igual al periodo abierto, el periodo permanece abierto. Si cambia precio, promoción, disponibilidad u otro atributo comercial relevante, se cierra el periodo anterior y se abre uno nuevo.

Por ello `price_history` no es una copia diaria redundante.

## 8. Precio

Los importes persistidos se almacenan como enteros de unidad menor.

```text
current_price_minor
reported_regular_price_minor
```

`reported_regular_price_minor` es una referencia declarada por la fuente. No se usa automáticamente como “precio anterior” ni como prueba de ahorro real.

Para análisis histórico:

```text
historical_previous_price = current_price del periodo aceptado inmediatamente anterior
```

Si ese periodo no existe, no se inventa baseline.

## 9. Disponibilidad

Ausencia de evidencia no se convierte en `out_of_stock`.

Estados fuente normalizados pueden incluir, según el contrato:

```text
in_stock
out_of_stock
unknown
```

La capa analítica considera un precio explícitamente `out_of_stock` como no utilizable para una canasta actual, aunque permanezca un valor de precio en el registro.

## 10. `scrape_runs`

**Grain:** una ejecución persistida por supermercado/ubicación.

Responsabilidades:

- identidad del run;
- `supermarket_id`;
- `location_id`;
- estado terminal;
- conteos de catálogo/SKU;
- digest del snapshot aceptado;
- timestamps/metadata necesarios para auditoría.

El postflight productivo verifica que los `scrape_run_id` esperados existan con conteos y SHA-256 correspondientes al snapshot que se persistió.

## 11. Integridad productiva

Después de persistir se comprueban, según el flujo:

- `PRAGMA integrity_check`;
- `pragma_foreign_key_check`;
- ausencia de periodos actuales duplicados por producto/ubicación;
- presencia de los run IDs exactos;
- reconciliación de conteos de estado actual con snapshots aceptados.

Un `HTTP 200` del backend no sustituye estas verificaciones.

## 12. `product_homologation_profiles`

Tabla **derivada** de `products`. No es la fuente de verdad del producto original.

**Grain:** un perfil por `product_id`.

Contrato actual:

```text
product_id
supermarket_id
normalized_name
normalized_brand
canonical_gtin
canonical_product_id
category
subcategory
product_type
taxonomy_rule_id
presentation_dimension
presentation_total_base
presentation_pack_count
presentation_unit_amount_base
presentation_status
comparison_status
conflict_reasons_json
normalization_version
profile_hash
updated_at_utc
```

### Presentación

La presentación se estructura para poder distinguir, por ejemplo:

- masa;
- volumen;
- conteo;
- multipack;
- conflicto/ambigüedad.

No se reduce un multipack ambiguo a una cantidad arbitraria.

### `comparison_status`

El perfil puede describir estados como `ready`, `review_required`, `single_source` o `unmapped`, pero este campo **no autoriza por sí solo** una comparación de precio. La autorización final pertenece a `safe_comparator` y evalúa el grupo completo.

## 13. Identidad cross-source

Un GTIN sólo se considera fuerte cuando:

- tiene longitud GTIN válida;
- supera check digit;
- se canoniza de forma determinista.

Sin identidad fuerte, el sistema puede conservar un candidato para revisión, pero no lo usa automáticamente en ahorro/canasta.

Incluso con el mismo GTIN, contradicciones comerciales pueden producir `not_comparable`.

Regresión explícita:

```text
Passion Jaguar 1 lb
!=
Passion Especial 1 lb
```

Marca y presentación iguales no son suficientes.

## 14. Capa de comparación segura

`safe_comparator.py` no crea una tabla física adicional obligatoria. Produce decisiones deterministas derivadas de perfiles homologados:

```text
comparable
review_required
not_comparable
```

Los consumidores analíticos sólo usan `comparable`.

Razones de bloqueo incluyen, entre otras:

- `strong_identity_missing`;
- `brand_identity_conflict`;
- `product_type_conflict`;
- `presentation_conflict`;
- `presentation_evidence_conflict`;
- `commercial_identity_conflict`.

## 15. Modelo analítico actual

`CurrentPriceObservation` proyecta el estado vigente mínimo necesario para analítica:

```text
source_record_id
supermarket_id
location_id
price_minor
availability
```

`ComparisonScope` exige exactamente una ubicación explícita por supermercado incluido.

### Producto comparable

`ProductComparison` agrupa sólo ofertas seguras de un `canonical_product_id` y calcula:

- mínimo actual;
- máximo actual;
- ahorro absoluto contra el máximo;
- ahorro porcentual;
- todos los precios del alcance.

### Canasta común

`BasketComparison` usa el mismo universo en todas las cadenas del alcance:

```text
products_comparable_and_priced_in_every_supermarket_in_scope
```

Un faltante no se imputa. Un universo vacío no tiene ganador.

## 16. Dataset de publicación

Contrato:

```text
precios-sps-publication/v1
```

Estructura raíz:

```text
schema
comparison_policy
currency
scope
offers
products
common_basket
excluded_group_counts
```

### `offers`

Una fila por producto canónico + supermercado + ubicación publicada.

### `products`

Una fila por producto canónico con mínimo, máximo y ahorro.

### `common_basket`

Una fila por supermercado con el total del mismo denominador.

### `excluded_group_counts`

Sólo conteos agregados de grupos bloqueados; no publica precios que puedan inducir una equivalencia falsa.

Diccionario completo: [`PUBLICATION-DATA-DICTIONARY.md`](PUBLICATION-DATA-DICTIONARY.md).

## 17. Exportación

`scripts/exportar_modelo_analitico.py` puede leer:

```text
SQLite en modo read-only
Turso usando credenciales del entorno confiable
```

y genera:

```text
publication.json
offers.csv
products.csv
common-basket.csv
excluded-groups.csv
manifest.json
```

El manifest contiene el backend lógico y conteos, pero nunca la URL ni el token de Turso.

## 18. Consumidores

Power BI y el portafolio consumen el dataset publicado. No deben volver a inferir:

- identidad;
- ubicación;
- aceptación del run;
- matching por nombre;
- equivalencia por marca/presentación.

La lógica crítica se mantiene una sola vez en Python y está cubierta por tests.

## 19. Evolución de esquema

Las migraciones se mantienen explícitas y fail-closed. Un persistidor que requiere un esquema nuevo verifica su presencia antes de modificar estado comercial.

La tabla derivada de homologación puede reconstruirse desde `products`, por lo que su refresh no modifica la fuente comercial original.

## 20. Fuente de verdad

- arquitectura: [`arquitectura.md`](arquitectura.md);
- estado operativo: [`PROJECT_STATE.md`](PROJECT_STATE.md);
- metodología de comparación: [`COMPARATOR-METHODOLOGY.md`](COMPARATOR-METHODOLOGY.md);
- contrato BI/publicación: [`PUBLICATION-DATA-DICTIONARY.md`](PUBLICATION-DATA-DICTIONARY.md).