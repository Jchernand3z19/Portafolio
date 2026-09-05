# Homologación de productos — cierre productivo 2026-09-05

La capa derivada `product_homologation_profiles` quedó cargada en Turso y su mantenimiento diferencial quedó integrado a `main`.

## Resultado productivo

- 56,779 productos fuente actuales.
- 56,779 perfiles derivados persistidos: cobertura 100%.
- 34,365 perfiles con GTIN válido.
- 18,748 perfiles con `product_type` clasificado.
- Estados de comparación: 18,773 `ready`, 2,558 `review_required`, 13,034 `single_source`, 22,414 `unmapped`.
- 8,126 grupos canónicos `ready` y 961 grupos canónicos retenidos para revisión.

La homologación permanece separada de `products` y `price_history`. Recalcular nombre normalizado, taxonomía, presentación o identidad canónica no abre ni cierra periodos de precio.

## Carga inicial

La carga inicial se ejecutó en el run `33945353115` y produjo el artifact `9963151121` (SHA-256 `3f141235a982975305b794912203c281a46157c7a93cc2ca5daf4f090a4ca89c`). Insertó 56,779 perfiles sin modificar los 56,779 productos, las 110,002 filas de `price_history` ni los 21 `scrape_runs` existentes.

## Refresh diferencial

El PR #383 quedó fusionado en `main` mediante el commit `1b427026f1383ca5087a5617fae34f1ae15cfad3`.

El refresh compara `profile_hash` y `normalization_version` contra la tabla derivada existente:

- un perfil sin cambios no entra a staging;
- sólo perfiles nuevos o realmente modificados se escriben;
- si todos coinciden, el proceso es un no-op real;
- un perfil existente cuyo `product_id` ya no pertenece al conjunto fuente provoca fallo cerrado;
- el postflight vuelve a exigir cobertura completa, cero violaciones FK, cero periodos actuales duplicados e `integrity_check=ok`.

El workflow permanente `.github/workflows/precios-supermercados-sps-homologation-refresh.yml` se ejecuta después de una actualización diaria exitosa de `La Colonia - Actualización MVP` sobre `main` para ejecuciones programadas o manuales, y también admite `workflow_dispatch` directo. Usa checkout inmutable, permisos `contents: read` y acciones fijadas por SHA.

## Verificación productiva de no-op

Se ejecutó una verificación independiente usando exactamente el código ya fusionado en `main`:

- run `33946558257`;
- artifact `9963520883`;
- SHA-256 del artifact `f8e3a9540ba46081c3d7815ac12d384e2940c5c8ca374bdfe017496e4ec6c4e7`;
- 56,779 perfiles procesados;
- `inserted=0`;
- `updated=0`;
- `unchanged=56779`;
- `no_op=true`;
- `staging_written=false`;
- tabla staging ausente al finalizar;
- `products=56779`, `price_history=110002`, `scrape_runs=21` y `profiles=56779` idénticos antes y después;
- cero violaciones FK, cero periodos actuales duplicados e `integrity_check=ok`.

## CI

- PR #383: run `33946205303` — **2,123 passed en 190.41 s**.
- `main` después del merge: run `33946387842` — **2,123 passed en 173.22 s**.

La evidencia estructurada completa está en [`production-evidence.json`](production-evidence.json).
