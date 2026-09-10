# Retail Price Intelligence Platform — especificación de producto

## Propósito y estado

Este documento define la evolución de Precios de Supermercados SPS hacia una
plataforma RPI con una adquisición común y dos productos derivados:

- **Retail Price Intelligence B2B**, servido mediante un Business Data Mart y
  presentado en Power BI;
- **Compra Inteligente B2C**, servido mediante un Consumer Data Mart público y
  presentado en una web responsive mobile-first.

GitHub y `PROJECT_STATE.md` conservan el estado ejecutado. Las secciones marcadas
como objetivo no deben presentarse como funcionalidad productiva hasta que sus
contratos, pruebas y publicación estén integrados.

## Arquitectura autoritativa

```text
supermercados
  -> extracción única por fuente y ubicación autorizada
  -> RAW + hashes + provenance
  -> completeness específico de fuente
  -> health signals
  -> aceptación comercial / last-known-good
  -> Turso: current implícito + periodos históricos compactos
  -> homologación conservadora
  -> comparabilidad + freshness
  -> Python analytics
       -> Business Data Mart -> Power BI B2B
       -> Consumer Data Mart -> Compra Inteligente web
```

Los dos productos reutilizan el mismo estado comercial aceptado. Ningún refresh
de BI o de la web ejecuta scraping y ninguna lógica de matching vive en DAX,
Power Query o JavaScript.

## Calidad y último dato válido

Completeness y health son decisiones distintas:

- **completeness** es source-specific y demuestra páginas, particiones, binding,
  membership, conteos y reconciliación necesarios para aceptar un catálogo;
- **health** registra señales como volumen, precios, promociones, categorías,
  disponibilidad, duración, requests y retries.

La capa compartida clasifica cada run como:

- `ACCEPTED`: completeness válido y sin alertas materiales;
- `DEGRADED`: completeness válido con health warnings auditables;
- `REJECTED`: completeness inválido, independientemente de las estadísticas.

Un run `REJECTED` no muta current/history ni sustituye el último run `ACCEPTED`
o `DEGRADED`. No se crean filas sintéticas para cubrir ausencias. La variación
estadística aislada sólo produce una señal de salud; no prueba incompletitud.

## Homologación y universo comparable

La identidad automática cross-retailer exige un GTIN/EAN válido igual y ausencia
de conflicto comercial. GTIN diferentes nunca se unen por similitud textual.
Marca y presentación no bastan. Una variante contradictoria queda
`not_comparable`; la regresión Passion Especial/Jaguar/Rayo de Sol permanece
bloqueada sin evidencia fuerte adicional.

Una métrica competitiva se calcula sobre el universo que cumple, a la vez:

1. identidad fuerte y consistencia comercial;
2. exactamente una oferta por retailer/ubicación del alcance;
3. precio efectivo positivo;
4. disponibilidad no explícitamente `out_of_stock`;
5. fuentes dentro de la ventana temporal comparable.

Cada salida competitiva debe declarar `comparable_count`, `valid_price_count`,
`excluded_count`, `coverage_pct`, `as_of` y `freshness_window`.

## Freshness

Cada fuente/ubicación analítica expone:

- `observed_at`;
- `last_successful_run`;
- `data_age_hours`;
- `freshness_status` (`FRESH`, `STALE`, `UNAVAILABLE`);
- `as_of`;
- `freshness_window_hours`.

La ventana de mercado es configurable. Si una fuente está stale/unavailable o
la separación entre timestamps supera la ventana, la comparación queda
`INSUFFICIENT_FRESH_COMPARISON`; no se produce un ranking directo. B2B y B2C
muestran la fecha real y nunca ocultan staleness.

## Python analytics

Python es la única fuente de verdad para las métricas compartidas.

### Precio actual y movimientos

- current/previous price;
- cambio absoluto y porcentual;
- dirección;
- días desde el último cambio;
- primer movimiento observado y `observed_response_lag`, sin afirmar causalidad.

### Historia

- mínimo, máximo, media, mediana y rango;
- conteo/frecuencia de cambios, duración y volatilidad;
- ventanas 7/30/60/90/365 días sólo con historia suficiente.

### Promociones

`source_reports_promotion` y `historical_price_reduction` son señales separadas.
Las clasificaciones permitidas incluyen `below_recent_average`,
`near_recent_minimum`, `source_promotion_without_historical_reduction` e
`insufficient_history`. El precio regular declarado no reemplaza la historia
observada.

### Competencia y PCI

```text
PCI = current_price / selected_market_reference * 100
```

La referencia puede ser mean, median, market minimum o un conjunto explícito de
competidores. PCI se publica junto con cobertura, universo comparable, freshness
y `as_of`. Se calculan además mínimo, máximo, media, mediana, spread, ganador y
rank con desempates visibles.

## Business Data Mart y Power BI B2B

El mart es derivado y reconstruible; no cambia el histórico compacto de Turso.
El modelo estrella materializa sólo grains necesarios:

- dimensiones: fecha, producto, retailer, ubicación, categoría y marca;
- hechos: precio diario, cambios, comparación actual, promoción y canasta.

Power BI presenta, sin redefinir lógica crítica en DAX/Power Query:

1. Executive Market Overview;
2. Competitive Pricing;
3. Category Intelligence;
4. Price Movements;
5. Promotion Intelligence;
6. Brand Intelligence;
7. Geographic Intelligence;
8. Assortment / Coverage;
9. Opportunities & Alerts.

Los assets reproducibles son preferibles a un PBIX opaco. La historia sólo se
habilita cuando el contrato histórico publicado exista y esté probado.

## Consumer Data Mart

El mart público contiene únicamente filas autorizadas por Python y los campos
necesarios para búsqueda, comparación, historia resumida y lista de compra. No
expone secretos, URLs privadas, colas de revisión ni catálogo productivo completo.
La web no hace matching por nombre.

Una oferta B2C conserva, cuando la fuente lo provee:

```text
canonical_product_id, source_product_id, supermarket_id, location_id,
category, product_type, product_name, brand, variant, presentation,
current_price, reported_regular_price, is_promotion, availability,
observed_at, freshness_status, historical_summary
```

La publicación navegable usa `rpi-consumer-catalog/v3` y se divide en manifest,
facetas, índices de navegación y particiones de hasta 250 filas. El manifest
declara hash y tamaño de cada archivo; el navegador valida ambos antes de usarlo.
El alcance B2C es exactamente cinco contextos SPS: La Colonia, Colonial,
Walmart, PriceSmart y Comisariato Los Andes. Una fila visible puede ser
`comparable`, `single_source` o `individual`; sólo la primera, con ofertas
`FRESH`, recibe ranking relativo.

## Compra Inteligente y Mi Compra

La aplicación es una sola web accesible para teléfono, tablet y PC. El flujo
principal es buscar, comparar ofertas seguras, elegir manualmente un retailer,
agregar, continuar comprando y revisar la lista agrupada.

Cada ítem guarda identidad, descripción, elección de retailer, cantidad,
`unit_price`, metadatos comerciales, observación y freshness. La selección manual
del usuario no cambia silenciosamente durante un refresh.

### Contrato monetario

```text
unit_price = current_price
line_total = unit_price * quantity
retailer_subtotal = sum(line_total)
grand_total = sum(retailer_subtotal)
```

Todos los cálculos críticos usan enteros minor units o `Decimal`, con redondeo
explícito. `reported_regular_price` puede mostrarse como referencia, pero nunca
infla el total. No se agrega 15%, 18% ni otro impuesto inferido. Shipping,
delivery, service y membership fees no forman parte del precio del producto ni
del total presencial del MVP.

La UI muestra productos por supermercado, cantidades, precios unitarios,
subtotales y `TOTAL ESTIMADO DE MI COMPRA`, con la nota:

> Total estimado calculado con los precios públicos observados en cada
> supermercado. Los precios pueden cambiar en tienda.

### Comportamiento local

- cascada Categoría → Producto → Marca → Presentación y búsqueda secundaria;
- matriz de cinco supermercados en escritorio y tarjetas por producto en móvil;
- una selección nativa tipo radio por producto, con toda la celda accionable y
  foco de teclado preservado;
- preparación de varios productos y alta por lote, con conflictos que exigen
  confirmación explícita;
- cantidades positivas, edición, eliminación y checklist comprado/pendiente;
- persistencia en el dispositivo sin cuentas;
- al reabrir, detección de precios cambiados para la misma identidad y retailer;
- actualización sólo por acción explícita;
- ítems no disponibles se señalan, nunca se sustituyen;
- exportación CSV y PDF con el mismo contrato monetario;
- render seguro mediante DOM/text APIs, sin HTML no confiable.

Cada oferta puede desplegar el último precio observado anterior, promedio de 30
y 90 días, mínimo/máximo de 90 días y una posición humana (`mínimo de 90 días`,
`debajo del promedio`, `en el promedio`, `sobre el promedio` o `historial
insuficiente`). Estos valores los calcula Python desde periodos aceptados; la web
no reconstruye series ni eleva el precio regular declarado a historia.

### Optimización

La opción automática compara selección manual, canasta completa por retailer y
split de mínimo precio. Sólo una canasta con cobertura total compite como total
completo. Los faltantes no cuestan cero. El resultado informa ahorro y cantidad
de supermercados, sin modelar todavía viaje, tiempo o umbral mínimo.

## Actualización derivada

```text
accepted commercial update
  -> homologation refresh
  -> Python analytics refresh
  -> Business Mart + Consumer Mart
  -> publicación estática validada
```

Un fallo conserva la publicación last-known-good. Los artifacts derivados llevan
schema version, hashes, run/SHA fuente, `as_of`, conteos y política de aceptación.

## Seguridad y separación public/private

- Turso y los sitios fuente nunca se consultan desde el navegador;
- ningún secreto o endpoint privilegiado llega a un artifact público;
- el Consumer Mart es reducido y sanitizado;
- material ambiguo o grupos inseguros permanecen fuera de la publicación;
- `ABSENT`, `OUT_OF_STOCK` y `UNKNOWN` conservan significados distintos;
- no se agregan fuentes, ciudades, login, pagos, ML o APIs públicas complejas en
  este MVP.

## Roadmap de madurez

| Nivel | Resultado | Gate de salida |
| --- | --- | --- |
| 0 — Data Foundation | seis cadenas, once ubicaciones, RAW/provenance, persistencia e histórico | ciclo productivo y downstream verdes |
| 1 — Analytics Foundation | quality, LKG, freshness, comparabilidad, historia, PCI y métricas | contratos deterministas y tests |
| 2 — B2B MVP | Business Mart y modelo Power BI de nueve páginas | refresh reproducible y métricas visibles |
| 3 — B2C MVP | Consumer Mart, búsqueda, Mi Compra, exportación y optimización | responsive/accessibility/security QA |
| 4 — Advanced Market Intelligence | análisis posteriores validados por uso e historia | decisión posterior al MVP |
| 5 — Commercial Product | multi-tenant/RLS/operación comercial | clientes y requisitos reales |
| 6 — Advanced Models | forecasting/elasticidad/modelos avanzados | cobertura e historia suficientes |

Los niveles 4–6 son direcciones de evaluación, no features comprometidas ni
implementadas.
