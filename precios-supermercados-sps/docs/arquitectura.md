# Arquitectura inicial

## Principios

- Un supermercado se incorpora a la vez.
- Cada extractor entrega los mismos contratos y nombres de campos.
- La observación fuente se conserva separada de la interpretación.
- Una oferta parcial legítima se conserva y genera revisión; no se descarta ni se completa con datos inventados.
- Una ejecución incompleta se rechaza como ejecución y no se convierte en un nuevo estado comercial.
- La desaparición puntual no equivale automáticamente a `out_of_stock`.
- El precio regular informado no prueba una reducción real.
- La reducción real se calculará contra el último `current_price` histórico aceptado de la misma oferta.
- La IA asesora ante cambios estructurales; una persona aprueba cualquier modificación de producción.

## Flujo previsto

```text
Sitio público
  -> extractor específico
  -> RawProduct
  -> normalización parcial o completa
  -> NormalizedOffer + review_status + pending_fields
  -> validación y quality_events
  -> ValidatedOffer + state_hash
  -> validación de completitud de la ejecución
  -> fact_scrape_runs
       -> accepted: comparar y persistir oferta/historial
       -> rejected/failed/abandoned: conservar métricas y eventos, no actualizar comercio
  -> Google Sheets temporal
  -> Power BI
```

## Observaciones incompletas legítimas

La falta de marca, categoría, subcategoría o presentación interpretable no elimina el producto. Estos campos se guardan como nulos, se enumeran en `pending_fields` y producen `review_status = needs_review` y eventos `pending_normalization`.

La regla de precio depende de `availability`:

- `in_stock`: `current_price` es obligatorio y mayor que cero;
- `out_of_stock`, `not_listed`, `unknown`: `current_price` puede ser nulo.

## Puerta de actualización comercial

La persistencia futura evalúa la ejecución completa antes de modificar `fact_offers_current` o `fact_offer_history`.

- `success`: actualización permitida.
- `warning`: permitida solo cuando los eventos no son bloqueantes.
- `rejected`: extracción técnicamente terminada pero incompleta o inconsistente; no actualiza.
- `failed`: error técnico; no actualiza.
- `abandoned`: ejecución inconclusa; no actualiza.
- `running`: no actualiza.

Esto evita interpretar una caída de cobertura, una página faltante o un cambio de estructura como agotado, producto eliminado o reducción de precio.

## Identidad

Las llaves no URL conservan el valor exacto con trim. La URL estable elimina solo tracking inequívoco. Todos los componentes obligatorios se validan antes de generar hashes.

## Persistencia histórica

Solo ejecuciones aceptadas pueden abrir o cerrar periodos. El proceso será idempotente por `scrape_run_id`, `offer_id` y `state_hash`. `change_type` resume el cambio y `changed_fields` conserva el detalle exacto.

## Riesgos y controles

| Riesgo | Control |
|---|---|
| SKU cambia por mayúsculas | Se conserva el caso exacto; no se aplica `casefold` a llaves fuente no URL. |
| URL funcional se altera | Solo se eliminan `utm_*`, `gclid`, `fbclid`, `msclkid`, `mc_cid`, `mc_eid`. |
| Producto parcial se pierde | Campos opcionales, `pending_fields`, `review_status` y eventos de calidad. |
| `in_stock` sin precio | Rechazo de la oferta individual y evento bloqueante. |
| Extracción incompleta altera precios | Puerta de completitud; ejecución `rejected` sin actualización comercial. |
| Doble periodo | Un solo periodo abierto por `offer_id` e idempotencia de reintentos. |
| Falso agotado | `not_listed` o `unknown` solo desde una ejecución aceptada y reglas del adaptador. |
| IA altera producción | Cambios humanos mediante rama, pruebas y PR. |
