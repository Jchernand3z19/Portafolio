# Decisiones técnicas

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

GATE-17 no se considera cerrado sólo porque exista un ruleset configurado. La evidencia productiva exige observar a GitHub bloquear merges reales.

En PR #29, con `main` reportado como `protected: true`, GitHub rechazó un intento de merge mientras `tests` estaba en progreso. Después de que el check terminó en `success`, un segundo intento fue rechazado por una conversación de review sin resolver. Tras resolver el hilo y volver a validar el head final, el merge fue permitido.

Por esa evidencia, `GATE-17 = PASS_PRODUCTIVE_EVIDENCE`. Esto protege la gobernanza de `main`, pero no concede autoridad live ni sustituye provenance físico.

## DT-031 — Diseño Google Cloud evaluado y supersedido

La arquitectura con Cloud Run, Direct VPC egress, Secure Web Proxy, Cloud Logging y Cloud KMS fue diseñada como una posible frontera física independiente. No llegó a convertirse en infraestructura productiva y dejó de ser la ruta seleccionada cuando la implementación Cloudflare alcanzó las fronteras necesarias con menor dependencia operativa.

Se conserva esta decisión únicamente como historial arquitectónico.

## DT-032 — Cloudflare es la frontera física seleccionada

La ruta seleccionada usa **Cloudflare Workers + Durable Objects SQLite + GitHub OIDC + Ed25519 + Workers Observability**.

La implementación fija repo, repository ID, `main`, workflow, environment, event, audience, host/path/método y límites. El caller no puede elegir un destino arbitrario. El Durable Object controla presupuesto, pacing, single-flight, replay y fencing. El Worker liga receipts Ed25519 a request, run, commit, release y respuesta cruda; la capa Python verifica firma/body y reconcilia evidencia contra Workers Observability.

Esta decisión describe la arquitectura elegida. La autoridad productiva sigue separada de la mera existencia de infraestructura.

## DT-033 — Completitud técnica no equivale a aceptación productiva

La cadena puede cerrar structural discovery autenticado, derivar el plan canónico, verificar receipts, reconciliar observability y construir un manifest completo. `CatalogAcceptanceReadiness` separa explícitamente completitud técnica de autoridad productiva y no produce por sí mismo `catalog_accepted=true` ni `production_authority=true`.

## DT-034 — Cloudflare se prueba primero contra un origen controlado no-La-Colonia

Antes de cualquier validación física del collector contra La Colonia, la infraestructura Cloudflare se prueba contra un origen controlado propio. La sonda usa Worker de origen, gateway, Durable Object, OIDC audience/environment, claves, signing key ID, schema y dominio criptográfico separados de la ruta productiva.

El caller no suministra la URL física. La sonda rechaza La Colonia antes de cualquier fetch. Un receipt de sonda no puede convertirse en evidencia de catálogo ni conceder autoridad productiva.

## DT-035 — `la_colonia_online` es contexto fuente, no ubicación comercial

El extractor de La Colonia conserva `location_id=la_colonia_online` únicamente como identidad del contexto raw del catálogo público en línea. Este ID no representa SPS, Tegucigalpa ni una tienda y debe permanecer `location_status=unknown`, sin `location_confidence`.

La normalización falla cerrada si un `RawProduct` registrado bajo ese contexto intenta declararse `confirmed` o `inferred`. El binding de ubicación debe producir una ubicación comercial distinta (`la_colonia_sps`, una tienda futura, etc.) sólo después de evidencia técnica suficiente. Así se impide que el nombre de un contexto fuente se convierta accidentalmente en autoridad geográfica.

## DT-036 — GTIN válido es identidad fuerte; lo demás queda pendiente

Un barcode sólo puede crear automáticamente un `product_id` cross-supermercado cuando es GTIN-8/12/13/14 numérico y supera el check digit. Su representación canónica es GTIN-14 y el ID derivado es `prod_gtin_<gtin14>`.

Si el barcode falta o no es GTIN válido, la observación no se descarta: conserva un `prod_pending_*` ligado al `source_product_id` y `pending_product_mapping`. Un resolver explícito/revisado puede asignar posteriormente otro `product_id` sin cambiar `source_product_id` ni `offer_id`.

## DT-037 — Producto normalizado y mapping fuente son tablas distintas

El contrato tabular común incorpora:

```text
dim_products
map_source_products
```

`dim_products` contiene sólo atributos normalizados/canónicos por `product_id`; no incluye supermercado, ubicación, precio, promoción, disponibilidad, URL fuente ni run. `map_source_products` conserva la relación por `source_product_id`, descriptores fuente, `product_id`, método/estado de mapping y razón de revisión.

Con estas dos tablas el contrato gestionado pasa de seis a ocho tablas. Un run no aceptado no materializa dimensión/mapping/current/history.

## DT-038 — Observability se valida con el verifier actual, no con la limitación histórica

La conclusión histórica de que la superficie pública de Workers Observability no podía exponer el detalle necesario no se usa como una propiedad arquitectónica permanente. El código actual descubre candidatos y consulta detalle con `view: events`, exigiendo custom span único, relación padre-hijo y fetch físico reconciliado con el receipt.

La frontera sigue abierta hasta observar una ejecución exitosa del verifier actual contra la evidencia física de la sonda existente. Esa comprobación no requiere una nueva request a La Colonia ni concede autoridad de catálogo.

## DT-039 — Ramas históricas se clasifican con evidencia y decisión versionada

La auditoría de ramas `precios-sps` usa ancestry, igualdad de tree y patch-equivalence antes de recurrir a inspección manual. Las decisiones `CLOSED_SUPERSEDED` quedan versionadas y ligadas al SHA exacto de `main` auditado.

El inventario falla cerrado si cambia el snapshot sin renovar la inspección, aparece una rama no resuelta o queda un `UNIQUE_UNMERGED`. El cierre de una rama histórica nunca sustituye la recuperación focalizada de hardening útil; ese patrón se aplicó al hardening de evidencia física recuperado antes del cierre del inventario.
