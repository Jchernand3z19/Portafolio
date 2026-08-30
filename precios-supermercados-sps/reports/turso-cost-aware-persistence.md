# Persistencia Turso — criterio de eficiencia

Este cambio aplica la metodología reusable de `production-data-engineering` al hot path de persistencia sin introducir tablas persistentes ni servicios nuevos.

## Objetivo

```text
READ NECESSARY SCOPE
-> COMPARE ONCE
-> COMPUTE DELTA
-> WRITE CHANGES ONLY
-> VERIFY AFFECTED SCOPE
```

## Cambios

- `incoming` conserva índice único por identidad fuente.
- La comparación comercial `incoming` vs. periodo actual se materializa una sola vez en una tabla temporal `delta`.
- `close_history` y `open_history` consumen `delta` en vez de repetir la comparación.
- `products` sólo ejecuta `UPDATE` cuando cambia metadata fuente; un run sin cambios no reescribe todo el catálogo.
- La verificación diaria dejó de contar globalmente `products`, `price_history`, `scrape_runs` y todos los periodos abiertos.
- Las verificaciones de histórico diario se acotan a La Colonia SPS/TGU.

## Evidencia exigida antes de producción

- equivalencia funcional con el updater SQLite;
- replay/idempotencia y rollback existentes;
- run sin cambios: una escritura en `scrape_runs`, cero writes de metadata e histórico;
- cambio sólo de metadata: actualizar únicamente el producto afectado, sin abrir histórico comercial;
- regresión de complejidad con N / 2N / 4N para impedir reintroducir comportamiento cuadrático;
- CI completa verde.

La comprobación del ahorro real facturado por Turso queda separada de esta evidencia offline. Después del reset de cuota debe hacerse una sola ejecución controlada y comparar la métrica real del proveedor antes/después. No se usa Turso para tuning que puede demostrarse localmente.
