# Estado actual — Retail Price Intelligence / Precios de Supermercados SPS

GitHub `main`, GitHub Actions, los artifacts productivos, Turso y la rama `portfolio-data` son la fuente de verdad técnica. Este archivo contiene únicamente el estado **vigente**; los hitos e incidentes anteriores se conservan en los snapshots y documentos históricos del proyecto.

## Checkpoint vigente — 2026-09-10

El producto está operativo como **Retail Price Intelligence (RPI)** con dos superficies principales:

- **Compra Inteligente B2C**, una experiencia web responsive para navegar precios públicos, comparar ofertas seguras y organizar una compra;
- **Business Mart B2B**, un contrato analítico reproducible para Power BI con comparación actual, histórico de precios, promociones, cobertura y freshness.

La adquisición, normalización, histórico y homologación siguen siendo una sola base compartida. La lógica monetaria y de comparabilidad autoritativa permanece en Python; ni Power BI ni el navegador crean equivalencias nuevas.

## Contratos vigentes

| Contrato | Estado | Uso |
| --- | --- | --- |
| `rpi-business-mart/v1` | vigente, privado | Power BI / analítica B2B |
| `rpi-consumer-mart/v2` | vigente, público | comparación analítica segura y escenarios B2C |
| `rpi-consumer-catalog/v3` | vigente, público | navegación escalable de Compra Inteligente |
| `rpi-marts-manifest/v1` | vigente | integridad, schemas, scope y SHA-256 |
| `rpi-consumer-catalog-manifest/v3` | vigente | integridad y serving del catálogo particionado |

Los contratos `precios-sps-publication/v1` y `precios-sps-static-bi-dataset/v1` se conservan por compatibilidad/historial, pero ya no son la arquitectura RPI principal.

## Publicación B2C verificada

La publicación posterior al PR #451 está materializada en `portfolio-data`. El Consumer Catalog v3 publicado el **2026-09-10** declara:

- `as_of = 2026-09-10T16:21:00.121554Z`;
- **44,042 filas visibles**;
- **46,680 ofertas fuente**;
- 2,638 filas comparables;
- 11,846 filas `single_source`;
- 29,558 filas individuales;
- 484 particiones, con máximo de 250 filas por partición;
- 45,420 ofertas con resumen histórico;
- payload inicial de 37,796 bytes sin comprimir / 4,957 bytes gzip;
- dos requests iniciales: manifest + facetas.

El alcance público B2C es exactamente:

| Cadena | Contexto SPS |
| --- | --- |
| La Colonia | `la_colonia_sps` |
| Colonial | `colonial_sps` |
| Walmart | `walmart_sps` |
| PriceSmart | `pricesmart_sps` |
| Comisariato Los Andes | `comisariato_los_andes_sps` |

Las cinco fuentes figuraban `FRESH` en ese corte. La publicación separa **visibilidad** de **comparabilidad**: un producto puede mostrarse individualmente aunque no exista evidencia suficiente para compararlo con otra cadena.

El Consumer Mart v2 publicado en el mismo ciclo quedó `COMPARABLE`, con 92 productos en el universo analítico seguro de La Colonia SPS + Walmart SPS y política `fail_closed_strong_identity_and_commercial_consistency`.

## Compra Inteligente

La interfaz pública consume únicamente archivos estáticos publicados y valida tamaños/SHA-256. No consulta Turso y no hace matching en JavaScript.

Está implementado:

- navegación por facetas dependientes;
- matriz de cinco supermercados SPS;
- búsqueda y tarjetas responsive;
- selección manual de oferta exacta;
- cantidades por producto;
- alta por lote con confirmación de conflictos;
- `Mi Compra` persistida localmente y agrupada por supermercado;
- actualización explícita de precios sin sustitución silenciosa de retailer;
- manejo visible de precios cambiados, faltantes o no disponibles;
- escenarios de canasta manual, por un solo supermercado y optimización por mejor precio seguro;
- contexto histórico por oferta: precio anterior, 30/90 días, mínimos, máximos y posición histórica;
- exportación local CSV y PDF.

Contrato monetario:

```text
unit_price = current_price
line_total = unit_price * quantity
retailer_subtotal = sum(line_total)
grand_total = sum(retailer_subtotal)
```

`reported_regular_price` es sólo referencia. No se inventan ISV, impuestos, delivery, service fees, membership fees ni otros cargos de checkout. Si una línea no tiene precio utilizable, los totales dependientes quedan incompletos; nunca se imputa cero.

## Business Mart y Power BI

`rpi-business-mart/v1` incluye:

- dimensiones de producto, retailer, ubicación, categoría y marca;
- `fact_current_comparison`;
- `fact_price_history` sobre periodos comerciales realmente persistidos;
- `fact_promotion_analysis`;
- `fact_basket_cost`;
- `fact_metric_coverage`;
- `source_freshness`.

Los cambios de precio, PCI, ranking, deltas, freshness y semántica promocional/histórica se calculan en Python. Los activos reproducibles de `powerbi/rpi/` contienen Power Query, DAX, relaciones, tema y especificación de las nueve páginas. El repositorio **no fabrica ni versiona un `.pbix` simulado**: un PBIX final, si se desea como archivo binario de presentación, se construye en Power BI Desktop a partir de esos activos.

## Operación recurrente

El workflow `.github/workflows/precios-supermercados-sps-la-colonia-mvp-update.yml` corre diariamente a `17 11 * * *` (05:17 `America/Tegucigalpa`) y cubre seis cadenas / once contextos productivos demostrados:

| Cadena | Ubicaciones/contextos productivos |
| --- | --- |
| La Colonia | SPS, Tegucigalpa |
| Colonial | SPS |
| Walmart | SPS, TGU FFAA, TGU El Sauce |
| PriceSmart | SPS 6603, TGU Florencia 6602 |
| Comisariato Los Andes | SPS |
| Paiz | TGU Multiplaza, TGU Próceres |

La última corrida programada completamente verde fue el run `34368332245` del **2026-09-09**.

El run programado `34492865834` del **2026-09-10** falló de forma segura durante la captura de Comisariato Los Andes por un timeout de transporte en `page-00200.json`. La compuerta global bloqueó la persistencia, por lo que ese intento no reemplazó el último estado comercial válido con datos parciales.

El PR **#455** (`[RPI] Retry transient Los Andes timeouts safely`) fue fusionado el 2026-09-10. Los Andes ahora permite **un único reintento por solicitud sólo para errores transitorios de transporte**, con máximo diez reintentos acumulados y dentro del presupuesto existente de intentos. No se reintentan errores HTTP y las reglas de completitud/fail-closed no se relajaron.

**Pendiente operativo único:** observar una siguiente ejecución programada con el ajuste #455 para confirmar el ciclo end-to-end en producción. No hace falta otro cambio de producto para esa comprobación y no se debe provocar scraping live adicional sólo para obtener evidencia.

## Cadena de publicación vigente

Tras una actualización aceptada:

```text
captura validada
→ Turso / histórico aceptado
→ refresh de homologación derivada
→ exportación RPI read-only
→ validación de schemas, scope, hashes y secretos
→ publicación atómica en portfolio-data
→ Compra Inteligente consume sólo archivos estáticos
```

La publicación pública incluye Consumer Mart v2, Consumer Catalog v3 y la muestra de portafolio. **Business Mart permanece privado** dentro del artifact analítico y no se copia al namespace público.

## Límites vigentes

- Paiz no tiene un contexto SPS aceptado; sus contextos demostrados son Multiplaza y Próceres en Tegucigalpa.
- PriceSmart El Sauce 6604 permanece excluido.
- Maxi Despensa y Despensa Familiar continúan en **NO-GO TEMPORAL PARA PRICE TRACKING WEB**.
- Un dato `STALE`, `UNAVAILABLE`, ambiguo o sin suficiente cobertura no puede producir ranking/PCI/recomendación competitiva nueva.
- Los documentos históricos de incidentes se preservan tal como fueron emitidos; este archivo es el único resumen mutable del estado presente.

## Criterio de cierre del producto actual

El producto funcional, los contratos B2B/B2C, Compra Inteligente, la publicación estática y los activos reproducibles de Power BI están implementados. Para declarar estable el ciclo operativo posterior al incidente del 10 de septiembre sólo falta comprobar una siguiente ejecución programada verde usando el ajuste #455.
