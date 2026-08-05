# Arquitectura inicial

## Principios

- Un supermercado se incorpora a la vez.
- Cada extractor entrega el mismo contrato común.
- La observación fuente se conserva separada de la normalización.
- Una ausencia puntual no equivale automáticamente a `out_of_stock`.
- El precio regular informado no prueba una reducción real.
- La reducción real se calculará contra el último `current_price` histórico de la misma oferta.
- La IA asesora ante cambios estructurales; una persona revisa y aprueba cualquier modificación de producción.

## Flujo previsto

```text
Sitio público
  -> extractor específico del supermercado
  -> RawProduct
  -> normalización e identidad
  -> NormalizedOffer
  -> validaciones y eventos de calidad
  -> ValidatedOffer + state_hash
  -> comparación con estado actual
  -> Google Sheets temporal
  -> Power BI
```

BigQuery y Cloud Run quedan fuera de la fase inicial y solo se incorporarán cuando exista estabilidad operativa y volumen que lo justifique.

## Componentes de esta entrega

### `enums.py`

Vocabulario cerrado para disponibilidad, ubicación y tipo de llave fuente. Evita que cada scraper invente valores distintos.

### `models.py`

Contratos inmutables con validaciones de campos obligatorios, decimales, URLs, zona horaria, evidencia de ubicación y enums.

### `identifiers.py`

- selección de llave estable por prioridad;
- `source_product_id` por supermercado y llave fuente;
- `offer_id` por supermercado, ubicación y producto fuente;
- `state_hash` por atributos relevantes del periodo.

### Pruebas

Validan estabilidad, rechazo de valores inválidos y comportamiento histórico esperado.

## Límites de responsabilidad

### Extractor específico

Debe localizar el producto, obtener valores fuente, registrar evidencia y producir `RawProduct`. No debe decidir por sí solo que una oferta es real ni escribir directamente en almacenamiento.

### Normalizador

Debe estandarizar nombre, marca, categoría, presentación, cantidades y unidades sin perder los valores originales.

### Validador

Debe comprobar el contrato, generar `state_hash` y producir eventos de calidad. Los errores no deben descartarse silenciosamente.

### Persistencia futura

Debe ser idempotente: un reintento con el mismo `scrape_run_id`, `offer_id` y estado no puede duplicar historial.

## Riesgos y controles

| Riesgo | Control inicial |
|---|---|
| Identidad cambia por precio | El precio no participa en `source_product_id` ni `offer_id`. |
| URL contiene campañas | La llave URL elimina parámetros de seguimiento y fragmentos. |
| Doble periodo actual | Regla de unicidad por `offer_id` en persistencia. |
| Falso agotado por desaparición | Usar `not_listed` o `unknown` hasta confirmar. |
| Fechas ambiguas | Todos los timestamps de auditoría deben ser UTC y conscientes de zona. |
| Redondeo monetario | Uso de `Decimal`, no `float`, en los contratos. |
| Cambio cosmético abre historial | El hash normaliza espacios y mayúsculas y excluye URLs. |
| IA altera producción | Solo recomendaciones; cambio humano mediante rama, pruebas y PR. |
| Impacto en Mundial o sitio | Proyecto encapsulado; no se registrará tarjeta en esta fase. |
