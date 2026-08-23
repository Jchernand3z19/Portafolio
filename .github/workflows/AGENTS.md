# Reglas adicionales para workflows de Precios Supermercados SPS

Estas reglas adicionales aplican únicamente al trabajar con workflows identificables por nombres o rutas relacionados con `precios-supermercados-sps` o `la-colonia`. No añaden restricciones específicas de La Colonia a workflows ajenos al proyecto.

- No modifiques workflows de Precios Supermercados SPS salvo una tarea humana explícita que autorice trabajo técnico sobre ellos. La instrucción permanente de autonomía del usuario autoriza mantener y mejorar los workflows necesarios para este proyecto.
- Desde la instrucción humana del `2026-08-23T21:02:02Z`, los workflows pueden realizar tráfico público **read-only** de forma autónoma cuando sea necesario para diagnóstico, radiografía, smoke, facet discovery, validación o extracción del catálogo.
- No se requiere un Authorization ID humano por cada ejecución read-only. Los IDs históricos de un solo uso son evidencia y permanecen consumidos; no se reutilizan ni se convierten en nuevos requisitos de interacción humana.
- Todo entrypoint read-only habilitado debe estar acotado: target allowlisted, `concurrency=1` cuando aplique, pacing razonable, deadline/presupuesto finito, sin secretos innecesarios, sin retries ocultos y stop ante 403 persistente, 429, CAPTCHA, login o riesgo de carga excesiva.
- La autorización permanente no permite checkout, compras, formularios con mutación de servidor, cambios de cuenta, bypass anti-bot, secretos nuevos, billing ni infraestructura externa con coste sin intervención humana.
- Un run read-only no concede `production_authority`, `catalog_accepted` ni autoridad de persistencia comercial; esas fronteras deben probarse por los contratos del producto.
- No modifiques mecanismos trusted/privileged sin revisión de seguridad. Nunca ejecutes código no confiable del PR head con credenciales o permisos privilegiados.
- PR #17 y PR #7 están integrados en `main`; cualquier texto histórico que diga que siguen abiertos, draft o congelados es estado obsoleto y no gobierna el repositorio actual.
- `precios-supermercados-sps/.automation/la-colonia-live-command.json` y cualquier solicitud histórica que contenga no equivalen a autoridad comercial.
- `SPS-context-and-root-facets-001`, `LC-location-binding-336`, `LC-location-binding-331`, `LC-location-binding-332`, `LC-location-binding-333`, `LC-location-binding-334`, `LC-location-binding-335` y `LC-location-binding-337` están consumidas; `SPS-context-and-root-facets-002` no concede ninguna autoridad adicional.
- Los markers históricos de IDs consumidos no conceden permiso especial; las nuevas ejecuciones read-only se gobiernan por la autorización permanente y por gates técnicos versionados.
- Todo cambio de workflow requiere revisión explícita de seguridad y validación estática/CI offline cuando corresponda.
- La CI del proyecto debe cubrir cambios por pull request y también pushes a `main` que afecten `precios-supermercados-sps/**` o `.github/workflows/**`.
- Las Actions externas deben continuar referenciadas por SHA completo verificado; no uses tags o ramas mutables.
