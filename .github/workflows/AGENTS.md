# Reglas adicionales para workflows de Precios Supermercados SPS

Estas reglas adicionales aplican únicamente al trabajar con workflows identificables por nombres o rutas relacionados con `precios-supermercados-sps` o `la-colonia`. No añaden restricciones específicas de La Colonia a workflows ajenos al proyecto.

- La instrucción permanente de autonomía del usuario autoriza mantener y mejorar técnicamente los workflows necesarios para este proyecto mediante GitHub, PR y CI.
- **Autonomía técnica no equivale a autorización live.** Una observación nueva contra páginas/APIs externas requiere una instrucción humana explícita y vigente cuando el alcance no esté ya cubierto por una autorización específica todavía válida.
- No inventes, amplíes ni reutilices una autorización histórica. Los IDs/markers consumidos o cerrados son evidencia histórica y no conceden permiso operativo nuevo.
- El binding de San Pedro Sula ya fue demostrado por evidencia live persistida; su workflow queda manual y fail-closed hasta que exista una nueva autorización explícita para repetir esa observación.
- El siguiente `facet_discovery`, smoke de catálogo, recorrido por categorías o full crawl son alcances live distintos del binding histórico. No los actives por inferencia ni por reutilizar markers previos.
- Todo entrypoint read-only que llegue a habilitarse debe estar acotado: target allowlisted, `concurrency=1` cuando aplique, pacing razonable, deadline/presupuesto finito, sin secretos innecesarios, sin retries ocultos y stop ante 403 persistente, 429, CAPTCHA, login o riesgo de carga excesiva.
- Ninguna autorización read-only permite checkout, compras, formularios con mutación de servidor, cambios de cuenta, bypass anti-bot, secretos nuevos, billing ni infraestructura externa con coste sin intervención humana.
- Un run read-only no concede `production_authority`, `catalog_accepted` ni autoridad de persistencia comercial; esas fronteras deben probarse por los contratos del producto.
- No modifiques mecanismos trusted/privileged sin revisión de seguridad. Nunca ejecutes código no confiable del PR head con credenciales o permisos privilegiados.
- PR #17 y PR #7 están integrados en `main`; cualquier texto histórico que diga que siguen abiertos, draft o congelados es estado obsoleto y no gobierna el repositorio actual.
- `precios-supermercados-sps/.automation/la-colonia-live-command.json` y cualquier solicitud histórica que contenga no equivalen a autoridad comercial ni live vigente.
- `SPS-context-and-root-facets-001`, `LC-location-binding-336`, `LC-location-binding-331`, `LC-location-binding-332`, `LC-location-binding-333`, `LC-location-binding-334`, `LC-location-binding-335` y `LC-location-binding-337` están consumidas; `SPS-context-and-root-facets-002` no concede ninguna autoridad adicional.
- Todo cambio de workflow requiere revisión explícita de seguridad y validación estática/CI offline cuando corresponda.
- La CI del proyecto debe cubrir cambios por pull request y también pushes a `main` que afecten `precios-supermercados-sps/**` o `.github/workflows/**`.
- Las Actions externas deben continuar referenciadas por SHA completo verificado; no uses tags o ramas mutables.
