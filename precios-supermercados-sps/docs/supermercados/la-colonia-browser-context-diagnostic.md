# La Colonia — diagnóstico de navegador para contexto SPS

## 1. Estado

Este documento describe una herramienta diagnóstica **pre-live**. No autoriza tráfico a La Colonia.

```text
SPS-context-and-root-facets-001 = consumida
SPS-context-and-root-facets-002 = no creada / no autorizada
autorizaciones live activas = 0
tráfico live de esta etapa = 0
SPS seleccionado = no
root consultado = no
facets consultadas = no
```

La herramienta resuelve a nivel de implementación la limitación observada en la prueba 001:

```text
tool_cannot_interact_with_store_selector_or_inspect_session_context
```

La integración contra el sitio real permanece pendiente de una autorización explícita futura.

## 2. Arquitectura

El diagnóstico permanece separado de `RawProduct`, `NormalizedOffer`, `ValidatedOffer`, scraper, runner y contratos comerciales.

Responsabilidades:

1. navegación e interacción DOM;
2. captura técnica de request/response/storage;
3. sanitización;
4. análisis de contexto;
5. persistencia temporal del diagnóstico;
6. tráfico real, bloqueado salvo autorización futura.

Módulo:

```text
src/precios_supermercados/diagnostics/la_colonia_sps_context_diagnostic.py
```

Modelo:

```text
SpsContextDiagnostic
```

## 3. Pre-live hardening

La revisión estática posterior a la primera implementación detectó tres huecos:

1. `validate_live_authorization` validaba formato y consumidos, pero no exigía una allow-list activa;
2. `run_live` persistía `output_path` solamente al terminar con éxito;
3. Playwright estaba instalado como librería, pero el runtime Chromium y los selectores reales del camino Playwright no se habían probado con navegador local/sintético.

Los tres puntos fueron endurecidos antes de cualquier nueva autorización live.

## 4. Allow-list de autorizaciones

Estado del código:

```text
ACTIVE_AUTHORIZATION_IDS = []
CONSUMED_AUTHORIZATION_IDS = [
  "SPS-context-and-root-facets-001"
]
```

La validación diferencia ahora:

- formato inválido;
- ID consumido;
- ID con formato válido pero no autorizado;
- ID realmente presente en la allow-list activa.

Estado esperado y probado:

```text
001 -> reject: consumed
002 -> reject: not authorized
003 -> reject: not authorized
999 -> reject: not authorized
texto inválido -> reject: invalid format
```

Las pruebas demuestran el funcionamiento positivo de la allow-list solamente mediante un ID sintético inyectado en el test:

```text
SPS-context-and-root-facets-777
```

Ese ID no se incorpora a la configuración del proyecto.

### Activación futura de 002

Una futura etapa autorizada tendría que cambiar explícitamente la allow-list para contener **solo**:

```text
SPS-context-and-root-facets-002
```

Ese cambio requeriría una autorización nueva y un commit deliberado. No habilitaría automáticamente 003, 004, 999 ni ningún otro ID.

En esta etapa 002 no se activa.

## 5. Modos

### `offline_fixture`

Es el modo seguro por defecto. Usa fixtures sintéticos y no inicia navegación a La Colonia.

### `live`

Requiere simultáneamente:

```text
--live
--authorization-id <ID_ACTIVO>
```

El ID debe:

1. cumplir el formato;
2. no estar consumido;
3. estar presente en `ACTIVE_AUTHORIZATION_IDS`.

Con la allow-list actual vacía, ningún ID puede iniciar navegador live desde la interfaz normal del proyecto.

## 6. Regla de consumo

El modelo distingue autorización validada de tráfico iniciado.

Campos:

```text
authorization_checked
browser_started
target_navigation_started
target_navigation_completed
store_selector_opened
city_selected
store_selected
context_observed
root_observed
facets_observed
authorization_consumption_eligible
```

Regla preparada para una etapa futura:

```text
antes de page.goto(TARGET_URL): authorization_consumption_eligible = false
inmediatamente antes de page.goto(TARGET_URL):
    target_navigation_started = true
    authorization_consumption_eligible = true
```

Por tanto, un fallo de browser/launch previo al tráfico no consumiría conceptualmente la autorización. Una vez iniciado el intento de navegación al target, el reporte queda marcado como elegible para consumo.

No se implementó persistencia remota del consumo en esta etapa.

## 7. Failure artifacts

`run_live` utiliza una única semántica: **devuelve un `SpsContextDiagnostic` fallido y lo persiste cuando existe `output_path`**.

Ante un fallo posterior al inicio del diagnóstico registra, como mínimo:

```text
completed_at
location_status
logical_requests
errors
warnings
stop_reason
progress checkpoints
```

Los `stop_reason` cubren, entre otros:

- `dom_target_not_found`;
- `ambiguous_dom_target`;
- `logical_request_budget_exceeded`;
- `playwright_timeout`;
- `target_navigation_failed`;
- `store_selector_failed`;
- `city_selection_failed`;
- `store_selection_failed`;
- `product_search_not_observed`;
- `facets_not_observed`;
- `unexpected_http_status`;
- `invalid_json_response`;
- `diagnostic_safety_error`;
- `authorization_rejected`;
- `unexpected_diagnostic_error`.

La persistencia ocurre desde `finally`, de modo que un fallo controlable no elimina el artefacto.

## 8. Sanitización de errores

Nunca se persiste directamente el texto bruto de una excepción sin pasar por `sanitize_error`.

Se redactan:

- `Authorization` y bearer tokens;
- cookies;
- tokens/JWT/API keys;
- session IDs;
- orderForm IDs;
- direcciones;
- códigos postales sensibles;
- coordenadas;
- email/teléfono;
- secretos/opacos;
- query strings sensibles.

Las URLs dentro de errores pasan por `sanitize_url` y conservan solo parámetros estructurales permitidos.

## 9. Detectores DOM

Estrategia escalonada:

1. role;
2. accessible name;
3. label;
4. text;
5. atributos semánticos;
6. select;
7. button;
8. combobox;
9. dialog;
10. fallback estructural.

Targets preparados:

```text
Selecciona tu tienda
San Pedro Sula
Plaza Pedregal
```

No se usan índices visuales como `nth(3)`.

`_pw_unique` falla ante ausencia o ambigüedad. `_pw_activate` puede seleccionar un `select/option` real o hacer click en botones/custom options.

## 10. Runtime Playwright/Chromium

Dependencia Python:

```text
playwright>=1.45,<2
```

La CI resolvió:

```text
Playwright = 1.62.0
```

No se ejecutó `playwright install chromium`.

`launch_compatible_chromium` sigue esta política:

1. usar el Chromium administrado por Playwright cuando su executable existe;
2. de lo contrario buscar un Chrome/Chromium ya presente en el entorno;
3. fallar de forma segura si no existe browser compatible.

Candidatos del sistema:

```text
google-chrome-stable
google-chrome
chromium
chromium-browser
```

La suite de CI demostró que el runner dispone de un browser compatible; por ello no fue necesario modificar workflows ni introducir una descarga de navegador en cada ejecución.

## 11. Browser integration tests

Las pruebas de integración usan exclusivamente contenido sintético/local y demuestran:

- lanzamiento headless mediante Playwright;
- BrowserContext limpio;
- `page.set_content()`;
- `get_by_role`;
- `_pw_unique`;
- `_pw_activate`;
- `select_option` real para San Pedro Sula;
- botón para Plaza Pedregal;
- ausencia y ambigüedad;
- ruta custom `combobox`;
- cookies/localStorage/sessionStorage sintéticos;
- route interception;
- fulfillment local de `synthetic.invalid`;
- bloqueo de red externa;
- cierre explícito del browser.

Para escenarios que requieren origen navegable se usa un `ThreadingHTTPServer` únicamente en loopback `127.0.0.1` dentro del runner de CI.

## 12. Cero tráfico externo durante browser tests

`install_local_network_guard` intercepta requests desde el proceso Chromium.

Permitido:

```text
about:
data:
file:
127.0.0.1
localhost
::1
synthetic.invalid -> fulfilled localmente por route interception
```

Cualquier otro HTTP/HTTPS es abortado antes de red.

La prueba incluye deliberadamente una navegación/fetch dirigida a:

```text
https://www.lacolonia.com/forbidden
```

pero BrowserContext la intercepta y aborta con `blockedbyclient` **antes de que abandone el navegador**. Su propósito es demostrar la protección automática; no es tráfico que llegue a La Colonia.

Resultado de esta etapa:

```text
tráfico a La Colonia = 0
```

## 13. Failure artifacts probados

Con `run_live` apuntando exclusivamente a un servidor sintético de loopback y un authorization ID inyectado solo en tests se probaron artefactos de fallo para:

1. selector de tienda ausente;
2. San Pedro Sula ausente;
3. Plaza Pedregal ambigua;
4. productSearch no observado;
5. facets no observadas;
6. budget agotado.

Cada caso verifica:

```text
completed_at presente
stop_reason presente
errors presentes
logical_requests presente
output JSON persistido
secretos ausentes
```

También se prueba que un fallo antes de `target_navigation_started` no sea elegible para consumo y que un fallo después de comenzar la navegación sí lo sea.

## 14. Captura técnica y GraphQL

La captura conserva metadata estructural de XHR/fetch/GraphQL:

- URL sanitizada;
- method;
- resource type;
- operationName;
- clasificación;
- from/to;
- orderBy;
- selectedFacets;
- map;
- status;
- content-type.

Clasificaciones:

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

No se guardan payloads completos automáticamente.

## 15. Replay de contexto

`_safe_replay_headers` solo conserva headers públicos explícitamente permitidos:

```text
accept
accept-language
content-type
x-vtex-locale
```

No copia ni inventa:

- `Cookie` manual;
- `Authorization`;
- `binding`;
- `salesChannel`;
- `regionId`;
- otros headers no demostrados.

El `APIRequestContext` asociado al BrowserContext puede conservar cookies del mismo contexto, pero todavía no existe evidencia live suficiente para afirmar que eso preserve todos los mecanismos comerciales SPS de La Colonia.

Por tanto:

```text
context_replay_verification = pending_live
```

No se inventan headers VTEX.

## 16. Presupuesto

Defaults:

```text
max_logical_requests = 8
concurrency = 1
minimum_delay_seconds = 1.5
max_retries = 1
```

El contador se detiene al alcanzar el presupuesto.

## 17. Fixtures

Se mantienen los fixtures sintéticos existentes:

```text
tests/fixtures/la_colonia_sps_context_diagnostic.html
tests/fixtures/la_colonia_sps_context_diagnostic.json
```

No contienen cookies, sesiones, direcciones ni tokens reales.

## 18. Validación CI del hardening

CI final de esta etapa:

```text
workflow = Precios Supermercados SPS - Pruebas base
run = 31204158725
run_number = 144
job = 92951035840
head = 773e5584974f4d081c66daf2294ff10a1867a52d
Python = 3.12.13
Playwright = 1.62.0
compileall = success
pytest = 533 passed
failed = 0
errors = 0
duration = 47.53s
conclusion = success
```

El runtime usó un browser compatible ya presente en el runner; no se descargó Chromium y no se modificó el workflow.

Los logs mostraron una advertencia de teardown de Playwright (`TargetClosedError` después de completarse las pruebas) además de las advertencias de deprecación del runner. La prueba explícita de cierre de browser sí pasó. La advertencia queda registrada como observación de runtime y no como fallo de pytest.

## 19. Qué no fue ejecutado

```text
--live contra La Colonia = no
SPS seleccionado = no
root de La Colonia = no
facets de La Colonia = no
productos descargados = 0
full crawl = no
recorrido por categorías = no
workflow live = no
```

## 20. Limitaciones restantes

- el DOM real de La Colonia puede diferir de los fixtures;
- el mecanismo real de SPS aún no está observado;
- `context_replay_verification` permanece `pending_live`;
- no existe autorización live activa;
- no existe `SPS-context-and-root-facets-002` autorizada;
- la prueba real del target requiere una autorización nueva futura;
- los logs de CI conservan una advertencia de teardown de Playwright aunque las 533 pruebas, incluida la de cierre explícito, pasan.

## 21. Decisión pre-live

El camino `run_live` queda endurecido para autorización, persistencia, sanitización, progreso, browser runtime y bloqueo de red de tests.

Esto **no autoriza** una ejecución live.

Estado obligatorio:

```text
active authorization IDs = []
001 = consumida
002 = no creada / no autorizada
tráfico a La Colonia = 0
```
