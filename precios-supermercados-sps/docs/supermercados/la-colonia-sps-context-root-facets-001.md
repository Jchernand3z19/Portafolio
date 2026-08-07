# La Colonia — SPS-context-and-root-facets-001

## Resultado

Fecha: 2026-08-07, America/Tegucigalpa.

Clasificación: **D — bloqueada por limitación de herramienta**.

La prueba se detuvo antes de seleccionar San Pedro Sula y antes de ejecutar cualquier consulta GraphQL de raíz o facets. La herramienta de navegación disponible permite abrir páginas y seguir enlaces, pero no permite interactuar con el botón `Selecciona tu tienda`, manipular el `<select>` dinámico del localizador ni inspeccionar cookies, localStorage, sessionStorage, requests XHR/fetch o headers generados por esa interacción.

No se construyó un contexto SPS por suposición y no se reutilizó el total 9,291 como total SPS.

## Prerrequisitos verificados

Antes de navegar se confirmó:

- PR #7 abierto, draft y no fusionado;
- head inicial `88d93b1c668c5a1f7416d9d05308b430d755285f`;
- CI previa verde: run `31196811785`, run number `129`, job `92926916828`;
- PR #17 abierto/draft/no fusionado en `c2bea10d26405004dc4447af8404f862138eddbd`;
- archivo operacional intacto;
- blob operacional `7b40b1dc9e12e4ded347c753b863b3fd3f8b8186`.

## Ventana de ejecución

```text
started_at = 2026-08-07T10:26:26-06:00
completed_at = 2026-08-07T10:28:00-06:00
```

## Solicitudes lógicas

Se mantuvo concurrencia lógica 1. No hubo reintentos.

Se consideran dentro del presupuesto tres interacciones públicas relevantes de contexto/catálogo:

1. apertura inicial de `https://www.lacolonia.com/`;
2. apertura controlada de una PLP pública mínima (`/freshco`) utilizada únicamente para comprobar cómo la herramienta representa el selector de tienda y el catálogo;
3. apertura del localizador `https://www.lacolonia.com/localizador-de-tiendas`.

La FAQ pública se consultó como documentación y no como solicitud lógica de catálogo. Las búsquedas realizadas mediante índice web externo no se contabilizan como solicitudes al catálogo de La Colonia.

```text
solicitudes_logicas_intentadas = 3
solicitudes_logicas_completadas = 3
reintentos = 0
maximo_autorizado = 8
```

La herramienta no expone códigos HTTP de estas aperturas. No se observó 429, captcha, autenticación obligatoria ni 403 persistente en el contenido retornado.

## Estado inicial observado

La interfaz pública muestra:

```text
ciudad = no seleccionada
boton = Selecciona tu tienda
tienda = no seleccionada
modalidad = no seleccionada
```

El localizador muestra:

```text
Sucursales
Elige ciudad o departamento
<select> dinámico
Loading...
```

La herramienta no expuso las opciones dinámicas del `<select>` ni una acción para seleccionar San Pedro Sula.

## Evidencia pública de San Pedro Sula

La FAQ pública confirma que San Pedro Sula es una ciudad atendida y que la recogida en tienda para SPS corresponde a Plaza Pedregal. Esta evidencia confirma disponibilidad funcional de SPS, pero **no confirma un contexto técnico activo en esta sesión**.

Una página corporativa pública también lista Plaza Pedregal como `T21` en San Pedro Sula. Ese identificador se conserva únicamente como referencia pública de sucursal; no se asume que `T21` sea el store ID, seller, region, binding o sales channel del ecommerce.

## Contexto técnico

No fue posible observar de forma reproducible cambios en:

- cookies;
- localStorage;
- sessionStorage;
- URL;
- headers públicos;
- variables GraphQL;
- binding;
- sales channel;
- region;
- seller;
- pickup context;
- orderForm;
- session/segment.

Por tanto:

```text
SPS seleccionado = no
estado_contexto_SPS = inconclusive / no establecido
store_id = Pendiente
pickup_point_activo = Pendiente
binding = Pendiente
sales_channel = Pendiente
region = Pendiente
session_segment = Pendiente
```

No se publicaron cookies, tokens, identificadores de sesión, direcciones ni datos personales.

## Raíz y facets

No se ejecutaron porque SPS no pudo fijarse técnicamente antes de alcanzar esos pasos.

```text
endpoint_raiz = Pendiente
operation_name_raiz = Pendiente
from = Pendiente
to = Pendiente
page_size = Pendiente
order_by = Pendiente
selected_facets = Pendiente
total_SPS_primera = Pendiente
total_SPS_segunda = Pendiente
sampling = Pendiente
endpoint_facets = Pendiente
operation_name_facets = Pendiente
category-1 = Pendiente
category-2 = Pendiente
category-3 = Pendiente
hojas_candidatas = Pendiente
nodos_vacios = Pendiente
arbol_completo = Pendiente
```

El total previo de 9,291 productos corresponde al contexto sin tienda seleccionada y **no se usa como total SPS**.

## Estabilidad y dependencia por ubicación

No se realizaron las repeticiones de raíz/facets porque no existía un contexto SPS técnicamente establecido.

```text
estabilidad_raiz = inconclusive
estabilidad_facets = inconclusive
catalog_location_dependency = inconclusive
price_location_dependency = inconclusive
availability_location_dependency = inconclusive
```

La documentación pública sigue confirmando que la disponibilidad puede variar por ciudad, pero esta prueba no produjo una comparación técnica antes/después.

## Presupuesto preliminar

No se calcula `root_pages` porque `total_SPS` permanece Pendiente.

No se calcula `leaf_count`, suma de quantities, maximum leaf quantity ni estimated leaf pages porque no se obtuvo metadata de facets bajo SPS.

## Stop reason

```text
stop_reason = tool_cannot_interact_with_store_selector_or_inspect_session_context
```

Continuar con una consulta de raíz sin contexto SPS habría podido atribuir incorrectamente a San Pedro Sula datos del contexto por defecto, por lo que la prueba se detuvo de acuerdo con el criterio D.

## Alcance conservado

No se ejecutó:

- full crawl;
- recorrido por categorías;
- `facet-discovery-001`;
- `facet-discovery-002`;
- baseline500-003;
- validation500;
- segundo diagnóstico;
- descarga masiva;
- persistencia;
- Google Sheets;
- BigQuery;
- Power BI.

No se modificó código de producción, scraper, GraphQL helper, runner, runtime, contratos, workflows ni archivo operacional.

No se crearon fixtures porque no se capturó una raíz ni facets válidas bajo SPS.

## Decisión

La prueba autorizada se considera consumida y finalizada como **D — bloqueada por limitación de herramienta**.

No se autoriza automáticamente ninguna prueba siguiente.

Antes de repetir o diseñar una prueba posterior se necesita una herramienta que pueda, en una sesión pública controlada:

1. interactuar con `Selecciona tu tienda` o el selector equivalente;
2. observar de forma sanitizada el cambio de sesión/contexto VTEX;
3. ejecutar después la raíz y facets bajo ese mismo contexto;
4. mantener los mismos límites de concurrencia y presupuesto.
