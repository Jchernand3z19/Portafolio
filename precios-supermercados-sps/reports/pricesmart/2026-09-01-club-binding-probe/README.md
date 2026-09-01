# PriceSmart Honduras — binding real de club y granularidad comercial

## Resultado

El flujo público correcto quedó demostrado mediante CDP:

```text
Elige tu preferencia de entrega
→ Recoger en club
→ lápiz / editar
→ seleccionar club
→ Guardar Club Preferido
→ nueva petición comercial
```

Se cambió una sola variable, el club, en una sesión anónima y sobre la misma
página. Los tres cambios produjeron una petición a:

```text
POST https://www.pricesmart.com/api/br_discovery/getProductsByKeyword
```

`view_id` permanece en `HN`. El binding comercial viaja en los nombres solicitados
por `fl`: `price_HN_6603`, `price_HN_6602` o `price_HN_6604`, junto con availability,
inventory, ahorro y precio regular del mismo club. Las respuestas devuelven esos
campos con el mismo sufijo por producto.

**Outcome B: binding reproducible, precios equivalentes en la muestra y
availability variable.** Se conserva SPS como contexto probado independiente y un
solo contexto comercial TGU representativo, Florencia. El Sauce no justifica un
segundo contexto TGU porque no apareció ninguna diferencia de precio, precio
regular o promoción.

No se creó scraper, fixture comercial, persistencia, workflow ni location
productiva. No se ejecutó full crawl ni se accedió a Turso.

## Binding causal observado

| Club visible | ID | Cookie guardada | Channel final | Campos de la petición |
| --- | --- | --- | --- | --- |
| San Pedro Sula | `6603` | `vsf-selected-club=6603` | `83a01076-4a4e-4163-9786-c59ef7c7c1a6` | `*_HN_6603` |
| Florencia | `6602` | `vsf-selected-club=6602` | `93a6de43-d3c7-4887-a824-44c565dc3101` | `*_HN_6602` |
| El Sauce | `6604` | `vsf-selected-club=6604` | `03544f88-d635-4711-b10c-e040ece7cfe6` | `*_HN_6604` |

La aplicación también guarda `vsf-provider-club-id` y
`vsf-selected-shipping-method=PICK_UP_IN_CLUB`. El cookie `vsf-channel` todavía
tenía el channel anterior cuando salió cada XHR disparada por el cambio; después
se actualizó al channel del nuevo club. Esto descarta atribuir el binding de esta
operación al valor contemporáneo de `vsf-channel`: el payload `fl` observado es
la evidencia que transporta el club a Bloomreach.

Tres replays exactos del payload observado, sin cookie, devolvieron HTTP 200 y el
mismo JSON semántico que el navegador. Florencia y El Sauce fueron idénticos byte
a byte. SPS sólo cambió serialización JSON; al parsearlo, la estructura completa,
documentos, precios y facets fueron iguales.

## Comparación de SKU

Las tres respuestas contienen las mismas 12 identidades `pid = master_sku`. Once
tienen precio declarado en los tres clubes. El SKU `464663` carece de precio en
SPS y Florencia mientras está agotado, pero sí tiene precio y stock en El Sauce;
no se cuenta como igualdad ni como diferencia de precio comparable.

| Comparación | SKU compartidos | Precio comparable | Diferencias de precio | Diferencias regular | Diferencias promoción | Availability distinta | Sólo availability |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Florencia vs El Sauce | 12 | 11 | **0** | **0 observadas** | **0 observadas** | 3 | 2 |
| SPS vs Florencia | 12 | 11 | **0** | **0 observadas** | **0 observadas** | 3 | 3 |
| SPS vs El Sauce | 12 | 11 | **0** | **0 observadas** | **0 observadas** | 4 | 3 |

Los 11 precios comparables son idénticos simultáneamente en los tres clubes.
Ningún documento de los 36 contextos SKU/club declaró
`original_price_without_saving_HN_<club>` ni `saving_amount_HN_<club>`:

- `reported_regular_price = null`;
- `is_promotion = null`;
- cero diferencias observadas de ambos campos;
- no se convierte `promoid_HN` en promoción de precio.

Los campaign IDs son iguales para el mismo SKU, pero etiquetas como
`free-delivery`, `new arrival` o `pantry-refresh` no declaran descuento, precio
regular o ahorro.

## Producto de control

| Campo | SPS 6603 | Florencia 6602 | El Sauce 6604 |
| --- | ---: | ---: | ---: |
| SKU | 479223 | 479223 | 479223 |
| `current_price` | L 359.95 | L 359.95 | L 359.95 |
| `reported_regular_price` | `null` | `null` | `null` |
| `is_promotion` | `null` | `null` | `null` |
| availability | `in_stock` | `in_stock` | `in_stock` |

La interfaz visible cambió el título y el encabezado a cada club y reflejó las
diferencias de disponibilidad de los demás SKU. Availability se deriva de la
combinación explícita `availability_HN_<club>=true` e
`inventory_HN_<club>=in stock`; no determina la granularidad comercial.

## Decisión de granularidad

```text
contextos recomendados para una fase productiva posterior:
  pricesmart_sps       = San Pedro Sula / 6603
  pricesmart_tgu       = Florencia / 6602

contexto TGU adicional:
  El Sauce / 6604      = no conservar por ahora
```

SPS quedó probado independientemente. Florencia y El Sauce comparten los 11
precios comparables y no declaran diferencias de regular/promoción. Sus dos
diferencias exclusivamente de availability y el SKU agotado sin precio en
Florencia no justifican dos catálogos comerciales TGU.

Esta decisión describe la granularidad de price tracking. Si más adelante el
producto requiere stock por club, availability puede observarse por separado sin
duplicar el catálogo comercial TGU.

## Paginación y presupuesto de un eventual full

Se consumieron los tres requests restantes del probe para validar paginación, sin
hacer full crawl:

| Contexto | `start` | `rows` | Devueltos | Total | Solape con página 1 |
| --- | ---: | ---: | ---: | ---: | ---: |
| SPS | 12 | 12 | 12 | 1,124 | 0 |
| Florencia | 12 | 12 | 12 | 1,124 | 0 |
| Florencia | 1,116 | 12 | 8 | 1,124 | 0 |

El modelo reproducible es offset `start` + `rows`. Son 94 páginas por contexto.
Para los dos contextos recomendados, un eventual full requeriría:

```text
base                    = 188 POST
retries incluidos       = 20
máximo propuesto        = 208 POST
concurrencia             = 1
duración máxima propuesta = 30 minutos
RAW estimado sin comprimir ≈ 10.64 MB
```

Ese presupuesto es sólo preflight. **El full crawl no está autorizado** y requiere
una autorización separada.

## Ledger

| Métrica | Resultado |
| --- | ---: |
| Sesiones de browser | 1 |
| Cargas | 1 |
| Clubes guardados por UI | 3 |
| XHR comerciales retenidas | 4: país + 3 clubes |
| Replays exactos por club | 3 |
| Probes de paginación | 3 |
| Retries | 0 |
| Concurrencia | 1 |
| Duración browser | 246.272 s |
| HTTP 403/429/CAPTCHA | 0 |

La captura observó 289 eventos, incluidos recursos bloqueados antes de red, y 57
respuestas, todas de `www.pricesmart.com`; sólo se publican las cuatro XHR
comerciales y sus respuestas. No se consultó GraphQL.

## Evidencia offline

- [raw-capture.tar.gz](raw-capture.tar.gz): requests, responses, snapshots,
  replays, paginación, ledger y manifest; SHA-256
  `a9015896b76372d86a33b5c5785c5a012520e57c6ae3afe066bc73897e9b1c30`.
- [evidence.json](evidence.json): comparación normalizada de los 12 SKU.
- [verify.py](verify.py): valida hashes, binding, identidad, precios, semántica de
  promoción, availability, replay, paginación y decisión TGU sin red.

```bash
python precios-supermercados-sps/reports/pricesmart/2026-09-01-club-binding-probe/verify.py
```
