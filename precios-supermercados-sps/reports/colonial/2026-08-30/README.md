# Primera captura Colonial — evidencia, no cierre del MVP

Captura pública autorizada del 2026-08-30, de 20:11:03 a 20:31:00 UTC, aceptada
después de corregir el parser **offline**. No se ha cargado en Turso ni existe
segunda observación real. La autorización de 24 horas fue registrada a las
20:10:18 UTC; no concede recurrencia ni cambios de facturación.

- `full-catalog.json.gz`: bytes exactos del snapshot aceptado; 9,199 productos,
  9,205 variantes. Descomprimido mide 4,481,582 bytes; su SHA-256 está en `evidence.json`.
- `raw-capture.tar.gz`: 433 cuerpos HTTP completos, `requests.json` portable con
  URL/fecha/status/SHA por recurso y el ejecutor inicial. No contiene headers,
  cookies de sesión guardadas ni respuestas autenticadas. El HTML público contiene
  sus scripts y referencias de imágenes, pero esos assets no se solicitaron.
- `evidence.json`: preflight, adquisición, eficiencia, hashes y límites de evidencia.
- `offline-sql-summary.json`: SQL real del updater sobre SQLite local compartido,
  con snapshots SPS/TGU del artifact 9734740995. **No es una respuesta de Turso.**

El ejecutor inicial conservado rechazó la reconciliación final porque una tarjeta
mostraba el precio de otra variante del mismo producto. No publicó snapshot
aceptado. El parser corregido de este PR reconstruye todos los productos desde
ese mismo RAW, sin solicitudes nuevas. `test_colonial_full_capture.py` verifica
los hashes, reproduce los datos y bloquea cualquier intento de red.

El snapshot registra las métricas del parseo offline (cero HTTP, 1.739 segundos).
Las métricas de adquisición están separadas: **426 GET nuevos + 7 respuestas del
probe reutilizadas = 433 recursos**; 439 GET si se incluyen ambos probes completos.
Todas las respuestas de la captura completa fueron 200; cero retries. Los inicios
del primer y último GET nuevo distan 541.385 segundos; no es una medida del cierre
del parser. El presupuesto fue 450 solicitudes nuevas y 1,200 segundos.

Para reconstruir desde la raíz del repositorio, con las dependencias existentes:

```bash
mkdir -p /tmp/colonial-capture
tar -xzf precios-supermercados-sps/reports/colonial/2026-08-30/raw-capture.tar.gz -C /tmp/colonial-capture
python precios-supermercados-sps/scripts/obtener_catalogo_colonial.py \
  --offline --reuse-cache /tmp/colonial-capture --output /tmp/colonial-reparsed
```

`--output` debe ser una carpeta nueva. Los productos se reproducen; las métricas
de ejecución cambian. Para replay idempotente de persistencia se usan los bytes
originales de `full-catalog.json.gz`, no un JSON serializado otra vez.

Los SHA de la captura vinculan el snapshot y el SQL offline. Las garantías live
pendientes se describen en [PROJECT_STATE](../../../docs/PROJECT_STATE.md).
