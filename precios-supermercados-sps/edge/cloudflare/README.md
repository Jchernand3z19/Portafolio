# Cloudflare edge provenance — core offline

Estado: **NO DESPLEGADO / NO LIVE**.

Este directorio prepara el core portable del futuro gateway Cloudflare. No contiene credenciales, no crea recursos externos y no ejecuta solicitudes a La Colonia durante las pruebas.

## Qué valida hoy

- serialización JSON canónica estable entre runtimes;
- SHA-256;
- base64url canónico;
- firma/verificación Ed25519 mediante Web Crypto;
- JWT OIDC de GitHub firmado con RS256 y JWKS suministrado;
- issuer, audience, expiración, `nbf`, `iat`, `jti` y edad máxima;
- `repository`, `repository_id`, `ref`, `workflow_ref`, `environment`, `event_name`, `sha`, `run_id` y `run_attempt`;
- URL GET exacta de La Colonia con scheme/host/path/params cerrados;
- hash de la query GraphQL versionada;
- shape/allowlist de variables VTEX;
- `hideUnavailableItems=false`, `skusFilter=ALL`, page size <= 50;
- construcción del payload v2 de receipt.

## Qué NO hace todavía

- no consulta el JWKS real de GitHub;
- no despliega un Worker;
- no guarda claves privadas;
- no implementa Durable Objects;
- no hace `fetch()` a La Colonia;
- no concede `production_authority` ni `catalog_accepted`.

## Pruebas

No hay dependencias npm. La suite Node usa únicamente APIs estándar:

```bash
node --test edge/cloudflare/test/core.test.mjs
```

La suite `pytest` ejecuta también estas pruebas y pasa una URL generada por `la_colonia_graphql.py` al core JavaScript. De esta forma el required check `tests` detecta divergencias entre el extractor Python y el gateway edge.

Requisito para desarrollo local: Node.js 22 o superior.

## Secretos futuros

La clave privada de firma se almacenará únicamente como Cloudflare Worker Secret. Los archivos `.dev.vars*`, `.env*`, `.wrangler/` y `node_modules/` quedan fuera de Git.

No se debe introducir la clave privada en GitHub Secrets si el objetivo es mantener al collector como autoridad independiente del caller.
