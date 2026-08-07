# Reglas adicionales para workflows de Precios Supermercados SPS

Estas reglas adicionales aplican únicamente al trabajar con workflows identificables por nombres o rutas relacionados con `precios-supermercados-sps` o `la-colonia`. No añaden restricciones específicas de La Colonia a workflows ajenos al proyecto.

- No modifiques workflows de Precios Supermercados SPS salvo tarea humana explícita.
- No ejecutes ni introduzcas tráfico live automáticamente y no habilites `workflow_dispatch` live por iniciativa propia.
- No modifiques mecanismos trusted/privileged sin autorización. Nunca ejecutes código no confiable del PR head con credenciales o permisos privilegiados.
- PR #17 permanece congelado salvo una tarea explícita dedicada a él; no lo integres desde tareas de PR #7.
- `precios-supermercados-sps/.automation/la-colonia-live-command.json` y cualquier solicitud histórica que contenga no equivalen a autorización.
- `SPS-context-and-root-facets-001` está consumida; `SPS-context-and-root-facets-002` no está autorizada; no hay autorizaciones live activas.
- Sin autorización explícita están prohibidos full crawl, `baseline500-003`, `validation500` y facet discovery live.
- Todo cambio de workflow requiere revisión explícita de seguridad y validación estática/CI offline cuando corresponda. La ejecución remota queda para la CI normal autorizada.
