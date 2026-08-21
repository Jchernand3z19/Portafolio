# Cliente Python del gateway edge

Estado: **OFFLINE / SIN TRANSPORTE PRODUCTIVO / SIN AUTORIDAD PRODUCTIVA**.

`precios_supermercados.edge_gateway_client` adapta el contrato del Worker Cloudflare al runtime Python sin abrir red por sí mismo. Todo transporte debe inyectarse explícitamente mediante `EdgeGatewayTransport.post_json`.

## Garantías actuales

- sólo conoce las rutas lógicas `/v1/initialize` y `/v1/execute`;
- no contiene hostname, URL desplegada, token ni secreto;
- exige `run_id = GITHUB_RUN_ID:GITHUB_RUN_ATTEMPT`;
- valida shapes exactos de respuestas y receipts v2;
- decodifica base64url en forma canónica;
- recalcula SHA-256 del body físico;
- reconcilia tamaño/status del body con el receipt;
- reconcilia autorización, run, commit, request, reservation, digest, nonce, traversal y partition contra el request esperado;
- exige `collector_provider=cloudflare_workers` para esta ruta;
- reconcilia el run del receipt con `github_run_id:github_run_attempt`;
- recalcula el `evidenceId` emitido por el Worker;
- construye `SignedEdgeReceipt` y mantiene separado su digest canónico del `evidenceId` del transporte;
- `WAIT`, `DENY` y errores nunca se convierten en evidencia;
- toda evidencia devuelta mantiene `cryptographic_signature_verified=False` y `production_authority=False`.

## Deliberadamente pendiente

La firma Ed25519 tiene formato validado, pero este cliente **no decide qué clave pública es confiable**. Esa decisión debe vivir fuera del caller y fuera del Worker que produjo la evidencia. Hasta que exista un verifier productivo independiente, una respuesta estructuralmente consistente no puede conceder `production_authority`, `catalog_accepted` ni mutación comercial.

No habilitar tráfico live a La Colonia desde este módulo. La autorización humana live sigue siendo un requisito separado.
