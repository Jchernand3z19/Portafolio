# La Colonia — diagnóstico de navegador para contexto SPS

## 1. Objetivo

Preparar una herramienta **offline-first** que resuelva la limitación observada en
`SPS-context-and-root-facets-001`:

```text
tool_cannot_interact_with_store_selector_or_inspect_session_context
```

La herramienta permite probar offline la lógica necesaria para que una futura
ejecución, con una autorización nueva y explícita, pueda usar un navegador real,
seleccionar San Pedro Sula mediante la UI pública, observar el contexto técnico
VTEX, capturar raíz/facets mínimas y producir un diagnóstico sanitizado.

Esta etapa **no ejecutó navegación live**, no seleccionó San Pedro Sula y no
consultó raíz ni facets de La Colonia.

## 2. Auditoría previa

En el head inicial `18f06c12c895e988719336c8907769322c000377`:

- `requirements.txt` solo contenía `pytest>=8.3,<10`;
- no existía `package.json` en la raíz ni en `precios-supermercados-sps/`;
- no se encontraron Playwright, Selenium ni Puppeteer en el repositorio;
- el proyecto ya utiliza Python 3.12 en CI;
- los diagnósticos existentes están implementados en Python.

Por ello la alternativa de menor acoplamiento es **Playwright para Python**.

## 3. Tecnología elegida

```text
tecnología = Playwright Python
dependencia = playwright>=1.45,<2
browser download = no ejecutado
```

La dependencia de Python se agrega para dejar reproducible el adaptador futuro.
El paquete del navegador (`playwright install chromium`) **no se descarga** en
esta etapa porque las pruebas unitarias no lo necesitan.

La importación de Playwright es perezosa y ocurre únicamente dentro de
`run_live`. `offline_fixture` no importa Playwright, no inicia browser y no
requiere binarios del navegador.

## 4. Arquitectura

Se separan seis responsabilidades:

| Capa | Responsabilidad | Estado en esta etapa |
|---|---|---|
| A | navegación/interacción DOM | implementada; live no ejecutado |
| B | captura técnica request/response/GraphQL/storage | implementada |
| C | sanitización | implementada y probada |
| D | análisis de contexto | implementado con `observed=true/false` |
| E | persistencia temporal sanitizada | implementada y probada |
| F | tráfico real | deshabilitado/no ejecutado |

El módulo está separado de `RawProduct`, `NormalizedOffer`,
`ValidatedOffer`, scraper, runner y contratos comerciales.

## 5. Módulo

```text
src/precios_supermercados/diagnostics/la_colonia_sps_context_diagnostic.py
```

Modelo principal:

```text
SpsContextDiagnostic
```

Campos:

- `test_id`;
- `started_at`;
- `completed_at`;
- `mode`;
- `browser`;
- `initial_location_text`;
- `selected_city`;
- `selected_store`;
- `location_status`;
- `context_evidence`;
- `cookies_observed`;
- `local_storage_observed`;
- `session_storage_observed`;
- `requests`;
- `root`;
- `facets`;
- `stability`;
- `redactions`;
- `errors`;
- `warnings`;
- `stop_reason`;
- `logical_requests`.

Es un modelo **diagnóstico**, no un contrato comercial.

## 6. Detectores DOM

La estrategia no depende de clases CSS generadas ni posiciones visuales.

Orden de resolución:

1. role;
2. accessible name;
3. label;
4. text;
5. atributos semánticos;
6. `select`;
7. `button`;
8. `combobox`;
9. `dialog`;
10. fallback estructural.

Targets preparados:

```text
Selecciona tu tienda
San Pedro Sula
Plaza Pedregal
```

No se utiliza `nth(3)` ni otro índice visual. Una ausencia produce
`DomTargetNotFound`; dos coincidencias de la misma prioridad producen
`AmbiguousDomTarget`. Ambos casos detienen la futura ejecución.

## 7. Interacción Playwright futura

El adaptador `run_live` queda preparado conceptualmente para:

1. crear `browser.new_context()` limpio;
2. abrir la home;
3. localizar `Selecciona tu tienda`;
4. abrir el selector;
5. localizar `San Pedro Sula`;
6. seleccionar la ciudad;
7. localizar `Plaza Pedregal`;
8. seleccionar la tienda mediante UI;
9. capturar storage/cookies antes/después;
10. determinar si existe evidencia técnica de cambio;
11. ir a `/supermercado`;
12. interceptar el request GraphQL real de catálogo;
13. abortarlo antes de enviarlo mientras se captura su forma;
14. reutilizar ese mismo endpoint/operation/query con `from=0`, `to=4`;
15. obtener raíz/facets mínimas;
16. repetir una vez;
17. comparar estabilidad;
18. persistir solo diagnóstico sanitizado;
19. cerrar browser.

El endpoint, `operationName`, query y facets futuras deben provenir del request
real observado. La herramienta no inventa store IDs, region IDs, bindings,
sales channels o endpoints alternos.

## 8. Captura de network

Se consideran relevantes `xhr` y `fetch`.

Por evento se conserva únicamente metadata necesaria:

- URL sanitizada;
- método;
- resource type;
- `operationName`;
- clasificación;
- variables estructurales;
- `from`;
- `to`;
- `orderBy`;
- `selectedFacets`;
- `map`;
- status;
- content-type.

Clasificaciones GraphQL:

```text
productSearch
facets
session
segment
region
store
checkout
other
```

Los payloads completos no se persisten automáticamente.

La función `build_minimal_graphql_replay` conserva el request real observado y
solo reduce su ventana a un máximo de cinco resultados.

## 9. Contexto VTEX

Se preparó observación —sin asumir presencia— de:

```text
vtex_session
vtex_segment
regionId
salesChannel
binding
postalCode
country
pickupPoint
store
seller
```

Cada mecanismo reporta:

```json
{
  "name": "vtex_segment",
  "observed": true,
  "changed_after_store_selection": true
}
```

Un nombre esperado no implica `observed=true`.

En live, `location_status=confirmed` solo puede asignarse si se observa cambio
técnico en uno de los mecanismos registrados después de seleccionar la tienda.
Cuando solo cambia la UI se clasifica `ui_only`.

## 10. Sanitización

La sanitización es central y se aplica antes de persistir.

Se redactan:

- valores de cookies;
- `Authorization`;
- tokens;
- JWT;
- API keys;
- IDs de sesión;
- orderForm IDs;
- direcciones;
- códigos postales;
- coordenadas;
- email;
- teléfono;
- secretos/opacos.

Para cookies/storage se conserva:

```text
name
storage_type
observed
value = redacted
length
sha256
changed_after_store_selection
```

El SHA-256 es únicamente una huella de cambio; no permite publicar el valor.

## 11. Modos y barreras

### offline_fixture

Es el modo predeterminado.

Requiere únicamente:

```text
--fixture-dom
--fixture-network
```

No inicia browser y no abre sockets.

### live

Para entrar al adaptador futuro deben existir simultáneamente:

```text
--live
--authorization-id <ID>
```

Sin `--authorization-id`, falla.

`SPS-context-and-root-facets-001` está declarado como consumido y falla aunque
se intente suministrarlo.

No existe una autorización hardcodeada para `002` y esta etapa **no crea
SPS-context-and-root-facets-002**.

Una ejecución live futura necesita una autorización nueva fuera del código.

## 12. Presupuesto

Defaults cerrados:

```text
max_logical_requests = 8
concurrency = 1
minimum_delay_seconds = 1.5
max_retries = 1
```

Protecciones:

- `max_logical_requests` no puede superar 8;
- `concurrency` debe ser exactamente 1;
- delay no puede bajar de 1.5 s;
- retries no puede superar 1;
- al agotar presupuesto se lanza `LogicalRequestBudgetExceeded`.

Las pruebas usan reloj sintético; no duermen 1.5 s reales.

## 13. Fixtures sintéticos

Se crean dos fixtures totalmente artificiales:

```text
tests/fixtures/la_colonia_sps_context_diagnostic.html
tests/fixtures/la_colonia_sps_context_diagnostic.json
```

Representan:

- selector cerrado;
- selector abierto;
- San Pedro Sula;
- Plaza Pedregal;
- cambio de contexto;
- request/response GraphQL root;
- request/response facets;
- cookie sintética;
- localStorage sintético;
- sessionStorage sintético;
- token ficticio;
- orderForm ficticio;
- región/sales channel/seller ficticios.

No contienen cookies ni sesiones reales.

## 14. Pruebas offline

El archivo:

```text
tests/test_la_colonia_sps_context_diagnostic.py
```

cubre, entre otros:

1. selector `Selecciona tu tienda`;
2. San Pedro Sula;
3. Plaza Pedregal;
4. ausencia de ciudad;
5. ambigüedad;
6. clasificación productSearch;
7. clasificación facets;
8. `operationName`;
9. `from/to`;
10. `selectedFacets`;
11. requests GET/POST;
12. replay mínimo;
13. resumen root;
14. clasificación de facets;
15. cookies redactadas;
16. Authorization redactado;
17. tokens redactados;
18. orderForm no expuesto;
19. cambios de storage;
20. `observed` real para mecanismos VTEX;
21. contador lógico;
22. límite de budget;
23. `concurrency=1`;
24. delay mínimo;
25. retries;
26. live sin authorization-id;
27. authorization-id consumido;
28. offline no acepta authorization-id;
29. persistencia sanitizada;
30. Playwright importado solo dentro de live;
31. URL sanitizada;
32. cero red.

## 15. Prueba explícita de cero red

No se usa la búsqueda textual autorreferencial que produjo la regresión anterior.

La prueba instala un **tripwire** en el transporte real de Python:

```text
socket.socket.connect
socket.create_connection
```

Si `offline_fixture` intenta abrir red, la prueba falla inmediatamente con
`AssertionError`.

El tripwire no silencia errores; convierte cualquier intento de red en fallo.

Además se verifica mediante AST que Playwright no sea un import de nivel de
módulo, por lo que cargar el diagnóstico offline no inicia infraestructura de
browser.

## 16. Ejecución offline

Ejemplo reproducible:

```bash
PYTHONPATH=precios-supermercados-sps/src python -m precios_supermercados.diagnostics.la_colonia_sps_context_diagnostic \
  --fixture-dom precios-supermercados-sps/tests/fixtures/la_colonia_sps_context_diagnostic.html \
  --fixture-network precios-supermercados-sps/tests/fixtures/la_colonia_sps_context_diagnostic.json \
  --output /tmp/la-colonia-sps-context-diagnostic.json
```

Este comando usa exclusivamente fixtures sintéticos.

## 17. Ejecución live futura

No ejecutada en esta etapa.

Forma conceptual:

```bash
python -m precios_supermercados.diagnostics.la_colonia_sps_context_diagnostic \
  --live \
  --authorization-id <NUEVA_AUTORIZACION_EXPLICITA> \
  --output <ruta_temporal>
```

Antes de una ejecución futura también será necesario instalar el browser
Playwright correspondiente, por ejemplo Chromium. Esa descarga **no se realizó
ahora**.

No usar `SPS-context-and-root-facets-001`: está consumida.

No se asigna ni crea `SPS-context-and-root-facets-002`.

## 18. Qué NO fue ejecutado

En esta etapa:

```text
tráfico a La Colonia = 0
SPS seleccionado = no
root consultado = no
facets consultadas = no
productos descargados = 0
full crawl = no
recorrido por categorías = no
facet discovery = no
workflow live = no
```

No se ejecutó `--live`.

## 19. Limitaciones

La integración real con el DOM y los eventos específicos de La Colonia no puede
validarse hasta una futura autorización live. Los fixtures demuestran
comportamiento del diagnóstico, no confirman selectores reales ni contexto VTEX
actual.

Playwright Python queda instalado como dependencia, pero el binario Chromium no
forma parte de esta etapa.

## 20. Decisión

La limitación observada en `001` queda abordada mediante una herramienta
reproducible, offline-first, sanitizada y protegida.

La siguiente ejecución live permanece **Pendiente** y requiere una autorización
nueva. No se autoriza automáticamente ningún ID ni ninguna prueba.
