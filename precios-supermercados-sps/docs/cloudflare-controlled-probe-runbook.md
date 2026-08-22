# Runbook — sonda Cloudflare contra origen controlado

Estado operativo vigente: consultar [`PROJECT_STATE.md`](PROJECT_STATE.md).

## Resultado histórico ya obtenido

La primera prueba física dejó de estar pendiente. La evidencia principal es:

```text
source run físico = 32551882793
verifier-only     = 32552932554
```

El run físico demostró, contra infraestructura propia `workers.dev`:

```text
GitHub workflow
-> OIDC de sonda
-> Worker precios-sps-controlled-probe
-> Durable Object ProbeLedger
-> fetch al Worker precios-sps-controlled-origin
-> challenge/body esperado
-> receipt Ed25519 probe-1
-> verificación criptográfica independiente
```

El verifier-only revalidó firma, bytes e identidad del intento físico sin poder ejecutar el gateway de sonda.

La reconciliación estricta de Workers Observability **no se declara cerrada**: el diagnóstico posterior encontró un trace candidato real, pero la API pública consultada no expone el custom span/fetch hijo en la forma requerida por el reconciliador. PR #134 retiró los diagnósticos temporales sin debilitar esa condición.

Por tanto, este runbook ya no es una lista de pasos “pendientes para el primer deploy”. Es la política para un **eventual rerun controlado**, sólo si existe una razón técnica nueva.

## 1. Qué demuestra y qué no

Una sonda válida puede demostrar capacidades físicas de infraestructura propia:

- autenticación OIDC;
- ejecución Worker/Durable Object;
- presupuesto/replay/pacing;
- fetch al origen controlado;
- hash de respuesta;
- receipt Ed25519;
- verificación independiente;
- telemetría disponible hasta el nivel que realmente exponga la API.

Nunca demuestra por sí sola:

- autorización para contactar La Colonia;
- binding SPS;
- completitud del catálogo de La Colonia;
- `production_authority=true`;
- `catalog_accepted=true`.

## 2. No repetir por defecto

No ejecutar otra sonda física sólo para volver a obtener la misma evidencia de OIDC/fetch/firma.

Un rerun requiere una razón explícita, por ejemplo:

- cambio del Worker/DO/OIDC/llaves que invalida evidencia anterior;
- cambio documentado de la API de Observability que permita probar una hipótesis nueva;
- investigación de una regresión productiva concreta;
- una tarea humana explícita que requiera nueva evidencia física.

Si el objetivo es sólo releer evidencia ya firmada o consultar Observability, preferir un verifier/read-only cuando exista y no ejecutar de nuevo el fetch físico.

## 3. Separación obligatoria de La Colonia

La sonda usa infraestructura propia e independiente:

- Worker `precios-sps-controlled-origin`;
- Worker `precios-sps-controlled-probe`;
- Durable Object `ProbeLedger`;
- audience/environment OIDC de sonda;
- llaves Ed25519 de sonda;
- schema/dominio criptográfico `probe-1`.

El caller nunca elige libremente el origen.

El origen permitido permanece limitado a HTTPS `*.workers.dev` y al path canónico derivado internamente. Cualquier destino La Colonia debe ser rechazado antes del fetch.

Un rerun de sonda **no crea ni consume una autorización live de La Colonia**.

## 4. Toolchain

Usar únicamente la versión de Wrangler fijada en `edge/cloudflare/package.json` y validada por CI. No sustituirla por `wrangler@latest` ni una instalación global durante un ejercicio físico.

Si la versión fijada cambia, hacerlo en un PR separado con pruebas antes de cualquier rerun.

## 5. Recursos de Cloudflare

Antes de un rerun, verificar que existan/estén correctamente configurados en una única cuenta de sonda:

1. `precios-sps-controlled-origin`;
2. `precios-sps-controlled-probe`;
3. `ProbeLedger` según configuración versionada;
4. par Ed25519 exclusivo de sonda;
5. Workers Observability según configuración versionada;
6. token API limitado a la cuenta/permiso necesario para las consultas requeridas.

No asumir que los recursos históricos siguen desplegados sólo porque existió un run físico previo.

## 6. Material criptográfico

Nombres esperados en Cloudflare para el gateway de sonda:

```text
PROBE_ORIGIN_URL
PROBE_RECEIPT_PRIVATE_KEY_PKCS8_B64URL
PROBE_RECEIPT_PUBLIC_KEY_SPKI_B64URL
```

Reglas:

- la private key vive únicamente en Cloudflare;
- no se pega en chat, GitHub, logs, artifacts ni archivos versionados;
- la public key puede configurarse en GitHub para el verifier;
- no reutilizar llaves de una futura ruta productiva de La Colonia;
- cualquier archivo temporal de bootstrap debe existir fuera del repositorio y eliminarse tras su uso.

## 7. GitHub Environment

Environment esperado:

```text
cloudflare-probe
```

Secrets:

```text
CLOUDFLARE_PROBE_GATEWAY_URL
CLOUDFLARE_PROBE_OBSERVABILITY_TOKEN
```

Variables:

```text
CLOUDFLARE_PROBE_PUBLIC_KEY_SPKI_B64URL
CLOUDFLARE_ACCOUNT_ID
```

El token de Observability no debe conceder permisos de deploy de Workers. Verificar el permiso vigente contra la documentación de Cloudflare en el momento del rerun; no copiar ciegamente un nombre de permiso histórico.

## 8. Despliegue/redeploy

Sólo si la razón del rerun requiere desplegar o actualizar recursos:

```text
precios-supermercados-sps/edge/cloudflare/
```

Origen controlado:

```bash
npm run deploy:probe-origin
```

Gateway/DO:

- usar la configuración `wrangler.probe.json` versionada;
- cargar secrets según el mecanismo cerrado definido por la toolchain vigente;
- no añadir Custom Domain ni destino externo;
- no ampliar el origen más allá de `*.workers.dev`.

Si los recursos existentes ya corresponden exactamente al SHA/configuración que se desea probar, no hacer un redeploy innecesario.

## 9. Ejecución manual

El workflow de sonda es manual y no recibe un origin URL del caller.

Antes de ejecutarlo:

1. revisar `PROJECT_STATE.md`;
2. comprobar que no existe un cambio concurrente relevante en `main`;
3. documentar por qué la evidencia física anterior no basta para la tarea actual;
4. verificar Environment/vars/secrets sin imprimir valores;
5. confirmar que ninguna ruta de La Colonia será invocada;
6. conservar `catalog_accepted=false` y `production_authority=false`.

Durante la ejecución:

- no aumentar retries por conveniencia;
- no seguir redirects inesperados;
- no modificar el destino en caliente;
- detener ante un comportamiento fuera del contrato.

## 10. Verificación

La evidencia firmada debe validarse fuera del Worker emisor:

- firma Ed25519;
- request/evidence ID;
- commit/run/attempt;
- release/version metadata cuando corresponda;
- hash/tamaño/body esperado;
- identidad del origen permitido.

Cuando Observability se consulte, el verificador sólo debe afirmar aquello que la API realmente permita demostrar. Si faltan campos estructurales necesarios, el resultado permanece no reconciliado; no se sustituye la evidencia ausente por inferencias.

## 11. Salida y seguridad

Artifacts/logs deben permanecer sanitizados.

Nunca publicar:

- token OIDC;
- bearer/API tokens;
- private keys;
- cookies;
- payloads sensibles;
- URLs con secretos/query sensible;
- datos de La Colonia obtenidos fuera de una autorización explícita.

Un resultado de sonda siempre conserva:

```text
production_authority = false
catalog_accepted = false
```

## 12. Relación con el próximo paso del proyecto

La evidencia de sonda ya no es el bloqueo inmediato para el contexto SPS. El siguiente hito específico de La Colonia se documenta en `PROJECT_STATE.md` y requiere una autorización humana separada para la radiografía mínima de ubicación.

No usar este runbook como justificación para ejecutar esa radiografía ni cualquier crawl de La Colonia.
