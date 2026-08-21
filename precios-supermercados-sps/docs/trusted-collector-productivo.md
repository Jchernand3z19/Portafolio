# Diseño productivo — Trusted collector y frontera física

Estado: **DISEÑO APROBADO PARA IMPLEMENTACIÓN, NO DESPLEGADO**.

Este documento define la arquitectura productiva elegida para cerrar la provenance física del collector de La Colonia y GATE-06/GATE-18. No autoriza tráfico live, no crea infraestructura y no sustituye una prueba productiva posterior.

## 1. Problema que debe resolver

El evaluador canónico actual añade deliberadamente `trusted_collector_provenance_unavailable` porque las páginas y digests se construyen dentro del mismo proceso que llama al evaluador. Una marca, HMAC local, digest o booleano generado por ese mismo proceso no demuestra que haya ocurrido una solicitud HTTP física independiente.

La solución productiva debe demostrar, de forma fail-closed, que:

1. el request físico salió por una ruta de red controlada;
2. la política de egress permitió exactamente ese destino;
3. el request fue ejecutado por el runtime autorizado y no por el caller;
4. la respuesta usada por el crawler corresponde a ese request físico;
5. dos recorridos de reconciliación representan solicitudes físicas distintas;
6. la evidencia no puede ser fabricada por GitHub Actions, por el caller del evaluador ni por un PR no integrado;
7. la ausencia de logs, firma, correlación o cierre físico impide la aceptación.

## 2. Arquitectura elegida

```text
GitHub Actions / controller
        |
        | OIDC / Workload Identity Federation
        v
Cloud Run Job: collector autoritativo
        |
        | Direct VPC egress = all-traffic
        v
Subred dedicada de collector
        |
        | ruta next-hop / policy-based route
        v
Secure Web Proxy (default deny)
        |
        | allowlist mínima La Colonia/VTEX
        v
Internet

collector -> Cloud KMS collector-receipt-key -> recibo firmado
Secure Web Proxy -> Cloud Logging -> transacción independiente

recibos + logs
        v
Cloud Run: provenance verifier
        |
        | verifica firma + correlación física + unicidad
        v
Cloud KMS verifier-attestation-key
        |
        v
attestation final firmada
        |
        v
GATE-18 / catalog_accepted
```

### Componentes

**Controller (GitHub Actions)**

- sólo orquesta;
- autentica a Google Cloud mediante OIDC/Workload Identity Federation, sin claves estáticas;
- puede invocar el collector/verifier autorizados;
- no posee permiso de firma KMS;
- no posee capacidad directa para generar provenance aceptable;
- los jobs live permanecen bloqueados hasta una autorización humana live nueva.

**Collector autoritativo (Cloud Run Job)**

- ejecuta una imagen inmutable construida desde código integrado/protegido;
- usa una service account exclusiva;
- usa Direct VPC egress con `all-traffic` hacia una subred dedicada;
- no dispone de una salida directa a Internet fuera de la ruta controlada;
- la subred del collector se dirige al Secure Web Proxy en modo next-hop;
- calcula el SHA-256 de request canónico y bytes crudos de respuesta;
- emite un recibo firmado con una clave asimétrica de Cloud KMS;
- no puede leer/alterar los logs independientes usados por el verifier.

**Secure Web Proxy (SWP)**

- política default-deny;
- permite únicamente hosts/rutas/métodos explícitamente requeridos por la ejecución autorizada;
- registra cada transacción mediada en Cloud Logging;
- el despliegue productivo debe demostrar que el collector no puede alcanzar Internet si se elimina/deshabilita la ruta al proxy;
- no se crea Cloud NAT independiente para el collector que permita un bypass de SWP.

Se elige **next-hop routing** sobre un proxy meramente explícito para que la aplicación no pueda decidir voluntariamente omitir el proxy. La aceptación del despliegue debe probar que la ruta aplica realmente a los IPs de Direct VPC egress del collector.

**Cloud Logging**

Los transaction logs de SWP son evidencia independiente del proceso collector. El verifier debe correlacionar como mínimo host, path, método, tiempos, status, tamaño de respuesta, acción de policy, IP/origen y, cuando esté disponible en la entrada correspondiente, la service account cliente.

**Cloud KMS — collector receipt**

- clave con purpose `ASYMMETRIC_SIGN`;
- la private key no sale de KMS;
- sólo la service account del collector recibe `cloudkms.cryptoKeyVersions.useToSign` sobre esa clave;
- controller, verifier y GitHub no reciben ese permiso;
- el verifier usa la public key/version esperada para validar recibos.

**Provenance verifier**

- service account separada;
- puede leer exclusivamente los logs necesarios de SWP;
- no puede ejecutar requests hacia La Colonia;
- no puede firmar como collector;
- reconcilia cada recibo firmado contra una transacción física de SWP;
- verifica que una transacción no se reutilice para dos requests lógicos;
- exige traversals independientes para primary/reconciliation;
- produce una attestation final firmada con **otra** clave KMS (`verifier-attestation-key`);
- sólo esa attestation verificada puede retirar `trusted_collector_provenance_unavailable` en el evaluador productivo.

## 3. Recibo físico mínimo

El recibo firmado del collector debe usar serialización canónica versionada y contener al menos:

```text
schema_version
run_id
request_id
reservation_id
authorization_id
approved_commit_sha
immutable_image_digest
request_digest
traversal_id
traversal_role            # primary | reconciliation
order_by
partition_id
from_index
to_index
http_method
target_scheme
target_host
target_path
canonical_request_sha256
raw_response_sha256
response_status
response_body_bytes
physical_started_at_utc
response_completed_at_utc
collector_service_account
collector_revision_or_job_execution
kms_key_version
nonce
```

No se incluyen cookies, tokens, JWT, direcciones personales, orderForm IDs ni credenciales en recibos o logs de aplicación.

## 4. Attestation final del verifier

La attestation final debe ligar:

```text
schema_version
run_id
authorization_id
approved_commit_sha
immutable_image_digest
collector_receipt_digests[]
swp_log_insert_ids[]
primary_traversal_id
reconciliation_traversal_id
primary_order_by
reconciliation_order_by
verified_request_count
verification_started_at_utc
verification_completed_at_utc
verdict                       # VERIFIED | REJECTED
reasons[]
verifier_kms_key_version
```

`VERIFIED` sólo es válido cuando todos los recibos esperados tienen firma válida y una correlación uno-a-uno con logs físicos de SWP.

## 5. Reglas fail-closed

Cualquiera de los siguientes casos produce `REJECTED` y mantiene `trusted_collector_provenance_unavailable`:

- firma KMS ausente/inválida o key version no permitida;
- attestation final sin firma válida;
- log SWP ausente, duplicado o ambiguo;
- log con policy action distinta de ALLOW;
- host/path/method/status/size incompatibles con el recibo;
- timestamp fuera de la ventana cerrada de la reserva;
- service account/origen inesperado;
- request físico sin recibo o recibo sin request físico;
- un mismo log físico reclamado por más de un request;
- primary y reconciliation comparten request/log/nonce;
- imagen ejecutada distinta del digest autorizado;
- commit distinto del aprobado;
- authorization ID inexistente, consumido o no coincidente;
- pérdida de acceso a Cloud Logging durante la verificación;
- cualquier ruta alternativa de Internet para el collector;
- evidencia caller-controlled usada como sustituto de KMS/SWP.

## 6. Separación IAM mínima

| Identidad | Puede | No puede |
|---|---|---|
| GitHub controller | invocar jobs autorizados mediante WIF | firmar receipts/attestations, escribir logs SWP, egress directo autoritativo |
| Collector SA | ejecutar collector, usar collector KMS sign | leer logs de verificación, firmar attestation final, administrar red/KMS |
| Verifier SA | leer logs SWP necesarios, verificar receipts, usar verifier KMS sign | enviar requests a La Colonia, usar collector KMS sign, administrar red |
| Deploy/Admin | desplegar infraestructura mediante flujo controlado | actuar como runtime normal |

No se almacenan service-account keys JSON en GitHub. La integración GitHub→GCP debe usar OIDC/Workload Identity Federation.

## 7. Controles de red requeridos

1. Cloud Run collector con Direct VPC egress `all-traffic`.
2. Subred dedicada para el collector.
3. Secure Web Proxy en modo `NEXT_HOP_ROUTING_MODE` en la misma región.
4. Route/PBR que capture el egress del rango dedicado y lo entregue a SWP.
5. Política SWP default-deny.
6. Allowlist mínima y versionada para el destino autorizado.
7. Sin Cloud NAT/egress alternativo utilizable por el collector.
8. Prueba negativa obligatoria: destino no allowlisted debe fallar.
9. Prueba de bypass obligatoria: sin SWP/ruta válida el collector no debe tener Internet.
10. Transaction logging de SWP habilitado y accesible sólo al verifier/auditoría.

## 8. Pruebas productivas necesarias antes de cerrar GATE-06/GATE-18

No basta con desplegar recursos. Deben observarse explícitamente:

- un request permitido aparece en SWP logs y produce receipt firmado;
- un destino no permitido queda DENY y no produce evidencia aceptable;
- intento de request fuera de SWP no alcanza Internet;
- receipt modificado falla verificación;
- receipt duplicado/replay falla;
- log eliminado/no disponible hace fallar el verdict;
- receipt sin log falla;
- log sin receipt falla la completitud de la reserva;
- primary y reconciliation usan transacciones físicas distintas;
- controller no puede llamar `asymmetricSign` con ninguna de las dos claves;
- collector no puede firmar con la clave del verifier;
- verifier no puede firmar con la clave del collector;
- una imagen/commit no autorizado falla antes del egress;
- la autorización one-shot queda consumida y no puede repetirse.

Sólo después de estas pruebas puede cambiarse:

```text
GATE-06 -> PASS_PRODUCTIVE_EVIDENCE
GATE-18 -> elegible para exact final validation
```

## 9. Integración futura con el código actual

No se cambia ahora `RawProduct`, `NormalizedOffer` ni `ValidatedOffer`.

La integración productiva debe añadir una frontera nueva fuera de esos contratos:

```text
SignedPhysicalReceipt
VerifiedPhysicalRequest
SignedProvenanceAttestation
```

`evaluate_canonical_catalog_coverage()` continuará fail-closed por defecto. Sólo una variante productiva que reciba y verifique una `SignedProvenanceAttestation` auténtica podrá omitir `trusted_collector_provenance_unavailable`.

No se aceptará una API como `trusted=True`, `provenance_ok=True`, un issuer local, un HMAC con secreto del mismo proceso ni un archivo/marker del repositorio.

## 10. Secuencia de implementación

### Fase A — Preparación humana mínima

- proyecto Google Cloud con billing habilitado;
- región elegida;
- permisos para crear IAM, Cloud Run, VPC, Secure Web Proxy, Cloud Logging, Cloud KMS y Workload Identity Federation.

### Fase B — Infraestructura sin tráfico a La Colonia

- APIs/identidades/WIF;
- VPC/subred;
- SWP default-deny;
- KMS keys;
- collector/verifier desplegados con endpoint de prueba local/no-La-Colonia;
- pruebas negativas y de IAM.

### Fase C — Validación física controlada

Requiere **nueva autorización humana live explícita**. Sólo entonces se habilita una prueba mínima contra La Colonia con presupuesto cerrado.

### Fase D — GATE-18

Con provenance productiva demostrada se ejecuta la validación exacta de catálogo. Recién después puede conectarse persistencia comercial productiva.

## 11. Coste y operación

Secure Web Proxy tiene coste por instancia/hora y por GB procesado. Por eso no se despliega ni se deja activo por iniciativa del código: billing/proyecto son una frontera humana explícita. Cloud Run, Cloud Logging, KMS y networking también pueden generar cargos según uso/configuración.

## 12. Referencias oficiales verificadas

- Cloud Run Direct VPC egress: https://docs.cloud.google.com/run/docs/configuring/vpc-direct-vpc
- Secure Web Proxy overview: https://docs.cloud.google.com/secure-web-proxy/docs/overview
- Secure Web Proxy next hop: https://docs.cloud.google.com/secure-web-proxy/docs/deploy-next-hop
- Secure Web Proxy transaction logs: https://docs.cloud.google.com/secure-web-proxy/docs/view-proxy-transaction-logs
- Cloud KMS asymmetric signatures: https://docs.cloud.google.com/kms/docs/create-validate-signatures
- Cloud KMS asymmetricSign API: https://docs.cloud.google.com/kms/docs/reference/rest/v1/projects.locations.keyRings.cryptoKeys.cryptoKeyVersions/asymmetricSign

Referencias consultadas el 2026-08-20/21. La implementación futura debe volver a verificar documentación, disponibilidad regional, límites y precios antes de crear recursos.
