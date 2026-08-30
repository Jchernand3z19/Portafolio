# Colonial — auditoría y primer probe propuesto

Fecha: 2026-08-30. Estado: `BLOCKED_HUMAN_AUTHORIZATION` para tráfico automatizado
nuevo; `BLOCKED_EXTERNAL` para futura persistencia mientras Turso rechace lecturas.
Este documento no concede autorización, no habilita un workflow y no declara MVP.

## Base auditada

- `Jchernand3z19/Portafolio/main`:
  `f34a324b2cb177baa77ce788c360476268af0f01`.
- Leídos `precios-supermercados-sps/AGENTS.md`, `.github/workflows/AGENTS.md`,
  `docs/PROJECT_STATE.md`, extractor vigente SPS/TGU, schema y updaters SQLite/Turso.
- Cero PRs abiertos al auditar. PRs #340, #341, #343–#346 fusionados; #342 cerrado
  sin merge. Búsqueda de PRs con `Colonial`: cero resultados.
- Sin código, fixtures ni documentación Colonial en el árbol auditado.
- [CI de main](https://github.com/Jchernand3z19/Portafolio/actions/runs/33314520368)
  verde, incluida suite completa. Verificados triggers de PR y push a main.
- Workflow permanente de actualización: `precios-supermercados-sps-la-colonia-mvp-update.yml`,
  con dispatch y schedule. El listado Actions conserva workflows históricos
  marcados `active` cuyas rutas ya no existen en main; ese estado no acredita
  permiso live ni operación vigente. No se habilitó ni despachó ninguno.
- Metodología leída directamente del repositorio privado
  `reusable-engineering-skills`, main
  `47d465c0f9f572bde957204c4caf9c648af983fa`: scraping-fast-path, web-source-recon,
  api-discovery, web-data-extraction, browser-automation, extraction-completeness,
  auditoría/autonomía, seguridad de efectos, provenance, entrega/CI/testing y
  calidad, normalización, histórico, replay y pipeline. No se copiaron skills.

La instrucción actual inicia Colonial sin ampliar La Colonia. Se mantienen las
fronteras de autorización y de persistencia del proyecto. El bloqueo de Turso y
los snapshots recuperables del schedule se detallan en [PROJECT_STATE](../PROJECT_STATE.md).

## Reconocimiento público permitido

La herramienta de investigación web consultó únicamente la
[portada pública](https://supercolonial.com/); las búsquedas de texto posteriores
reutilizaron esa misma vista. Es evidencia de contenido público, no una captura
HTTP RAW ni una sesión de navegador reproducida.

Observado:

- Catálogo con categorías, enlaces de producto, precios en HNL y precios tachados.
- Ejemplo promocional: LEYDE QuesilloTipo Sureno 1Lb, L 101.19 y L 118.99 tachado.
- Ejemplo agotado: COLONIAL Tequeños 8 Un, L 119.99, control «Agotado».
- Delivery/Pick Up anuncia San Pedro Sula, Honduras.
- Errores de plantilla Liquid y rutas de comercio compatibles con Shopify.

**Shopify es una hipótesis**, pendiente de evidencia cruda de plataforma.
No hay request JSON demostrada, product/variant IDs verificados ni muestra
estructurada aceptada. No se considera «in_stock» todo producto sólo por mostrar
precio. No se abrió carrito, checkout, login ni formularios.

No se observó selector comercial por sucursal en el texto disponible; esto no
prueba su ausencia en DOM/JavaScript. `colonial_sps` sigue siendo la hipótesis de
ubicación lógica única. Cookies/storage, variables de inventario/sucursal y
binding comercial están `not_tested`; no se crean ubicaciones físicas por inferencia.

## Primer probe: plan acotado, NO AUTORIZADO

Objetivo: confirmar plataforma y obtener primero un producto correcto, luego
20–50 productos, casos comerciales representativos y evidencia mínima de recorrido.

Scope permitido propuesto: sólo GET públicos a `https://supercolonial.com`, sin
credenciales, cookies privadas, assets visuales, mutaciones ni browser por producto.
No se consultará una API de administración ni se usará una identidad alternativa.

Presupuesto máximo: **10 requests HTTP**, contando redirects y retries;
concurrencia 1, pacing mínimo 1 segundo, timeout por request 20 segundos,
deadline total 5 minutos. No se repite una URL ya recibida y validada. Ningún
retry automático; un retry explícito por error transitorio sólo si cabe en los
10 requests. Stop ante 401/403/429, CAPTCHA, login o degradación sostenida.
Un 404 de una hipótesis permite otra superficie pública dentro del mismo presupuesto.

Orden adaptativo (no ejecutar todas las alternativas por defecto):

1. Un GET del documento inicial para confirmar plataforma, JSON embebido y
   posibles parámetros/contexto comercial; conservar RAW y SHA.
2. Si Shopify queda confirmado, probar inmediatamente la hipótesis pública
   `/products.json?limit=1&page=1`. Ese endpoint no está demostrado aún.
3. Sólo si devuelve identidad/nombre/precio correctos: una página de 40 productos
   del listado y validación offline de todas sus variantes.
4. Hasta dos recursos de producto/colección ya enlazados, si la muestra no incluye
   promoción, precio regular o agotado; priorizar JSON/estado antes de HTML.
5. Sólo con muestra aceptada: dos páginas consecutivas del listado con el mayor
   tamaño normal que la fuente permita comprobar (250 es candidato, no capacidad
   demostrada). Medir identidades, overlap, orden y productos por request.
6. Usar el saldo, hasta el máximo global, para la colección general, sitemap o
   metadata pública que ofrezca total/membership y contexto. No recorrer todo el
   sitemap ni completar el catálogo dentro de este probe.

Si el listado no funciona, volver al HTML/estado ya capturado y usar sólo una
alternativa pública justificada. No construir código productivo para una hipótesis
fallida. Si el scope depende de navegador, dejar esa necesidad explícita para una
autorización posterior acotada.

Resultados esperados: cuerpos RAW reutilizables, status/content type/URL/fecha/SHA,
identidad producto-variante-SKU, semántica precio/compare-at/promoción/disponibilidad,
scope y campos unknown, paginación y mejor señal independiente de completitud.
No afirmar completitud usando únicamente conteo de las propias filas.

## Preflight del full crawl todavía no calculable

`expected_products`, `expected_items`, `page_size`, `expected_pages`,
`expected_requests`, duración, límites y recovery: **desconocidos** hasta el probe.
No usar las cifras de La Colonia ni un supuesto de 8,000 productos como total Colonial.
Una vez comprobados N y P, el listado lineal costaría aproximadamente `ceil(N/P)`
más requests de evidencia/terminación y recovery autorizado, sin página por producto.

La autorización del probe no cubrirá full crawl, segunda observación ni recurrencia.

## Integración existente, sin implementación anticipada

El schema actual ya separa `supermarket_id` y `location_id` en cinco tablas.
Los updaters vigentes validan explícitamente La Colonia; no se puede pasar Colonial
renombrado como La Colonia ni cambiar constantes globales para simular otro proveedor.
Después de demostrar fuente y catálogo, adaptar sólo la responsabilidad común
necesaria, conservando ambos validadores específicos e identidades fuente aisladas.

Verificación offline ejecutada: los siete tests existentes de los updaters SQLite
y Turso pasaron; el SQL remoto se prueba localmente. Eso **no demuestra** todavía
aislamiento Colonial, parser Colonial ni los trece escenarios exigidos para el MVP.
Esos tests se incorporarán con el contrato Colonial real, sin fabricar fixtures
presentadas como capturas de la fuente.

No se modificaron código productivo, tablas, persistencia, configuración live ni
workflow. No se descargaron imágenes ni scripts del supermercado. El siguiente
paso técnico es la primera observación automatizada autorizada, no arquitectura.
