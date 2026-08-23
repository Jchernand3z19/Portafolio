# Reglas adicionales para workflows de Precios Supermercados SPS

Estas reglas adicionales aplican únicamente al trabajar con workflows identificables por nombres o rutas relacionados con `precios-supermercados-sps` o `la-colonia`. No añaden restricciones específicas de La Colonia a workflows ajenos al proyecto.

- No modifiques workflows de Precios Supermercados SPS salvo una tarea humana explícita que autorice trabajo técnico sobre ellos.
- No ejecutes ni introduzcas tráfico live automáticamente y no habilites entrypoints live por iniciativa propia.
- No modifiques mecanismos trusted/privileged sin revisión de seguridad. Nunca ejecutes código no confiable del PR head con credenciales o permisos privilegiados.
- PR #17 y PR #7 están integrados en `main`; cualquier texto histórico que diga que siguen abiertos, draft o congelados es estado obsoleto y no gobierna el repositorio actual.
- `precios-supermercados-sps/.automation/la-colonia-live-command.json` y cualquier solicitud histórica que contenga no equivalen a autorización.
- `SPS-context-and-root-facets-001`, `LC-location-binding-336` y `LC-location-binding-331` están consumidas; `SPS-context-and-root-facets-002` no está autorizada; no hay autorizaciones live activas.
- Los markers históricos de `LC-location-binding-336` y `LC-location-binding-331` no conceden permiso para repetir radiografías ni para otra operación.
- Sin autorización explícita están prohibidos full crawl, `baseline500-003`, `validation500`, facet discovery live y cualquier otro tráfico nuevo hacia La Colonia.
- Todos los jobs capaces de producir tráfico live deben permanecer fail-closed hasta que exista autorización humana nueva y se cierre la frontera productiva correspondiente.
- Todo cambio de workflow requiere revisión explícita de seguridad y validación estática/CI offline cuando corresponda.
- La CI del proyecto debe cubrir cambios por pull request y también pushes a `main` que afecten `precios-supermercados-sps/**` o `.github/workflows/**`.
- Las Actions externas deben continuar referenciadas por SHA completo verificado; no uses tags o ramas mutables.
