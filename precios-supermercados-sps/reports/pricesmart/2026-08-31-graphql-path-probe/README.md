# PriceSmart Honduras — `/graphql` no expone el contrato autorizado

## Resultado

El probe se cerró correctamente después del primer POST. La ruta exacta
`https://graphql-commerce.bloomreach.io/graphql` aceptó y validó una petición
GraphQL, pero rechazó el documento `channels` observado en los assets de
PriceSmart:

- `Cannot query field "channels" on type "Query". Did you mean "findChannels"?`;
- `Unknown type "Locale"`;
- `Unknown type "Point"`.

La respuesta fue HTTP 400 con código `GRAPHQL_VALIDATION_FAILED`. No contenía
datos ni pidió autenticación. `findChannels` y una consulta adaptada a otro esquema
quedan fuera de las operaciones autorizadas, por lo que no se enviaron más POST.
Un retry del mismo documento no podía cambiar un error determinista de validación.

No hubo 403, 429, CAPTCHA, redirect, mutación, login, cookie, token, membresía,
carrito, full, persistencia ni Turso.

## Autorización y ledger

La extensión fue autorizada el `2026-08-31T23:14:29Z`. La ventana live comenzó
`23:16:21.978621Z`, con deadline `23:26:21.978621Z`, y se cerró a
`23:16:22.301805Z`, tras 0.323184 s.

| Métrica | Resultado |
| --- | ---: |
| POST usados en esta extensión | 1/7 |
| POST no consumidos | 6 |
| Presupuesto original previo | 1/8 usado en `/` |
| Retries | 0/2 |
| Concurrencia | 1 |
| Operación solicitada | `channels` |
| Status | 400 |
| Código | `GRAPHQL_VALIDATION_FAILED` |

El payload preserva el documento `channels` extraído del asset oficial y sólo las
variables de claves `6602`, `6603`, `6604`, límite 3 y locale Honduras. Se enviaron
los headers públicos `connector: commercetools`, `br-acct-env: pricesmart`,
`Origin: https://www.pricesmart.com` y JSON. No se envió `Authorization`.

## Estado de los objetivos

| Objetivo | Resultado |
| --- | --- |
| Binding reproducible de club | No demostrado |
| Identidades SKU compartidas | 0 |
| `current_price` | No evaluable |
| `reported_regular_price` | No evaluable |
| `is_promotion` | No evaluable |
| Availability separada | No evaluable |
| Florencia vs El Sauce | No evaluable |
| SPS independiente | No evaluable |
| Granularidad TGU | Sin decisión |
| Paginación/full | No estimable |

Los tres clubes y el contrato comercial continúan demostrados como configuración
del cliente Nuxt, pero esta ruta no confirmó que ese contrato sea ejecutable de
forma pública. El HTTP 400 tampoco significa catálogo vacío: hubo error de esquema
antes de resolver datos. Availability no influyó en la decisión.

No se crea parser, fixture de producto, scraper ni presupuesto de full. Sin una
respuesta comercial exitosa, hacerlo inventaría una fuente que no se observó.

## Continuación resuelta

La extensión posterior autorizó introspección limitada y `findChannels`. Apollo
Server bloqueó la introspección y el resolver consultó el upstream placeholder
`api.sphere.io/changeme/channels`, que devolvió 404. Se cerró sin producto,
credenciales ni otro mecanismo. Ver el
[reporte, RAW y decisión final de binding](../2026-08-31-graphql-schema-probe/README.md).

## Evidencia

- [raw-capture.tar.gz](raw-capture.tar.gz): request, response, ledger y manifest;
  SHA-256 `83dde6d9a1a65fc0d9aeb7ab1887a0642c527d67faf769794e3215bcf42c88ba`.
- [evidence.json](evidence.json): resultado normalizado y reproducible.
- [verify.py](verify.py): valida offline hashes, presupuesto, endpoint, operación,
  variables, ausencia de mutation y los tres errores de esquema.

No hubo valores sensibles en la captura y no se necesitó redacción.
