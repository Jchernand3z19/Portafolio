# Decisiones técnicas

Este archivo conserva decisiones históricas en orden. Cuando una decisión deja de ser vigente, se mantiene para trazabilidad y una decisión posterior la marca explícitamente como supersedida.

## DT-001 — Monorepositorio

El proyecto vive en `precios-supermercados-sps/`. Los workflows viven en `.github/workflows/`.

## DT-002 — Contratos Python conservadores y dependencias explícitas

Los contratos de dominio usan `dataclass`, `StrEnum`, `Decimal`, `datetime` y validaciones propias. Las dependencias externas del proyecto se declaran en `requirements.txt`; actualmente incluyen `pytest`, `playwright`, `PyYAML` y `cryptography`. No se presenta la biblioteca estándar como única dependencia del proyecto completo.

## DT-003 — Nomenclatura única

Los nombres oficiales son `current_price`, `reported_regular_price`, `scrape_run_id`, `availability` y `run_status`. No se mantienen alias paralelos.

## DT-004 — Tres etapas explícitas

- `RawProduct`: fidelidad de la fuente.
- `NormalizedOffer`: formato común, incluso con interpretación parcial.
- `ValidatedOffer`: hash, estado de revisión y eventos de calidad.

## DT-005 — Observaciones parciales legítimas

Marca, categoría, subcategoría y componentes de presentación pueden quedar nulos. El contrato conserva el producto con `pending_fields`, `review_status = needs_review` y eventos `pending_normalization`. No se inventan datos.

## DT-006 — Regla de precio por disponibilidad

`in_stock` requiere `current_price > 0`. `out_of_stock`, `not_listed` y `unknown` permiten `current_price = null`.

## DT-007 — Identidad independiente del precio

Precio, promoción, disponibilidad y fecha no participan en `source_product_id`, `product_id` ni `offer_id`.

## DT-008 — Sensibilidad de llaves fuente

ID interno, SKU, barcode e ID de API conservan mayúsculas y minúsculas y solo eliminan espacios externos. La normalización específica de un supermercado deberá documentarse en su adaptador y pruebas.

## DT-009 — URL conservadora

La URL estable elimina fragmentos y solo parámetros inequívocos de tracking: `utm_*`, `gclid`, `fbclid`, `msclkid`, `mc_cid`, `mc_eid`. `ref` y cualquier parámetro potencialmente funcional se conservan.

## DT-010 — Componentes obligatorios no vacíos

`supermarket_id`, `location_id`, `source_product_id` y `source_key` se validan antes de crear identificadores.

## DT-011 — Producto fuente y normalizado

`source_product_id` identifica el registro del supermercado. `product_id` agrupa productos comparables. El mapeo puede permanecer `pending` sin eliminar la observación.

## DT-012 — Oferta por ubicación

`offer_id` combina supermercado, ubicación y producto fuente.

## DT-013 — Promoción declarada versus reducción real

`is_promotion` conserva la condición observada. `reported_regular_price` no demuestra ahorro. La reducción real se calcula contra el `current_price` del periodo histórico aceptado inmediatamente anterior. No existe `promotion_text`.

## DT-014 — Ubicación auditable

`location_status` puede ser `confirmed`, `inferred` o `unknown`. Confirmed/inferred requieren `location_evidence` y `location_confidence` entre 0 y 1.

## DT-015 — Hash con nulos deterministas

`state_hash` incluye precios, promoción, disponibilidad y atributos normalizados relevantes, incluso cuando sean nulos. Cambios cosméticos no alteran el hash.

## DT-016 — Estados de ejecución

`run_status` usa `running`, `success`, `warning`, `rejected`, `failed`, `abandoned`. Una ejecución incompleta se marca `rejected`; no actualiza precios, disponibilidad ni periodos.

## DT-017 — Métricas de completitud

Cada ejecución registra cobertura de páginas, productos, ofertas y precios, comparación con la última ejecución aceptada, rechazos y eventos estructurales. Los umbrales viven en `cfg_supermarkets`.

## DT-018 — Historial trazable

Cada periodo registra `change_type`, `changed_fields`, ejecución de apertura/cierre, precios originales, versiones, ubicación y auditoría. Un reintento no duplica historial.

## DT-019 — Trazabilidad GitHub

`fact_scrape_runs` conserva workflow, run ID, intento, commit SHA y ref ejecutada.

## DT-020 — Google Sheets es contrato histórico, no backend elegido

El modelo documenta estructuras compatibles con una primera etapa en Google Sheets, pero no conecta Google Sheets ni solicita credenciales. Esa documentación no obliga a escoger Sheets, BigQuery, SQLite o PostgreSQL como backend productivo antes de cerrar la frontera de aceptación autoritativa.

## DT-021 — Sitio público fuera de alcance

No se modifica Mundial 2026, `js/main.js`, el registro de proyectos ni la página pública.

## DT-022 — Frontera comercial fail-closed y backend-neutral

`commercial_state.py` implementa la transición current/history sin almacenamiento externo. Sólo un run `success` o `warning` con catálogo aceptado puede mutar estado. `running`, `rejected`, `failed`, `abandoned` o catálogo no aceptado no mutan. La capa revalida `state_hash`, exige cronología `observed_at_utc <= validated_at_utc <= decided_at_utc`, hace replay idempotente y rechaza reutilización conflictiva de `scrape_run_id`.

Una oferta ausente de un payload posterior no se interpreta como eliminación, `not_listed` ni `out_of_stock`; esos estados requieren evidencia explícita. El booleano `catalog_accepted` de esta capa no concede autoridad live: en producción debe provenir de una decisión autoritativa derivada de provenance independiente.

## DT-023 — CI en PR y defensa en profundidad sobre `main`

La suite offline corre en pull requests, manualmente y en pushes a `main` que afecten `precios-supermercados-sps/**` o `.github/workflows/**`. El ruleset productivo exige el check `tests` antes de fusionar un PR a `main`; la ejecución adicional sobre push permanece como defensa en profundidad. La auditoría de workflows prueba que esta cobertura no desaparezca silenciosamente.

## DT-024 — Replay terminal liga evidencia persistible

`running` es un estado transitorio y no consume la identidad terminal de `scrape_run_id`. El mismo run puede evolucionar de `running` a su decisión final. En cambio, una decisión terminal aplicada o descartada comercialmente queda ligada de forma idempotente a su decisión, `state_hash`, timestamps, identidad de oferta y evidencia persistible/auditable (`source_url`, versiones, trazabilidad fuente explícita, ubicación, review/pending y eventos de calidad).

Reutilizar un `scrape_run_id` terminal con evidencia distinta falla cerrado. `raw_values` no participa en ese fingerprint porque es un contenedor crudo arbitrario y no forma parte de la identidad persistible definida por esta frontera. Esto no altera `state_hash`: los cambios comerciales siguen determinados exclusivamente por los campos canónicos del estado.

## DT-025 — No fijar el HEAD mutable dentro de la fuente canónica

Los SHAs históricos usados como evidencia de auditoría pueden documentarse. El HEAD “actual” de `main` se consulta en GitHub y no se intenta mantener autorreferencialmente dentro de README/arquitectura, porque cualquier merge que actualice esos archivos produciría inmediatamente un nuevo HEAD y volvería obsoleto el valor escrito.

## DT-026 — Identidad determinista revalidada en la frontera comercial

La persistencia comercial no confía en IDs suministrados por el caller. Antes de mutar current/history se recalculan `source_product_id = generate_source_product_id(supermarket_id, source_key_type, source_key)` y `offer_id = generate_offer_id(supermarket_id, location_id, source_product_id)`.

Además, una identidad lógica de oferta no puede pertenecer a dos `offer_id`, un `offer_id` existente no puede migrar a otra identidad, y la relación entre producto fuente y llave fuente debe permanecer estable incluso entre ubicaciones. La moneda permanece estable para un `offer_id`; `product_id` sí puede cambiar por una corrección legítima de mapeo normalizado.

## DT-027 — Evidencia mutable aislada mediante snapshots defensivos

Los contratos protegidos no se modifican para resolver mutabilidad anidada de `raw_values`. La frontera comercial copia recursivamente esa evidencia antes de almacenarla y devuelve snapshots defensivos desde `current()` y `history()`.

Una mutación posterior del objeto caller-defined o de una vista devuelta no puede alterar current/history ya aceptado. Si una evidencia no puede copiarse de forma segura, la transición falla cerrada antes del commit.

## DT-028 — Pricing derivado es puro y usa el periodo aceptado anterior

`commercial_pricing.py` es una capa backend-neutral que deriva `RealPriceReduction` a partir de current/history ya aceptados. El baseline es exclusivamente el `current_price` del periodo histórico inmediatamente anterior; `reported_regular_price` e `is_promotion` nunca participan en la fórmula de ahorro real.

Sin precio actual o baseline no se inventa reducción. Una igualdad o subida produce reducción cero. Un run rechazado no puede crear un baseline comercial porque no muta current/history.

## DT-029 — Pricing revalida evidencia persistida y falla cerrado

Una derivación de precio no asume que un backend futuro conserve intactos los wrappers recibidos. Antes de calcular se revalidan IDs deterministas, `state_hash`, cronología, moneda, `offer_id`, apertura, última observación, contigüidad y la existencia de un único periodo abierto al final.

Todo periodo cerrado debe registrar `closed_by_scrape_run_id`; un periodo abierto no puede tener run de cierre. El run que cierra un periodo debe ser el mismo que abre el siguiente periodo contiguo. Las incoherencias impiden calcular ahorro y producen `CommercialPricingError` en vez de una cifra potencialmente falsa.

## DT-030 — `main` protegido con enforcement funcional verificable

GATE-17 no se considera cerrado sólo porque exista un ruleset configurado. La evidencia productiva exige observar a GitHub bloquear merges reales. La evidencia de PR #29 demostró bloqueo por check pendiente y por conversación de review sin resolver antes del merge permitido.

## DT-031 — Diseño Google Cloud evaluado y supersedido

La arquitectura Cloud Run/Direct VPC/Secure Web Proxy/Logging/KMS se conserva únicamente como historial; no llegó a ser la ruta productiva final.

## DT-032 — Cloudflare como frontera física seleccionada en la etapa de prueba

La ruta Cloudflare Workers + Durable Objects + OIDC + Ed25519 fue seleccionada y validada como frontera física durante la etapa correspondiente. Sus evidencias y límites se conservan históricamente; no define por sí sola el backend comercial actual.

## DT-033 — Completitud técnica no equivale a aceptación productiva

La cadena puede cerrar discovery, receipts y reconciliación técnica sin que eso conceda `catalog_accepted=true` o `production_authority=true`.

## DT-034 — Cloudflare se prueba primero contra origen controlado

Antes de una validación física contra una fuente real, la infraestructura se prueba contra un origen propio. La sonda no concede autoridad de catálogo.

## DT-035 — `la_colonia_online` es contexto fuente, no ubicación comercial

`la_colonia_online` no representa SPS/Tegucigalpa ni una tienda. El binding comercial debe producir un `location_id` distinto sólo después de evidencia suficiente.

## DT-036 — GTIN válido es identidad fuerte; lo demás queda pendiente

Un barcode sólo crea identidad cross-retailer automática cuando es GTIN-8/12/13/14 válido y supera check digit. Sin ello se conserva identidad pendiente/revisable.

## DT-037 — Producto normalizado y mapping fuente son conceptos distintos

`dim_products` y `map_source_products` separan identidad canónica de relación fuente. Esta decisión define el contrato lógico, no obliga a su materialización física temprana.

## DT-038 — Observability se valida con el verifier actual

Las conclusiones históricas sobre limitaciones de observability no se elevan a propiedades permanentes; se usa evidencia del verifier vigente.

## DT-039 — Ramas históricas se clasifican con evidencia

La auditoría de ramas usa ancestry, igualdad de tree y patch-equivalence. Las decisiones de cierre se ligan al SHA auditado.

## DT-040 — Google Sheets fue backend temporal de una fase anterior

En esa etapa Google Sheets se seleccionó como almacenamiento temporal estructurado. Esta decisión queda **supersedida por DT-043** para la arquitectura productiva actual.

## DT-041 — `prod_pending_*` también es identidad determinista protegida

El prefijo no basta: la identidad pendiente se recalcula y valida. Un ID pendiente forjado falla cerrado.

## DT-042 — Materialización MDM diferida en la etapa de una sola fuente

Durante la fase temprana no se materializaron estructuras MDM sin necesidad real. La decisión fue válida para aquella etapa; la arquitectura multi-fuente actual se rige por la homologación productiva y DT-043/DT-044.

## DT-043 — Turso/libSQL es el backend comercial productivo vigente

Google Sheets deja de ser el backend temporal seleccionado para el producto actual. El estado comercial productivo compartido se mantiene en **Turso/libSQL**, con SQLite como equivalente local/reproducible.

`products`, `locations`, `price_history` y `scrape_runs` forman la base comercial común multi-fuente. La capa de homologación es derivada y reconstruible. Ningún frontend consulta Turso directamente.

Esta decisión supersede DT-040 como selección de backend vigente sin borrar la evidencia histórica de esa fase.

## DT-044 — RPI usa contratos B2B y B2C separados

La capa SERVE actual se divide deliberadamente en:

- `rpi-business-mart/v1`: privado, B2B / Power BI;
- `rpi-consumer-mart/v2`: público, comparación analítica segura;
- `rpi-consumer-catalog/v3`: público, navegación escalable de Compra Inteligente.

El Consumer Catalog separa visibilidad de comparabilidad. Una oferta individual puede publicarse sin autorización cross-retailer; sólo Python puede producir ranking/recomendación.

`precios-sps-publication/v1` y `precios-sps-static-bi-dataset/v1` quedan como contratos legados/compatibilidad.

## DT-045 — Publicación RPI pública atómica y Business Mart privado

El pipeline derivado valida schema, scope, hashes, tamaños y ausencia de secretos antes de publicar. Consumer Mart v2 y Consumer Catalog v3 se sincronizan a `portfolio-data`; Business Mart v1 permanece dentro del artifact privado B2B.

El navegador carga datos estáticos, no ejecuta Turso ni matching. Un fallo de exportación/sync conserva la publicación last-known-good.

## DT-046 — El catálogo B2C se sirve bajo demanda

El Consumer Catalog v3 usa manifest + facetas + índices bajo demanda + particiones de máximo 250 filas. La partición física sigue grupos de navegación para evitar fan-out excesivo. El arranque no descarga el catálogo completo.

## DT-047 — Reintentos de Los Andes limitados a fallos transitorios de transporte

Después del timeout productivo del 2026-09-10, Comisariato Los Andes permite como máximo un reintento por solicitud únicamente ante `URLError`/`TimeoutError`, con un tope adicional de diez reintentos acumulados y respetando el presupuesto total de intentos. Errores HTTP no se reintentan y la compuerta de completitud permanece fail-closed.
