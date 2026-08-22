# Runbook — sonda Cloudflare contra origen controlado

Estado: **READY_FOR_EXTERNAL_DEPLOYMENT / NO DESPLEGADA / NO EJECUTADA / NO LA-COLONIA**.

Este runbook describe el primer ejercicio físico permitido de la infraestructura Cloudflare del proyecto. La sonda usa exclusivamente un origen controlado `workers.dev`; **no autoriza ni realiza tráfico hacia La Colonia** y nunca concede `catalog_accepted` ni `production_authority`.

La fuente canónica del estado general es `docs/arquitectura.md`.

## 1. Objetivo de la prueba

Demostrar en infraestructura Cloudflare real, antes de tocar La Colonia, que funciona la cadena:

```text
GitHub workflow manual
-> GitHub OIDC de sonda
-> Worker precios-sps-controlled-probe
-> Durable Object ProbeLedger
-> fetch exacto
-> Worker precios-sps-controlled-origin
-> bytes/challenge exactos
-> receipt Ed25519 probe-1
-> verificación criptográfica fuera del Worker
-> Workers Observability
-> custom span + único child fetch
-> reconciliación de plataforma
```

Un PASS demuestra únicamente las invariantes físicas de la sonda. No significa que el collector de La Colonia esté productivamente autorizado.

## 2. Precondiciones versionadas

Antes de desplegar:

- `main` contiene PR #84, #88, #89, #90 y #91;
- la suite observada en PR #91 es **1234/1234 pruebas aprobadas** + `compileall`;
- `edge/cloudflare/wrangler.probe-origin.json` define el origen controlado;
- `edge/cloudflare/wrangler.probe.json` define el gateway/DO de sonda;
- ambos Workers tienen tracing con `head_sampling_rate = 1`;
- el gateway de sonda usa un `ProbeLedger` separado del `AuthorizationGateway` productivo;
- el gateway productivo de La Colonia y su allowlist no se modifican para esta prueba;
- `ACTIVE_AUTHORIZATION_IDS` de La Colonia puede y debe seguir vacío.

No es requisito crear una autorización live de La Colonia para ejecutar esta sonda. El barrido posterior a PR #91 no dejó una tarea de implementación offline conocida que pueda sustituir esta prueba física externa.

## 3. Toolchain fijado

El CLI de despliegue se invoca **únicamente** mediante el script versionado de `edge/cloudflare/package.json`:

```text
wrangler = npx --yes wrangler@4.125.0
```

Verificación local:

```bash
npm run wrangler -- --version
```

El resultado esperado es `4.125.0`. No usar `npx wrangler`, `npx wrangler@latest` ni una instalación global no versionada para esta prueba.

Si se decide cambiar la versión, hacerlo primero en un PR separado, revalidar configuración/CI y actualizar el test de toolchain. No actualizar Wrangler durante el mismo ejercicio físico.

## 4. Recursos externos necesarios

En una sola cuenta Cloudflare:

1. Worker `precios-sps-controlled-origin`;
2. Worker `precios-sps-controlled-probe`;
3. Durable Object SQLite `ProbeLedger`, creado por la configuración del gateway;
4. par Ed25519 **exclusivo de sonda**;
5. Workers Observability habilitado por la configuración versionada;
6. API Token limitado a la cuenta requerida y con el permiso que Cloudflare exige para consultar Workers Observability.

En GitHub:

1. Environment `cloudflare-probe`;
2. dos secrets de Environment;
3. dos variables de Environment.

No se reutilizan claves, audience, environment ni secrets de `la-colonia-live`.

## 5. Material criptográfico

El par Ed25519 de sonda debe ser nuevo e independiente del collector productivo.

```text
PROBE_RECEIPT_PRIVATE_KEY_PKCS8_B64URL = PKCS#8 DER, base64url sin padding
PROBE_RECEIPT_PUBLIC_KEY_SPKI_B64URL  = SubjectPublicKeyInfo DER, base64url sin padding
```

Reglas obligatorias:

- la **private key sólo existe en Cloudflare** después de la carga;
- no se guarda en GitHub Secrets, variables, artifacts, logs, archivos versionados ni chat;
- la public key sí se copia a GitHub como variable del Environment para el verifier independiente;
- el key ID de sonda permanece `cloudflare-probe-ed25519-v1`;
- no reutilizar una clave productiva futura.

Si una herramienta local genera la clave, cualquier archivo temporal debe vivir fuera del repositorio, usar permisos restrictivos y eliminarse inmediatamente después de cargarlo. `edge/cloudflare/.gitignore` bloquea además `.dev.vars`, `.wrangler/` y patrones de secrets locales como defensa adicional.

## 6. Orden de despliegue

Trabajar desde:

```text
precios-supermercados-sps/edge/cloudflare/
```

### 6.1 Origen controlado

El origen no necesita secrets.

```bash
npm run deploy:probe-origin
```

Este script usa el Wrangler fijado. Registrar la URL final exacta:

```text
https://precios-sps-controlled-origin.<subdominio>.workers.dev
```

No usar Custom Domain ni otro host en esta fase. Antes de continuar, comprobar que el hostname termina exactamente en `.workers.dev`.

### 6.2 Gateway de sonda

`wrangler.probe.json` declara:

```text
PROBE_ORIGIN_URL
PROBE_RECEIPT_PRIVATE_KEY_PKCS8_B64URL
PROBE_RECEIPT_PUBLIC_KEY_SPKI_B64URL
```

Valores:

- `PROBE_ORIGIN_URL`: URL del Worker controlado anterior;
- private key: PKCS#8 de sonda;
- public key: SPKI correspondiente al mismo par.

`secrets.required` hace que el deploy falle si falta alguno. Para el **primer deploy**, cargar los tres de forma atómica junto con el código:

```bash
npm run wrangler -- deploy --config wrangler.probe.json --secrets-file /ruta/fuera-del-repo/probe-secrets.json
```

El archivo temporal debe estar fuera del repositorio, tener permisos restrictivos y eliminarse inmediatamente después.

No inicializar el Worker mediante una secuencia de `wrangler secret put`: la documentación actual indica que cada `secret put` crea una nueva versión y la despliega inmediatamente, introduciendo estados parciales innecesarios durante el bootstrap.

Registrar la URL final exacta `https://...workers.dev` del gateway.

## 7. Configuración de GitHub Environment

Environment:

```text
cloudflare-probe
```

### Secrets

```text
CLOUDFLARE_PROBE_GATEWAY_URL
CLOUDFLARE_PROBE_OBSERVABILITY_TOKEN
```

`CLOUDFLARE_PROBE_GATEWAY_URL` contiene sólo el origen HTTPS del gateway, sin path, query, fragment, puerto ni credenciales.

`CLOUDFLARE_PROBE_OBSERVABILITY_TOKEN` debe limitarse a la única cuenta requerida y no debe tener permisos para modificar Workers. La API oficial de Workers Observability exige actualmente el permiso denominado `Workers Observability Write` para el endpoint de consulta; el nombre del permiso no debe reinterpretarse como permiso para desplegar scripts.

### Variables

```text
CLOUDFLARE_PROBE_PUBLIC_KEY_SPKI_B64URL
CLOUDFLARE_ACCOUNT_ID
```

`CLOUDFLARE_ACCOUNT_ID` debe ser el ID hexadecimal de 32 caracteres de la cuenta. La public key debe corresponder exactamente al par cargado en Cloudflare.

## 8. Separación de permisos del workflow

Workflow:

```text
.github/workflows/precios-supermercados-sps-cloudflare-probe.yml
```

Es únicamente `workflow_dispatch`.

### `controlled-probe`

- Environment `cloudflare-probe`;
- `id-token: write`;
- **sin checkout de repositorio**;
- obtiene GitHub OIDC;
- valida la URL fija del gateway;
- ejecuta exactamente una sonda;
- publica sólo evidencia sanitizada.

### `verify-evidence`

- depende de `controlled-probe`;
- checkout inmutable de `github.sha`;
- **sin `id-token: write`**;
- verifica Ed25519 con la public key del Environment;
- consulta Workers Observability con el token separado;
- exige custom span único y child `fetch` único;
- reconcilia URL, método, HTTP status, tamaño, version metadata, run/attempt y timestamps.

`test_workflow_security_audit.py` falla si esta separación cambia sin actualización explícita de política.

## 9. Ejecución física permitida

Sólo después de configurar todos los recursos anteriores, ejecutar manualmente:

```text
Precios SPS - Sonda Cloudflare controlada
```

sobre `main`.

No seleccionar una rama de PR. La política OIDC exige:

```text
repository = Jchernand3z19/Portafolio
repository_id = 1282475205
ref = refs/heads/main
workflow_ref = Jchernand3z19/Portafolio/.github/workflows/precios-supermercados-sps-cloudflare-probe.yml@refs/heads/main
environment = cloudflare-probe
event_name = workflow_dispatch
aud = urn:precios-sps:cloudflare:probe:v1
```

El `probeId` se deriva exactamente como `github-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}`; no existe input humano para URL, challenge, origin o authority.

## 10. Criterio PASS

La ejecución sólo es PASS si **todos** estos puntos se observan:

```text
controlled-probe = success
verify-evidence = success
receipt schema = probe-1
Ed25519 verification = PASS
raw body SHA-256 = PASS
canonical request reconstruction = PASS
evidenceId reconstruction = PASS
OIDC repo/ref/workflow/environment/run/attempt = PASS
Durable Object fencing = PASS
Workers Observability discovery = exactly 1 trace
custom span = exactly 1
origin child fetch = exactly 1
fetch URL = controlled workers.dev origin
fetch method = GET
fetch status = 200
fetch body size = signed receipt body size
Cloudflare script version = signed collector_release_id
fetch time = compatible with signed physical window
production_authority = false
catalog_accepted = false
La Colonia requests = 0
```

Un solo mismatch convierte la sonda en FAIL; no se degrada a evidencia parcial aceptable.

## 11. Criterios de parada y no-retry

La ruta física de sonda no tiene retry oculto. Detener y revisar ante:

- OIDC rechazado;
- tracing no muestreado;
- Durable Object inválido;
- redirect;
- origen distinto de `*.workers.dev`;
- firma o body inválidos;
- receipt replayed en la primera operación del run;
- trace ausente o duplicado;
- más de un child fetch candidato;
- versión de Worker distinta;
- token de Observability insuficiente;
- error de límites de Cloudflare.

Un error de Observability **no autoriza repetir automáticamente el fetch físico**. Una nueva ejecución usa un nuevo run ID y se analiza como una nueva sonda.

## 12. Evidencia que se conserva

Conservar de forma sanitizada:

- GitHub Actions run ID/attempt;
- commit SHA;
- nombres de Workers;
- Cloudflare script version ID;
- receipt público firmado;
- evidence ID;
- trace ID;
- custom span ID;
- fetch span ID;
- physical evidence ID;
- status PASS/FAIL y motivo.

No conservar private key, OIDC token, Observability API token ni `Authorization` headers.

El artifact `precios-sps-cloudflare-controlled-probe` puede conservar el resultado sanitizado del gateway durante su retención configurada; no convierte la evidencia en autoridad de catálogo.

## 13. Qué desbloquea un PASS

Un PASS productivo de esta sonda permite afirmar únicamente:

```text
CLOUDFLARE_CONTROLLED_PROBE = PASS_PRODUCTIVE_EVIDENCE
```

Todavía permanece:

```text
GATE-06 = OPEN_PRODUCTIVE
GATE-18 = OPEN_PRODUCTIVE
SPS = UNCONFIRMED
ACTIVE_AUTHORIZATION_IDS = []
catalog_accepted = false
production_authority = false
```

Después del PASS puede prepararse y validar el despliegue del Worker productivo **sin invocarlo contra La Colonia**. Cualquier request real a La Colonia sigue necesitando una autorización humana nueva y explícita.

## 14. Fuentes de plataforma verificadas

Al preparar este runbook se verificó en documentación oficial de Cloudflare que:

- Wrangler admite `exports` declarativos para Durable Objects y `storage: "sqlite"`;
- `secrets.required` se valida durante `wrangler deploy`/`versions upload`;
- `wrangler deploy --secrets-file` permite cargar secrets junto con el código;
- `wrangler secret put` crea una nueva versión y la despliega inmediatamente;
- el endpoint de Workers Observability es `POST /accounts/{account_id}/workers/observability/telemetry/query`;
- el endpoint acepta API Tokens y enumera `Workers Observability Write` entre los permisos aceptados;
- la versión de Wrangler fijada para esta fase es `4.125.0`.

Los límites, precios y permisos pueden cambiar. Revalidarlos inmediatamente antes del primer despliegue real sin cambiar la versión fijada dentro de la misma ejecución.
