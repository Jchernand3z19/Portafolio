# PriceSmart Honduras — GraphQL detenido por path no autorizado

## Resultado

El probe se detuvo correctamente después del primer POST. La operación read-only
`channels` se envió al único endpoint autorizado,
`https://graphql-commerce.bloomreach.io/`, y recibió **HTTP 404 `Cannot POST /`**.
La petición no alcanzó GraphQL; no hay datos, binding, precios ni paginación que
aceptar. Probar `/graphql`, `/signin` u otro path habría ampliado el endpoint y se
evitó expresamente.

No fue 403, 429, CAPTCHA ni una respuesta que deba evadirse. No hubo retry,
redirect, mutación, login, token, membresía, carrito, full, persistencia ni Turso.

## Autorización y ledger

Autorización registrada `2026-08-31T22:47:02Z`. Ventana live iniciada
`22:49:02.292225Z`, con deadline `22:59:02Z`. Se cerró a
`22:49:02.588625Z`, tras 0.2964 s.

| Métrica | Resultado |
| --- | ---: |
| POST usados | 1/8 |
| Retries | 0/2 |
| Concurrencia | 1 |
| Operación | `channels` |
| Status | 404 |
| Respuesta | `Cannot POST /` |

El payload contiene el documento `channels` capturado del asset oficial y sólo
variables para las claves `6602`, `6603`, `6604`, límite 3 y locale Honduras. Los
headers públicos fueron `connector: commercetools`, `br-acct-env: pricesmart`,
`Origin: https://www.pricesmart.com` y JSON. No se envió `Authorization`.

La [guía oficial de GraphQL Commerce](https://documentation.bloomreach.com/content/reference/graphql-commerce-api-guides)
publica la base de producción, exige `br-acct-env` y documenta el connector
`commercetools`. La [referencia oficial](https://documentation.bloomreach.com/content/reference/graphql-commerce-api)
también muestra `connector` y `br-acct-env` para el playground. La respuesta live
demuestra que actualmente el path raíz no acepta POST, aunque la configuración
PriceSmart y la documentación publiquen esa base.

## Estado de los objetivos

| Objetivo | Resultado |
| --- | --- |
| Binding reproducible de club | No evaluable |
| Identidades SKU compartidas | 0 |
| `current_price` | No evaluable |
| `reported_regular_price` | No evaluable |
| `is_promotion` | No evaluable |
| Availability separada | No evaluable |
| Florencia vs El Sauce | No evaluable |
| SPS independiente | No evaluable |
| Granularidad TGU | Sin decisión |
| Paginación/full | No estimable con respuesta GraphQL |

Los contratos y clubes demostrados por el tramo GET anterior siguen vigentes como
evidencia de cliente, pero no sustituyen una respuesta comercial. Availability no
influyó en ninguna decisión.

No se crea parser o fixture vacío: sin una respuesta GraphQL exitosa no existe
estructura fuente que validar. El request preserva el documento `channels` real y
servirá como fixture de entrada cuando el endpoint correcto entregue datos.

## Continuación resuelta

La extensión posterior autorizó exactamente `/graphql`. El primer `channels`
llegó a un servidor GraphQL, pero recibió HTTP 400 porque el esquema no contiene
`channels`, `Locale` ni `Point` y sugiere `findChannels`. El alcance volvió a
cerrarse sin retry ni adaptación. Ver el
[reporte, RAW y decisión final de este gate](../2026-08-31-graphql-path-probe/README.md).

## Evidencia

- [raw-capture.tar.gz](raw-capture.tar.gz): request, response, ledger y manifest;
  SHA-256 `018f3921d6e542d5329d456f380f44113101d45b92d1e5809903ddae63349798`.
- [evidence.json](evidence.json): resultado reproducible.
- [verify.py](verify.py): hashes, endpoint, operación, variables, ausencia de
  mutation y respuesta 404, todo sin red.

No hubo valores sensibles en la captura y no se necesitó redacción.
