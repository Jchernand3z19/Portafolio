# Runbook — despliegue productivo del edge Cloudflare

Estado operativo vigente: consultar [`PROJECT_STATE.md`](PROJECT_STATE.md).

Este runbook prepara el **despliegue de infraestructura** del Worker `precios-sps-provenance`. No autoriza ninguna solicitud a La Colonia, no concede `production_authority`, no acepta el catálogo y no habilita `extraction_enabled`.

El despliegue real modifica infraestructura externa de Cloudflare y requiere una cuenta/credenciales autorizadas. Por esa razón se ejecuta únicamente con intervención humana deliberada; no forma parte de CI y el repositorio no expone un script automático `deploy:production`.

## 1. Objetivo

Cerrar, sin contactar La Colonia, los prerrequisitos externos necesarios para que una futura ejecución live pueda fallar o avanzar sobre infraestructura real verificable:

```text
precios-sps-provenance
+ AuthorizationGateway (Durable Object)
+ secrets Ed25519/productivos
+ EDGE_COLLECTOR_CODE_SHA256
+ CF_VERSION_METADATA
+ tracing/observability
+ URL pública del gateway
+ GitHub Environment la-colonia-live
```

Una vez cerrados estos puntos todavía será obligatoria una autorización humana nueva y explícita para cualquier tráfico a La Colonia.

## 2. Configuración versionada que gobierna

Trabajar únicamente desde:

```text
precios-supermercados-sps/edge/cloudflare/
```

Archivos relevantes:

```text
wrangler.json
package.json
src/index.mjs
src/worker-policy.mjs
```

`wrangler.json` es la configuración productiva canónica. No sustituirla por `wrangler.probe.json` ni por `wrangler.probe-origin.json`.

El Worker productivo esperado es:

```text
name = precios-sps-provenance
Durable Object = AuthorizationGateway
binding = AUTHORIZATION_GATEWAY
storage = sqlite
version metadata binding = CF_VERSION_METADATA
preview_urls = false
```

## 3. Toolchain fijada

La CLI canónica está pinneada en `edge/cloudflare/package.json`:

```text
wrangler = npx --yes wrangler@4.125.0
```

Verificarla mediante el script versionado:

```bash
npm run wrangler -- --version
```

El resultado debe ser `4.125.0`.

No usar `wrangler@latest`, una instalación global ni un tag/versión distinta durante la operación productiva. Un cambio de versión de Wrangler requiere primero un PR separado y CI verde.

## 4. Preflight local sin red al supermercado

Antes de autenticar contra Cloudflare:

1. confirmar que `main` es el SHA aprobado para el despliegue;
2. confirmar que no existe un PR concurrente que cambie `edge/cloudflare/`, el workflow live o sus contratos;
3. ejecutar la suite completa del proyecto;
4. verificar que `wrangler.json` sigue declarando exactamente los bindings/secrets esperados;
5. confirmar que `ACTIVE_AUTHORIZATION_IDS=[]` y el workflow live permanece fail-closed;
6. no abrir navegador, no invocar scripts de La Colonia y no probar el gateway contra el supermercado.

La preparación de infraestructura y la autorización live son fronteras diferentes.

## 5. Material criptográfico

El Worker requiere:

```text
EDGE_RECEIPT_PRIVATE_KEY_PKCS8_B64URL
EDGE_RECEIPT_PUBLIC_KEY_SPKI_B64URL
EDGE_COLLECTOR_CODE_SHA256
```

Reglas obligatorias:

- generar/obtener un par Ed25519 productivo separado del de la sonda;
- la private key vive únicamente en Cloudflare después del bootstrap;
- no guardar la private key en GitHub Secrets, Actions variables, artifacts, logs, issues, PRs ni chat;
- la public key correspondiente sí puede copiarse después a la variable de GitHub Environment destinada al verifier;
- no reutilizar llaves históricas de la sonda;
- cualquier archivo temporal con secretos debe estar **fuera del repositorio** y eliminarse inmediatamente después del deploy;
- nunca imprimir el contenido del archivo de secretos para diagnosticar un fallo.

`EDGE_COLLECTOR_CODE_SHA256` debe representar la identidad de código que el proceso de despliegue/preflight vaya a reconciliar. No inventar un hash ni reutilizar uno histórico. Si no existe una derivación reproducible y verificable para el artefacto que se va a desplegar, el despliegue no se considera listo para satisfacer el preflight productivo aunque Wrangler pueda publicar el Worker.

## 6. Archivo temporal de secretos

Wrangler permite cargar secrets junto con el código mediante `--secrets-file`. El archivo temporal puede ser JSON o dotenv; debe ubicarse fuera del checkout y contener únicamente los valores productivos requeridos.

Ejemplo de **nombres**, no de valores:

```text
EDGE_RECEIPT_PRIVATE_KEY_PKCS8_B64URL
EDGE_RECEIPT_PUBLIC_KEY_SPKI_B64URL
EDGE_COLLECTOR_CODE_SHA256
```

No crear `.env.production`, `secrets.json` ni equivalentes dentro del repositorio para una operación real, incluso si el `.gitignore` pudiera excluirlos.

## 7. Autenticación Cloudflare

Usar una identidad humana/API con el mínimo alcance necesario para desplegar el Worker y su Durable Object en la cuenta correcta.

Antes de ejecutar cualquier mutación:

- verificar explícitamente la cuenta objetivo;
- confirmar que no se está usando una cuenta de sonda equivocada;
- confirmar que no se añadirá Custom Domain, route adicional ni otro destino;
- confirmar que el nombre final será `precios-sps-provenance`.

No almacenar el token de deploy en el repositorio ni reutilizarlo como token de Workers Observability de sólo lectura.

## 8. Despliegue productivo manual

Desde `precios-supermercados-sps/edge/cloudflare/`, y sólo después de cerrar los preflights anteriores:

```bash
npm run wrangler -- deploy --config wrangler.json --secrets-file /ruta/fuera-del-repo/product-secrets.json
```

La operación debe usar exactamente `wrangler.json` y el archivo temporal fuera del repositorio.

`wrangler deploy` crea una nueva versión y la despliega. `secrets.required` obliga a Wrangler a comprobar que los nombres requeridos estén configurados antes de completar el deploy.

Si Wrangler informa un binding, secret, Durable Object o configuración inesperada, detenerse; no modificar la política en caliente para conseguir un deploy verde.

Después de completar el comando, eliminar de inmediato el archivo temporal de secretos.

## 9. Read-back del despliegue sin La Colonia

No considerar cerrado el despliegue sólo porque el comando terminó con código 0.

Consultar el estado productivo con la misma toolchain fijada:

```bash
npm run wrangler -- deployments status --config wrangler.json --json
```

El read-back debe permitir identificar, sin exponer secretos:

- Worker `precios-sps-provenance`;
- deployment/version activa;
- versión coherente con `CF_VERSION_METADATA` cuando el Worker sea invocado posteriormente;
- configuración productiva esperada.

Además, obtener por una vía autenticada de Cloudflare el Script Settings real y verificar, sin inventar defaults:

```text
observability.enabled = true
observability.traces.enabled = true
observability.traces.head_sampling_rate = 1
```

La aplicación ya contiene parsers/preflight fail-closed para Script Settings. Una respuesta API incompleta o no autenticada no se convierte en evidencia válida por interpretación manual.

No ejecutar `/v1/execute`, `/v1/catalog-execute` ni `/v1/structural-execute` contra La Colonia como parte de este read-back.

## 10. Public key y URL del gateway

Una vez desplegado el Worker:

1. identificar la URL pública real del gateway sin incluir secretos/query sensible;
2. obtener la public key Ed25519 productiva correspondiente a la private key almacenada en Cloudflare;
3. verificar offline que el material público es parseable por el verifier del proyecto;
4. no recuperar ni exportar la private key desde Cloudflare.

La URL y la public key son configuración necesaria del caller; no son por sí mismas evidencia de autoridad productiva ni autorización live.

## 11. GitHub Environment `la-colonia-live`

Después del read-back productivo y sólo con valores verificados, configurar en el Environment:

```text
CLOUDFLARE_EDGE_GATEWAY_URL
CLOUDFLARE_EDGE_RECEIPT_PUBLIC_KEY_SPKI_B64URL
```

No añadir la private key productiva a GitHub.

La configuración del Environment debe quedar separada de cualquier marker/Authorization ID de La Colonia. Mantener:

```text
ACTIVE_AUTHORIZATION_IDS = []
```

hasta que exista una autorización humana nueva para una observación live concreta.

## 12. Evidencia mínima a conservar

Conservar únicamente evidencia sanitizada que permita reauditar la infraestructura:

- SHA de `main` desplegado;
- nombre del Worker;
- deployment/version ID;
- digest/fingerprint de la public key, nunca private key;
- identidad/digest reproducible del código desplegado;
- resultado de Script Settings;
- timestamp de observación;
- URL pública del gateway sin secretos;
- confirmación de que el workflow live siguió fail-closed durante toda la preparación.

No conservar tokens, archivos de secrets, valores privados, cookies ni payloads de La Colonia.

## 13. Condiciones de salida

La infraestructura puede declararse **técnicamente preparada para pedir una nueva autorización live** sólo cuando todos estos puntos sean verificables:

```text
Worker/DO desplegados
required secrets presentes en Cloudflare
private key sólo en Cloudflare
public key correspondiente validada
collector code identity reconciliable
release/version identificada
tracing/observability configurados y leídos de vuelta
CLOUDFLARE_EDGE_GATEWAY_URL configurada en la-colonia-live
CLOUDFLARE_EDGE_RECEIPT_PUBLIC_KEY_SPKI_B64URL configurada en la-colonia-live
workflow live sigue fail-closed
```

Incluso entonces permanecen:

```text
production_authority = false
catalog_accepted = false
extraction_enabled = false
ACTIVE_AUTHORIZATION_IDS = []
```

hasta cruzar sus fronteras correspondientes.

## 14. Siguiente frontera

Sólo después de cerrar y verificar esta infraestructura se puede pedir una autorización humana **nueva** para la observación mínima live que figure en `PROJECT_STATE.md`.

El deploy productivo no reutiliza ni revive autorizaciones anteriores y nunca se interpreta como permiso implícito para contactar La Colonia.
