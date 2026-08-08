# Arquitectura canónica actual — Precios Supermercados SPS

Estado verificado para la fase offline. Este documento es la fuente canónica del
estado actual; los documentos bajo `docs/supermercados/` conservan evidencia e
historia, pero no conceden autoridad ni sustituyen este contrato.

## Estado operativo

- Tráfico live a La Colonia: bloqueado.
- Autorizaciones activas: ninguna.
- SPS technical context: `UNCONFIRMED`.
- Catálogo live completo: no declarado.
- GATE-17: `BLOCKED_EXTERNAL`.
- Ready for live: no.

Los jobs `live-crawl`, `diagnostic` y `facet-discovery` tienen un guard
incondicional `if: ${{ false }}`. El dispatcher y comentarios son observabilidad;
no conceden Request, Approval, Grant, Claim, Capability, Reservation ni autoridad
física.

`COMMENTS / ISSUE COMMENTS / PR COMMENTS / MARKERS / LOGS / ARTIFACTS ARE
OBSERVABILITY ONLY.`

## Contratos y flujo de datos

`RawProduct`, `NormalizedOffer` y `ValidatedOffer` permanecen protegidos e
intactos. La ubicación de las observaciones de La Colonia continúa
`LocationStatus.UNKNOWN`. El estado técnico SPS vive por separado como
`SpsTechnicalContextStatus(CONFIRMED, UNCONFIRMED, UNAVAILABLE)`.

```text
facets sintéticos -> árbol -> hojas deterministas -> plan cerrado
-> ventanas primarias -> overlaps -> segunda travesía/reconciliación
-> unión determinista -> COMPLETE o INCOMPLETE (fail-closed)
```

`COMPLETE` exige simultáneamente árbol y hojas completos, membership válido,
totales estables, ventanas planificadas, respuestas no truncadas, recuperación
total de omisiones, reconciliación por otra travesía, residual cero y unión global
igual al total reportado. Deduplicar nunca demuestra completitud.

Identidad de producto VTEX: `productId -> productReference -> linkText`. Identidad
de SKU: `itemId`. La unión se ordena determinísticamente y no serializa IDs en
resúmenes públicos.

## Autoridad y frontera física — modelo offline

`live_safety.py` es un modelo linealizable en memoria, no infraestructura
productiva. Canonical JSON UTF-8 versionado y domain-separated liga `request_id`,
SHA aprobado inmutable, plan, presupuesto cerrado y epoch.

Transiciones:

```text
Grant: ACTIVE -> CONSUMED | REVOKED
Reservation: RESERVED -> ACTIVATED -> CLOSING -> CLOSED
                         -> UNCERTAIN -> FENCING_REQUIRED -> FENCED
```

Una sección crítica atómica consume el Grant y crea la única reserva global. Una
reserva admite una conexión, un GET, una respuesta final y cero retries. Cada fase
recibe un tiempo finito, no negativo y monotónico por reserva y autoridad, se
contrasta con su deadline cerrado y una violación transiciona a incertidumbre sin
liberar. Pacing se mide start-to-start y exige al menos 1.5 s. Cierre normal y
fencing tienen liberaciones CAS distintas y únicas. El modelo offline exige
evidencia ligada a reserva, epoch, request digest, fase y tiempo, emitida por el
simulador inyectado; no confunde ese emisor de pruebas con un observador productivo
independiente. El inicio físico también exige evidencia ligada: un booleano del
caller no puede afirmar observación ni liberar. Su ausencia deja la reserva
`UNCERTAIN` e instala pacing conservador después del fencing. El reloj monitor usa
`monotonic` por defecto y cada API pública evalúa el deadline activo.

El contrato DNS/TLS offline es un schema cerrado: exige peer seleccionado dentro
de una única resolución controlada, host/SNI/Host exactos, puerto 443 y
verificación de hostname/certificado; niega fallback DNS, Happy Eyeballs, proxy y
proxy de entorno, redirects, pooling/reuse, HTTP/2, HTTP/3, QUIC, retries de
connect/TLS/HTTP, AIA/OCSP/CRL/CT online, certificate URL fetch, Alt-Svc,
speculative connect, preconnect y toda red auxiliar. Una atestación exacta de
capacidades ligada al digest de policy y al issuer privado del enforcer offline es
obligatoria. Esto es `PASS_OFFLINE_MODEL`, no evidencia física productiva.

Todos los adapters reales legacy niegan red por defecto y quedan sellados tras su
construcción. Sólo wrappers explícitos `OfflineTestTransport`/`OfflineTestOpener`
con handlers definidos en módulos `test_*` operan en pruebas. Esa frontera es una
suposición de confianza del harness, no una prueba de aislamiento de proceso ni un
firewall: GATE-06 sólo puede ser `PASS_OFFLINE_MODEL` hasta contar con enforcement
externo. Playwright live valida primero allow-list vacía y, aun con un ID sintético
inyectado, el modo `live` queda globalmente bloqueado; `local_only` existe
exclusivamente para loopback/synthetic tests, bloquea service workers y WebSockets
y deshabilita canales de background conocidos. Tampoco se presenta ese harness
como aislamiento físico productivo.

## Matriz de gates

| Gate | Significado canónico | Estado |
|---|---|---|
| GATE-01 | DEFAULT DENY | PASS_OFFLINE_MODEL |
| GATE-02 | UNIQUE LIVE ENTRY / BLOCK ALTERNATIVES | PASS_OFFLINE_MODEL (todos los jobs live bloqueados) |
| GATE-03 | AUTHORIZATION SEPARATE FROM CONTRACT VALIDITY | PASS_OFFLINE_MODEL |
| GATE-04 | IMMUTABLE SHA / REQUEST IDENTITY | PASS_OFFLINE_MODEL |
| GATE-05 | ONE-SHOT ATOMIC CONSUMPTION / REPLAY | PASS_OFFLINE_MODEL |
| GATE-06 | PHYSICAL EGRESS GUARD | PASS_OFFLINE_MODEL; productivo pendiente |
| GATE-07 | GLOBAL LIVE EXCLUSION | PASS_OFFLINE_MODEL |
| GATE-08 | PHYSICAL DELAY >=1.5s | PASS_OFFLINE_MODEL |
| GATE-09 | PHYSICAL RETRIES <=1 | PASS_OFFLINE_MODEL; implementación usa 0 |
| GATE-10 | CLOSED FAIL-CLOSED BUDGET | PASS_OFFLINE_MODEL |
| GATE-11 | STOP ON 403 | PASS_OFFLINE_MODEL |
| GATE-12 | STOP ON 429 | PASS_OFFLINE_MODEL |
| GATE-13 | STOP ON CAPTCHA / ANTIBOT | PASS_OFFLINE_MODEL |
| GATE-14 | STOP ON AUTH / ADDRESS / GPS REQUIREMENT | PASS_OFFLINE_MODEL |
| GATE-15 | EXCESSIVE LOAD STOP | PASS_OFFLINE_MODEL |
| GATE-16 | TRUSTED WORKFLOW / CODE / SUPPLY CHAIN | PASS_OFFLINE_MODEL; jobs live cerrados |
| GATE-17 | PRODUCTIVE RULESET / PROTECTION EVIDENCE | BLOCKED_EXTERNAL |
| GATE-18 | EXACT FINAL VALIDATION | PASS_OFFLINE_MODEL |
| GATE-19 | ADVERSARIAL OFFLINE COVERAGE | PASS_OFFLINE_MODEL |
| GATE-20 | COMMENTS NON-AUTHORITATIVE | PASS_OFFLINE_MODEL |

Ningún estado de esta matriz autoriza live. La habilitación futura requiere una
revisión independiente, evidencia productiva de GATE-17, decisión humana y una
autorización nueva ligada a un SHA inmutable.
