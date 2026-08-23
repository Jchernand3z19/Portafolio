# Arquitectura — Precios de Supermercados SPS

Este documento describe la **arquitectura estable**. El estado operativo mutable, autorizaciones, evidencia productiva y último conteo de pruebas viven exclusivamente en [`PROJECT_STATE.md`](PROJECT_STATE.md).

No uses PRs históricos, ramas o este documento para inferir autorización live.

## 1. Objetivo y principios

Construir una plataforma que recolecte precios de varios supermercados, los normalice a un contrato común, valide calidad/completitud, historice sólo cambios comerciales relevantes y exponga datos confiables a Power BI.

Alcance inicial: **San Pedro Sula**, un supermercado a la vez.

Principios:

1. la fuente manda; no se inventan atributos ni ubicación;
2. contexto fuente y ubicación comercial son conceptos distintos;
3. granularidad (`city`, `store`, etc.) debe demostrarse;
4. corrección técnica no equivale a autoridad productiva;
5. toda ambigüedad crítica falla cerrada;
6. nuevo periodo histórico sólo ante cambio relevante;
7. todo run terminal se registra;
8. un mismo esquema sirve a todos los supermercados;
9. lógica comercial independiente del backend;
10. logs, artifacts, hashes y telemetry no conceden autoridad.

## 2. Flujo principal

```text
Fuente
  ↓
Extractor específico
  ↓
RawProduct
  ↓
Normalización
  ↓
NormalizedOffer
  ↓
Validación + identidad + state_hash
  ↓
ValidatedOffer
  ↓
Completitud / provenance / decisión autoritativa
  ↓
Máquina current/history
  ↓
TabularBatch común
  ↓
Adapter de persistencia
  ↓
Google Sheets (fase inicial)
  ↓
Proyección semántica
  ↓
Power BI
```

BigQuery queda como evolución posterior cuando extracción, calidad, identidad, persistencia y operación diaria sean estables.

## 3. Contratos protegidos

### `RawProduct`
Observación fiel a la fuente. Conserva sólo lo que el extractor pudo demostrar.

### `NormalizedOffer`
Forma común entre supermercados. Normalizar no significa completar información inexistente.

### `ValidatedOffer`
Oferta normalizada que pasó validaciones y contiene `state_hash`, revisión y quality events.

Los tres contratos son generales y no se cambian para acomodar una anomalía particular sin una necesidad demostrada y pruebas de compatibilidad.

## 4. Identidad de producto y oferta

Se separan:

```text
source_product_id = identidad del producto dentro de la fuente
product_id        = identidad normalizada/comparable entre fuentes
offer_id          = supermercado + ubicación comercial + producto fuente
```

`source_product_id` y `offer_id` son deterministas y se recalculan en fronteras críticas.

Para identidad cross-supermercado, un GTIN-8/12/13/14 sólo se acepta si supera su check digit y se normaliza a GTIN-14. Si no existe una identidad fuerte usable, el producto queda bajo `prod_pending_*` y `pending_product_mapping` hasta revisión. Un mapping explícito puede reemplazar el `product_id` provisional sin alterar la identidad fuente.

Precio, promoción, disponibilidad y fecha nunca forman parte de IDs estables.

## 5. Presentación

Las presentaciones se representan con componentes independientes:

```text
unit_count
content_per_unit
measurement_unit
total_content
```

No se colapsan multipacks. Una presentación `2 x 500 ml` sigue siendo dos unidades de 500 ml, aunque el total sea 1000 ml. Si la fuente no permite demostrar un componente, queda nulo y puede requerir revisión.

## 6. Ubicación: contexto fuente vs ubicación comercial

La arquitectura distingue explícitamente:

- **source location context**: contexto raw en que se obtuvo el payload;
- **commercial location**: ciudad/tienda demostrada a la que puede atribuirse una oferta.

Para La Colonia:

```text
la_colonia_online = contexto fuente raw, no ciudad/tienda
la_colonia_sps    = ubicación comercial candidata dentro del alcance
la_colonia_tgu    = ubicación comercial conocida fuera del alcance inicial
```

`la_colonia_online` debe permanecer `location_status=unknown`; bajo ese mismo ID no puede promoverse a SPS mediante `confirmed` o `inferred`. La promoción de ubicación pertenece a una frontera de binding separada que debe producir una ubicación comercial distinta.

Una ubicación comercial no puede habilitarse si:

- su granularidad sigue `unknown`;
- la fuente requiere selección y `technical_binding_confirmed=false`;
- falta `source_location_key` cuando el binding lo requiere;
- está fuera de alcance o no disponible.

### Radiografía de binding

La radiografía preparada compara:

```text
before
-> after_city
-> after_store (si existe selector de tienda)
```

Busca señales fuertes como `regionId`, `salesChannel`, `binding`, `store`, `storeId` o `pickupPoint`. Cambios opacos de `vtex_session`/`vtex_segment` no bastan por sí solos. Valores sensibles/opacos se representan mediante fingerprints sanitizados.

Una radiografía sólo puede proponer una transición. No activa extracción automáticamente.

## 7. Extractores

Cada supermercado tiene su adapter específico, pero todos producen los contratos comunes.

El extractor puede capturar:

- identificadores fuente;
- precio actual;
- precio regular/referencia declarado;
- disponibilidad;
- marca/categoría/presentación cuando se demuestran;
- contexto/evidencia de ubicación;
- metadata de trazabilidad.

No le corresponde:

- decidir ahorro real;
- mutar current/history;
- inventar ubicación;
- conceder `catalog_accepted` o `production_authority`;
- decidir persistencia productiva.

## 8. Completitud de catálogo

Deduplicar no demuestra completitud. La capa de catálogo valida árbol/facets, membresía, totales, ventanas, gaps, truncamiento, repeticiones, ownership, unión producto/SKU y reconciliación de páginas contra el plan canónico.

Una ejecución puede ser técnicamente completa y continuar sin autoridad productiva.

## 9. Frontera Cloudflare / provenance

La arquitectura seleccionada usa:

```text
GitHub Actions autorizado
-> GitHub OIDC
-> Cloudflare Worker
-> Durable Object
-> request físico allowlisted
-> respuesta + hash
-> receipt Ed25519
-> verificador Python independiente
-> Workers Observability
-> manifest / readiness
```

Propiedades:

- identidad OIDC cerrada al repo/ref/workflow/environment/run esperado;
- caller no elige libremente destino físico;
- host/path/método/query restringidos;
- presupuesto, pacing, single-flight, replay y fencing en Durable Object;
- cero retries ocultos en las rutas cerradas;
- receipt ligado a request/run/release/respuesta;
- clave privada sólo en Cloudflare;
- verificador separado usa clave pública confiable;
- evidencia de sonda nunca se convierte en autoridad de catálogo.

### Observability

El contrato actual descubre trace IDs y consulta el detalle mediante `view: events`, revalidando custom span, relación padre-hijo y fetch físico. La hipótesis histórica de que la API pública necesariamente impedía esta reconciliación ya no se usa como conclusión canónica; la frontera permanece **pendiente de una ejecución productiva exitosa del verifier actual** contra la evidencia física existente.

No hace falta contactar La Colonia ni repetir la sonda para realizar esa verificación.

## 10. Current/history y replay

Sólo una decisión comercial aceptada y autoritativa puede mutar current/history.

Invariantes:

- `running` es transitorio;
- replay terminal idéntico es idempotente/reconciliable;
- divergencia bajo el mismo run falla;
- continuidad de identidad/ubicación/moneda;
- cronología cerrada;
- ausencia no implica baja;
- snapshot defensivo de evidencia mutable;
- transición atómica;
- mismo `state_hash` mantiene el periodo;
- cambio de `state_hash` cierra exactamente uno y abre uno nuevo.

Un fingerprint de replay demuestra igualdad, no autoridad.

## 11. Precio regular vs ahorro real

```text
current_price              = precio observado que paga el cliente
reported_regular_price     = referencia declarada por la tienda
historical_previous_price  = current_price aceptado inmediatamente anterior
```

La reducción real es:

```text
max(historical_previous_price - current_price, 0)
```

`reported_regular_price` e `is_promotion` no demuestran ahorro. Sin baseline aceptado no se inventa una reducción.

## 12. Modelo tabular común

La fase inicial usa ocho tablas compartidas:

```text
cfg_supermarkets
cfg_locations
dim_products
map_source_products
fact_offers_current
fact_offer_history
fact_scrape_runs
fact_quality_events
```

`dim_products` contiene únicamente atributos normalizados/canónicos por `product_id`; no contiene supermercado, ubicación, precio ni run. `map_source_products` conserva la relación fuente -> producto y la cola de mappings pendientes.

Current/history siguen siendo comunes a todas las cadenas; nunca se crea una tabla por supermercado.

## 13. Rehidratación durable

La persistencia debe permitir reconstruir un runner nuevo y revalidar IDs, `state_hash`, review status, runs de apertura/current, cronología, cierre de periodos, gaps/overlaps y correspondencia current/history.

`raw_values` no se conserva en el snapshot durable cuando no participa en identidad/hash/transición.

## 14. Batch comercial

Antes del backend se construye un batch completo:

```text
estado persistido
-> rehidratación
-> preflight comercial
-> transición current/history
-> dimensión/mapping de producto
-> registros de run/calidad
-> snapshot tabular
-> adapter
```

Runs no aceptados no materializan dimensión/mapping/current/history. Un backend no recibe una mutación parcial que pueda dejar el snapshot incoherente.

## 15. Google Sheets

Google Sheets es el backend temporal estructurado de la primera fase.

Capas:

1. **plan**: snapshot -> operación de workbook;
2. **transport**: autenticación y endpoints/scopes cerrados;
3. **adapter**: read-modify-write del snapshot gestionado;
4. **bootstrap**: validación/aplicación controlada de configuración.

La materialización usa una operación `spreadsheets.batchUpdate` planificada y preserva pestañas ajenas al proyecto. Texto fuente se escribe como string explícito para evitar fórmulas accidentales.

El workbook físico existente fue creado bajo el contrato anterior de seis tablas. El contrato actual tiene ocho; `dim_products` y `map_source_products` deben materializarse mediante el workflow de storage y confirmarse por read-back antes de declarar la migración física terminada.

## 16. Automatización diaria

Sólo se activa después de cerrar:

1. binding de ubicación;
2. validación live estable;
3. completitud y autoridad del catálogo;
4. persistencia productiva.

```text
schedule
-> extractor
-> calidad/completitud
-> decisión autoritativa
-> transición current/history
-> persistencia
-> run log
-> dataset BI
```

Los fallos estructurales no borran el último snapshot confiable.

## 17. Power BI

Power BI consume la proyección semántica común sobre datos aceptados. No scrapea, no decide autoridad y no redefine el cálculo de ahorro real.

## 18. GitHub y CI

GitHub es la fuente de código, documentación y gobernanza. Todo workflow SPS se audita por triggers exactos, mínimo privilegio, acciones fijadas por SHA, checkout seguro, secretos/variables allowlisted y bloqueo de entrypoints live.

La suite Python ejecuta también la suite Node canónica declarada en `edge/cloudflare/package.json`; no se mantiene una segunda lista manual de tests Node.

```bash
python -m compileall precios-supermercados-sps/src precios-supermercados-sps/scripts
pytest precios-supermercados-sps/tests
```

El conteo vigente se publica sólo en `PROJECT_STATE.md`.

## 19. Orden arquitectónico

```text
CORRECTNESS
-> INFRASTRUCTURE PREFLIGHTS
-> LOCATION BINDING
-> LIVE VALIDATION
-> AUTHORITATIVE ACCEPTANCE
-> PERSISTENCE
-> DAILY AUTOMATION
-> ANALYTICS
-> NEXT SUPERMARKET
```

No se salta una frontera para aparentar avance. Un bloqueo explícito es preferible a datos incorrectamente etiquetados o no autoritativos.
