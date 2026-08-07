# La Colonia — plan de extracción posterior a la radiografía

## 1. Estado

Este documento es un plan. **No autoriza ninguna ejecución.**

```text
radiografía = incompleta
SPS-context-and-root-facets-001 = consumida; no repetir
SPS-context-and-root-facets-002 = no creada / no autorizada
autorizaciones live activas = 0
diagnóstico de navegador SPS = pre-live hardening completado
contexto SPS real = no confirmado
listo para implementar scraper completo = no
listo para full crawl = no
```

No se modifican scraper productivo, runner normal, contratos comerciales, archivo operacional ni workflows live.

## 2. Objetivo

Construir un extractor verificable para el catálogo público de La Colonia que:

- represente San Pedro Sula de forma reproducible;
- identifique producto, SKU, seller y oferta;
- conserve precio y disponibilidad con contexto confirmado;
- demuestre cobertura y detecte omisiones;
- opere secuencialmente y bajo presupuesto;
- se detenga ante bloqueo, inestabilidad o pérdida de contexto.

## 3. Principios

1. **Ubicación antes que precio.** No normalizar precios como SPS sin contexto confirmado.
2. **SKU antes que nombre.** `itemId` es la identidad primaria del SKU; `productId` agrupa variantes.
3. **Raíz como referencia, hojas como particiones.** Ninguna demuestra cobertura por sí sola.
4. **Deduplicación global.** Un SKU puede aparecer en varias superficies.
5. **Evidencia antes que inferencia.** `expected` no implica `observed`.
6. **Operación conservadora.** Concurrencia 1, pausa mínima 1.5 s, máximo un reintento.
7. **Sin full crawl antes de demostrar contexto, estabilidad, cobertura y presupuesto.**

## 4. Fase 1 — Contexto SPS

### 4.1 Prueba consumida

```text
SPS-context-and-root-facets-001
resultado = D — bloqueada por limitación de herramienta
stop_reason = tool_cannot_interact_with_store_selector_or_inspect_session_context
repetición = no autorizada
```

Se detuvo antes de seleccionar SPS y antes de consultar raíz/facets.

### 4.2 Diagnóstico de navegador

Se implementó:

```text
src/precios_supermercados/diagnostics/la_colonia_sps_context_diagnostic.py
```

El diagnóstico prepara:

- BrowserContext limpio;
- selectores semánticos para `Selecciona tu tienda`, `San Pedro Sula` y `Plaza Pedregal`;
- observación sanitizada de cookies/localStorage/sessionStorage;
- captura XHR/fetch/GraphQL;
- replay mínimo basado en el request real observado;
- budget máximo de 8 solicitudes lógicas;
- failure artifacts persistibles;
- checkpoints de progreso;
- bloqueo de autorizaciones no activas.

### 4.3 Hardening pre-live

Estado actual:

```text
ACTIVE_AUTHORIZATION_IDS = []
CONSUMED_AUTHORIZATION_IDS = [SPS-context-and-root-facets-001]
```

Por tanto:

```text
001 -> reject: consumed
002 -> reject: not authorized
003 -> reject: not authorized
999 -> reject: not authorized
```

Una futura autorización de 002 requerirá un cambio explícito que active exactamente ese ID. No existe esa activación en el estado actual.

### 4.4 Regla de consumo

```text
fallo antes de page.goto(TARGET_URL)
    -> authorization_consumption_eligible = false

inicio de page.goto(TARGET_URL)
    -> target_navigation_started = true
    -> authorization_consumption_eligible = true
```

No existe todavía persistencia remota del consumo.

### 4.5 Runtime

Playwright Python está instalado como dependencia y la CI pre-live demostró un Chrome/Chromium compatible ya presente en el runner.

```text
Playwright = 1.62.0
playwright install chromium = no ejecutado
workflow modificado para browser = no
```

La validación usa contenido local/sintético y bloquea HTTP/HTTPS externo desde BrowserContext.

### 4.6 Replay de contexto

`_safe_replay_headers` no inventa ni copia headers sensibles o no demostrados. Solo permite headers públicos cerrados.

Las cookies del BrowserContext pueden acompañar el `APIRequestContext`, pero no se ha demostrado todavía que todos los mecanismos SPS de La Colonia se preserven en el replay.

```text
context_replay_verification = pending_live
```

## 5. Fase 2 — Capturar raíz y facets

Solo después de una nueva autorización y de confirmar SPS:

1. seleccionar ciudad/tienda exclusivamente por UI pública;
2. observar cambio técnico reproducible;
3. capturar la forma real del request de catálogo;
4. reducir la ventana a `from=0`, `to<=4`;
5. capturar una raíz mínima;
6. capturar facets mínimas;
7. repetir una vez;
8. registrar estabilidad y sampling;
9. detener si el contexto no puede atribuirse a SPS.

No existe autorización para ejecutar estos pasos actualmente.

## 6. Taxonomía y facets

Después de confirmar SPS:

- registrar `recordsFiltered` y `sampling`;
- inventariar `type`, `name`, `key`, `value`, `quantity`, `selected`, `children`;
- separar `category-1`, `category-2`, `category-3` y niveles reales adicionales;
- separar marca, landing, colección y especificaciones;
- detectar categorías vacías;
- excluir valores corruptos;
- detener ante sampling o árbol inconsistente.

## 7. Paginación

Validar antes de cualquier recorrido amplio:

- `from/to` inclusivos;
- page size efectivo;
- `OrderByNameASC` estable;
- total constante dentro de la ventana;
- firmas distintas entre páginas;
- ausencia de repetición o parcialidad inesperada;
- límite máximo del backend;
- estabilidad al repetir.

## 8. Productos y ofertas

Muestras futuras mínimas:

1. precio normal;
2. promoción declarada;
3. agotado bajo SPS confirmado;
4. producto por peso;
5. multi-SKU;
6. EAN ausente si aparece;
7. más de un seller si aparece.

Campos de interés:

```text
productId
productReference
productName
linkText
brand
categories/categoryTree
itemId
referenceId
ean
name/nameComplete
measurementUnit
unitMultiplier
sellerId/sellerDefault
Price
ListPrice
AvailableQuantity
discountHighlights
teasers
images
```

Reglas:

- `effective_price = Price` únicamente bajo SPS confirmado;
- `reported_regular_price = ListPrice` solo cuando corresponda;
- no inventar promociones;
- `No disponible` sin tienda no equivale a `out_of_stock` global;
- cantidades Search son señal de disponibilidad, no inventario exacto.

## 9. Identidad y deduplicación

```text
product identity = productId
SKU identity = itemId
offer identity = supermarket + verified context + itemId + sellerId
state identity = state_hash existente
```

No usar `productName` como identidad.

## 10. Cobertura

Estrategia recomendada: **híbrida**.

1. raíz SPS paginada como universo de referencia;
2. hojas estructurales como particiones candidatas;
3. dedupe por `itemId`;
4. agrupación por `productId`;
5. medir intersecciones, residuales, solapamientos y SKU sin hoja;
6. repetir una muestra para demostrar estabilidad.

Clasificaciones previstas:

```text
complete_and_partitionable
complete_with_overlap
incomplete
sampled
unstable
inconclusive
```

No aceptar como prueba de cobertura una simple suma de `quantity`.

## 11. Presupuesto

Referencia histórica sin ubicación verificada:

```text
9291 / page_size 50 -> 186 páginas aproximadas
```

No es total SPS ni autorización.

Presupuesto futuro:

```text
requests_context
+ requests_facets
+ requests_root
+ requests_leaves
+ requests_probes
+ requests_recovery
```

El presupuesto definitivo permanece pendiente de total SPS, sampling, hojas y solapamientos.

## 12. Normalización

Mapeo inicial futuro:

```text
current_price = Price
effective_price = Price bajo contexto confirmado
reported_regular_price = ListPrice cuando sea válida la comparación
is_promotion = diferencia válida o teaser/highlight
availability = seller + Price + AvailableQuantity + contexto
presentation = atributos SKU; fallback conservador
location_status = confirmed solo con evidencia reproducible
```

No modificar contratos antes de resolver los huecos documentados.

## 13. Recuperación y failure artifacts

La herramienta de contexto ya persiste un diagnóstico sanitizado ante fallos controlables.

Campos de progreso:

```text
authorization_checked
browser_started
target_navigation_started
target_navigation_completed
store_selector_opened
city_selected
store_selected
context_observed
root_observed
facets_observed
```

Detener ante:

- 403 persistente;
- 429;
- captcha/antibot;
- autenticación obligatoria;
- JSON inválido;
- HTTP inesperado;
- cambio de esquema;
- selector ausente/ambiguo;
- pérdida de contexto SPS;
- página repetida/parcial;
- presupuesto agotado;
- riesgo de afectar el servicio.

## 14. Seguridad pre-live

Durante tests de navegador:

```text
about:, data:, file: = permitidos
loopback local = permitido
synthetic.invalid = interceptado y fulfilled localmente
HTTP/HTTPS externo = abortado antes de red
lacolonia.com = abortado antes de red
```

Resultado de esta etapa:

```text
tráfico a La Colonia = 0
SPS seleccionado = no
root consultado = no
facets consultadas = no
productos descargados = 0
```

## 15. CI pre-live

Primera validación técnica del hardening:

```text
workflow = Precios Supermercados SPS - Pruebas base
run = 31203765743
run_number = 142
job = 92949733529
Python = 3.12.13
Playwright = 1.62.0
compileall = success
pytest = 533 passed
failed = 0
errors = 0
duration = 40.49s
conclusion = success
```

No se utilizó workflow_dispatch ni workflow live.

La suite probó browser real local/sintético, selectores, storage, network interception, failure artifacts y autorizaciones. Los logs registraron una advertencia de teardown `TargetClosedError`, pero pytest quedó completamente verde y el test explícito de cierre de browser pasó.

## 16. Criterios de listo para implementar scraper completo

Todavía pendientes:

- SPS reproducible en sesión real autorizada;
- seller/precio/disponibilidad bajo SPS;
- endpoint de listados revalidado bajo SPS;
- facets capturadas bajo SPS;
- sampling conocido;
- identidad product/SKU observada bajo SPS;
- casos representativos;
- paginación confirmada;
- presupuesto calculado.

## 17. Criterios de listo para full crawl

Además de lo anterior:

- total raíz SPS estable;
- unión de hojas medida;
- solapamientos cuantificados;
- residuales explicados;
- páginas estables/no repetidas;
- ausencia de 403/429 persistentes;
- umbrales aprobados;
- autorización explícita nueva.

## 18. Próximo paso

No existe prueba live autorizada.

```text
SPS-context-and-root-facets-001 = consumida
SPS-context-and-root-facets-002 = no creada / no autorizada
autorizaciones activas = 0
```

Una futura etapa podrá activar exactamente 002 **solo después** de autorización explícita. Después deberá ejecutar una prueba mínima con el diagnóstico ya endurecido.

## 19. Decisión

```text
estrategia recomendada = híbrida
diagnóstico de navegador = hardening pre-live completado
context_replay_verification = pending_live
siguiente prueba live = Pendiente
autorización live actual = inexistente
full crawl = no autorizado
recorrido por categorías = no autorizado
```
