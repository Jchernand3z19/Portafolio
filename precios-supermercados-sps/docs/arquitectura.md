# Arquitectura — Precios de Supermercados SPS

Este documento describe la **arquitectura estable** del proyecto. El estado operativo mutable, SHA de `main`, último conteo de pruebas, autorizaciones y bloqueos vigentes se mantienen exclusivamente en [`PROJECT_STATE.md`](PROJECT_STATE.md).

No uses un PR histórico ni este documento para inferir una autorización live.

## 1. Objetivo

Construir una plataforma que pueda recolectar precios de varios supermercados, normalizarlos a un contrato común, validar calidad/completitud, conservar únicamente cambios comerciales relevantes y exponer un dataset confiable a Power BI.

Alcance geográfico inicial: **San Pedro Sula**.

Principio de expansión: **un supermercado a la vez**, manteniendo la misma frontera de datos y reutilizando infraestructura común.

## 2. Principios

1. **La fuente manda:** no inventar marca, presentación, precio, disponibilidad, ciudad, tienda ni promoción.
2. **Ubicación verificable:** un precio sólo se etiqueta con una ubicación cuando el contexto técnico que lo produjo está demostrado.
3. **Granularidad explícita:** una fuente puede variar por ciudad, tienda u otro nivel; no se asume `city` por conveniencia.
4. **Autoridad separada de corrección:** una ejecución puede ser técnicamente correcta y aun así no estar autorizada para mutar current/history.
5. **Fail-closed:** ambigüedad de identidad, ubicación, completitud, provenance o autoridad bloquea promoción/persistencia comercial.
6. **Histórico por cambio:** no crear un nuevo periodo si el estado comercial relevante no cambió.
7. **Todo run se registra:** incluso cuando no hay cambios o el run termina rechazado/fallido.
8. **Un mismo esquema para todos los supermercados.**
9. **Backend intercambiable:** lógica comercial independiente de Google Sheets/BigQuery.
10. **Observabilidad no concede autoridad:** logs, comments, artifacts y telemetry documentan hechos; no autorizan tráfico ni catálogo.

## 3. Capas

```text
Fuente / sitio
    ↓
Extractor específico del supermercado
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
Completitud / provenance / decisión comercial
    ↓
Máquina current/history
    ↓
TabularBatch común
    ↓
Adapter de persistencia
    ↓
Google Sheets (fase inicial)
    ↓
Dataset de Power BI
```

BigQuery y Cloud Run quedan como evolución posterior cuando extracción, calidad, identidad, persistencia y operación diaria sean estables.

## 4. Contratos protegidos

### `RawProduct`

Observación fiel a la fuente. Conserva lo que el extractor realmente pudo demostrar.

### `NormalizedOffer`

Forma común entre supermercados. Normalizar no significa completar datos inexistentes.

### `ValidatedOffer`

Oferta normalizada que pasó validaciones de identidad/estado y contiene `state_hash`, revisión y evidencia de calidad.

Estos contratos no se cambian sólo para acomodar una anomalía de un supermercado; primero se comprueba que el cambio sea generalizable y compatible.

## 5. Identidad

Cada supermercado puede tener identificadores fuente diferentes, pero la plataforma construye identidad durable de producto/oferta.

Para La Colonia/VTEX la jerarquía observada es:

```text
Producto: productId -> productReference -> linkText
SKU:      itemId
```

Los IDs derivados y `state_hash` se recalculan en fronteras críticas y durante rehidratación. Un valor persistido no se confía sólo porque ya estaba almacenado.

## 6. Ubicaciones

La ubicación se modela separando:

- supermercado;
- ciudad visible/declarada;
- alcance del proyecto;
- granularidad comercial (`city`, `store`, `unknown`, etc.);
- binding técnico con la fuente;
- estado de evidencia en cada oferta;
- habilitación de extracción.

Una ubicación no puede habilitarse si su granularidad sigue `unknown`.

Para fuentes con selección explícita de ubicación, `technical_binding_confirmed` y `source_location_key` deben estar demostrados antes de persistir ofertas como pertenecientes a esa ubicación.

### Radiografía de binding

La radiografía de ubicación compara snapshots en tres momentos:

```text
before
-> after_city
-> after_store (si existe selector de tienda)
```

Busca mecanismos comerciales conocidos, por ejemplo:

- `regionId`;
- `salesChannel`;
- `binding`;
- `store`;
- `storeId`;
- `pickupPoint`.

`vtex_session` y `vtex_segment` son señales débiles: un cambio opaco de sesión no basta para declarar que dos tiendas comparten precio.

Los valores opacos no deben salir al artifact; se usan fingerprints SHA-256.

### Transición

El resultado de radiografía no modifica configuración directamente.

- `city + strong`: puede proponer binding de ciudad, manteniendo extracción apagada.
- `store + strong`: obliga a modelar tiendas; no permite colapsarlas bajo una sola ubicación ciudad.
- `unknown`: no cambia configuración.

## 7. Extractores

Cada supermercado tiene un adapter/extractor propio, pero todos entregan los contratos comunes.

Responsabilidades del extractor:

- navegar/consultar la fuente dentro del contrato autorizado;
- capturar identificadores fuente;
- extraer precio actual y, cuando exista, precio regular/referencia declarado;
- disponibilidad;
- marca/categoría/presentación cuando la fuente lo demuestra;
- evidencia de ubicación;
- metadata suficiente para trazabilidad.

Responsabilidades que **no** pertenecen al extractor:

- decidir si una promoción es “real” usando histórico;
- mutar current/history;
- inventar ubicación;
- otorgar `catalog_accepted`;
- decidir persistencia productiva.

## 8. Completitud de catálogo

Deduplicar resultados no demuestra que el catálogo esté completo.

La capa de completitud valida, según la fuente:

- árbol/facets;
- membresía de particiones;
- totales independientes;
- ventanas/paginación;
- gaps;
- truncamiento;
- repeticiones;
- conflictos de ownership;
- unión producto/SKU;
- reconciliación de las páginas observadas contra el plan canónico.

Una ejecución puede ser `technically_complete=true` sin convertirse en catálogo comercial autoritativo.

## 9. Frontera Cloudflare / provenance

La arquitectura edge seleccionada usa:

```text
GitHub Actions autorizado
-> GitHub OIDC
-> Cloudflare Worker
-> Durable Object
-> request físico allowlisted
-> respuesta + hash
-> receipt Ed25519
-> verificador independiente Python
-> Workers Observability
-> manifest / readiness
```

### Propiedades de seguridad

- OIDC cerrado a identidad esperada de repo/ref/workflow/environment/run;
- caller no elige libremente destino físico;
- host/path/método/query restringidos;
- presupuesto/pacing/single-flight/replay/fencing en Durable Object;
- `max_retries=0` en las rutas cerradas salvo cambio explícito revisado;
- receipt ligado a request/run/release;
- private key sólo en Cloudflare;
- verificador externo usa public key confiable;
- el job con OIDC y el job que verifica código/evidencia están separados cuando aplica;
- un resultado de sonda nunca produce `catalog_accepted=true` ni `production_authority=true`.

### Sonda controlada

La sonda contra origen propio `workers.dev` existe para probar la infraestructura sin involucrar La Colonia.

Su estado/evidencia actual se registra en `PROJECT_STATE.md`. El runbook está en `cloudflare-controlled-probe-runbook.md`.

La sonda usa Worker, Durable Object, audience, llaves, schema y dominio criptográfico separados de la ruta productiva.

## 10. Decisión comercial y current/history

`commercial_state.py` implementa la máquina backend-neutral.

Invariantes principales:

- sólo una decisión comercial aceptada muta current/history;
- `running` es transitorio;
- replay terminal idéntico es idempotente;
- divergencia bajo la misma identidad de run falla;
- continuidad de identidad/ubicación/moneda;
- cronología cerrada;
- ausencia en un payload no implica `not_listed` ni `out_of_stock`;
- evidencia se captura defensivamente;
- transición atómica;
- mismo `state_hash` mantiene el periodo abierto;
- cambio de `state_hash` cierra exactamente un periodo y abre uno nuevo.

## 11. Precio regular vs oferta real

Separar siempre:

```text
current_price              = precio observado que paga el cliente
reported_regular_price     = referencia/regular declarado por la tienda
historical_previous_price  = último current_price aceptado antes del actual
```

La tienda puede mostrar un `reported_regular_price` útil para presentación, pero ese valor **no demuestra** el descuento real.

La reducción real usa histórico propio:

```text
reduction = max(previous_accepted_current_price - current_price, 0)
```

Si no hay baseline aceptado, no se inventa ahorro.

## 12. Modelo tabular común

La fase inicial usa tablas compartidas por todos los supermercados:

```text
cfg_supermarkets
cfg_locations
fact_offers_current
fact_offer_history
fact_scrape_runs
fact_quality_events
```

No se crea una tabla de current/history separada por cadena de supermercado.

### `fact_scrape_runs`

Registra toda ejecución terminal, con o sin cambios comerciales.

### `fact_offers_current`

Snapshot actual por identidad comercial.

### `fact_offer_history`

Periodos históricos cerrados/abiertos sólo cuando cambia el estado relevante.

### `fact_quality_events`

Eventos de calidad con identidad determinista por run/secuencia.

## 13. Rehidratación durable

La persistencia debe ser suficiente para reconstruir objetos comerciales en un runner nuevo.

La rehidratación recalcula/verifica:

- IDs derivados;
- `state_hash`;
- review status;
- run de apertura/current;
- cronología;
- cierre de periodos;
- gaps/overlaps;
- correspondencia current/history.

`raw_values` no forman parte del snapshot durable cuando no son necesarios para identidad/transición y pueden contener payload fuente voluminoso.

## 14. Batch comercial

Antes de llegar al backend, el proceso construye un `TabularBatch` completo:

```text
estado persistido
-> rehidratación
-> preflight comercial
-> transición current/history
-> registros de run/calidad
-> snapshot tabular completo
-> adapter
```

Un backend no recibe sólo “las filas que cambiaron” si ello pudiera borrar o perder el resto del snapshot.

## 15. Google Sheets — fase inicial

Google Sheets funciona como backend temporal estructurado y revisable.

Capas:

1. **plan**: convierte snapshot a una única operación de workbook;
2. **transport**: autentica y restringe endpoints/scopes;
3. **adapter**: read-modify-write del snapshot gestionado;
4. **bootstrap**: valida/aplica sólo configuración cuando corresponde.

### Seguridad del transporte

- `spreadsheet_id` opaco, no URL arbitraria;
- endpoint fijo `https://sheets.googleapis.com/v4`;
- scope único de Sheets;
- redirects deshabilitados;
- errores sanitizados;
- credenciales sólo en el step que las necesita;
- pestañas ajenas al proyecto se preservan.

### Materialización

El workbook se actualiza mediante un único `spreadsheets.batchUpdate` planificado para mantener atomicidad de la solicitud.

El texto fuente se escribe explícitamente como string para evitar que valores que comienzan con `=` se conviertan en fórmulas.

## 16. Automatización diaria

La automatización diaria se activa sólo después de cerrar:

1. binding de ubicación;
2. validación live estable de la fuente;
3. completitud/autoridad del catálogo;
4. persistencia productiva.

Flujo esperado:

```text
schedule
-> extractor
-> calidad/completitud
-> decisión autoritativa
-> transición current/history
-> persistencia
-> registro del run
-> salida para BI
```

Los fallos estructurales deben detener promoción de datos sin borrar el último snapshot confiable.

## 17. Power BI

Power BI es el único dashboard previsto en la primera arquitectura de producto.

Dataset objetivo:

- producto;
- marca;
- presentación;
- categoría/subcategoría cuando exista;
- supermercado;
- ubicación comercial;
- precio actual;
- precio histórico anterior;
- precio regular/referencia declarado;
- promoción;
- disponibilidad;
- fecha de observación;
- periodos históricos;
- métricas de cambio/reducción real.

La capa BI consume datos persistidos/aceptados; no scrapea sitios ni decide autoridad.

## 18. Expansión a otros supermercados

Para cada nuevo supermercado:

```text
radiografía del sitio
-> determinar ubicación/granularidad
-> extractor específico
-> normalización al contrato común
-> pruebas offline
-> validación live limitada/autorizada
-> completitud
-> persistencia común
-> Power BI existente
```

La mayor parte de la infraestructura debe reutilizarse. Lo específico por supermercado debe concentrarse en el acceso/parseo de la fuente y sus reglas de identidad/ubicación demostradas.

## 19. GitHub y CI

GitHub es la fuente de código, documentación y gobernanza.

Todo workflow SPS está sometido a auditoría fail-closed:

- triggers exactos;
- mínimo privilegio;
- acciones fijadas por SHA;
- checkout seguro;
- secretos/variables allowlisted;
- entrypoints live bloqueados cuando no existe autorización;
- un workflow nuevo debe registrarse explícitamente en la auditoría.

Suite base:

```bash
python -m compileall precios-supermercados-sps/src precios-supermercados-sps/scripts
pytest precios-supermercados-sps/tests
```

El conteo vigente de pruebas se publica sólo en `PROJECT_STATE.md`.

## 20. Orden arquitectónico de avance

```text
CORRECTNESS
-> LOCATION BINDING
-> LIVE VALIDATION
-> AUTHORITATIVE ACCEPTANCE
-> PERSISTENCE
-> DAILY AUTOMATION
-> ANALYTICS
-> NEXT SUPERMARKET
```

No saltar una frontera para mostrar avance aparente. La plataforma debe preferir un bloqueo explícito a datos incorrectamente etiquetados o no autoritativos.
