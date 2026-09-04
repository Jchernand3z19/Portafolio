# Comisariato Los Andes — captura completa SPS 2026-09-04

Esta evidencia corresponde al primer recorrido completo aceptado del catálogo público de Comisariato Los Andes para San Pedro Sula y a su carga inicial verificada en Turso.

## Alcance demostrado

- Tienda: `COMISARIATO LOS ANDES`
- `store_id`: `1`
- `office_code`: `00`
- Departamento: `COR` / Cortés
- Ciudad: `501` / San Pedro Sula
- Modalidad del catálogo: `PD`
- Productos reportados: `6,646`
- Productos únicos reconciliados: `6,646`
- Productos con precio: `6,646`
- Promociones demostradas: `120`
- Solicitudes: `69`
- Reintentos: `0`
- Concurrencia: `1`

La ubicación fue consultada y validada dentro de la misma ejecución que capturó el catálogo. La reconciliación exige cobertura exacta de offsets, hashes SHA-256 de cada respuesta RAW, ausencia de identidades duplicadas, estabilidad del total y una comprobación final del catálogo.

## Semántica de precio

`newPrice` es el precio efectivo observado y `price` debe coincidir con él. Una promoción solo se acepta cuando `oldPrice` es mayor que `newPrice`; cuando `discount` está presente, debe coincidir exactamente con `oldPrice - newPrice`.

En esta captura completa, `listPrice` tuvo el valor literal `PD` en los 6,646 registros. Por lo tanto no se interpreta como importe ni como precio regular.

## Disponibilidad

`availibilityCount` no se usa como stock comercial. En el recorrido completo fue `0` para 6,645 productos y `1000` para uno, aun cuando los 6,646 seguían perteneciendo al catálogo público y tenían precio. La normalización conserva la señal fuente como evidencia y publica `availability=unknown` hasta demostrar una semántica fiable.

## Persistencia inicial en Turso

El snapshot aceptado se recuperó desde el artefacto inmutable de GitHub Actions y se comprobó contra su digest y tamaño antes de cualquier mutación. No se volvió a consultar el supermercado para la carga.

La persistencia inicial quedó confirmada con:

- `persist_run_id`: `comisariato-los-andes-initial-33826831402`
- Productos procesados: `6,646`
- Periodos históricos abiertos: `6,646`
- Periodos históricos cerrados: `0`
- Periodos abiertos verificados después del commit: `6,646`
- Periodos abiertos duplicados: `0`
- SHA-256 almacenado en `scrape_runs`: `a1fe77e3c3132c96c01f7cd792084d47ae25fbb09e3eb69fb67b230d5f09f9fc`
- Run de verificación: `33827599712`
- Artefacto de verificación: `9920510209`

La verificación posterior leyó Turso de nuevo y exigió coincidencia exacta del `run_id`, ubicación, estado `success`, cantidades, hash del snapshot y ausencia de periodos históricos abiertos duplicados.

## Integridad

- Membership SHA-256: `a0d044e6474439a875b20f5648080db53fb755b11629a705eb54487c97d217f9`
- Snapshot SHA-256: `a1fe77e3c3132c96c01f7cd792084d47ae25fbb09e3eb69fb67b230d5f09f9fc`
- Snapshot: `7,189,669` bytes
- Artefacto GitHub Actions: `9920279680`
- Digest del artefacto: `97e6bebc77bb998d55a2bd4200893a96d010daa87e3d1c0efbaf409bb154d461`
- Run de captura: `33826831402`

`evidence.json` es el manifiesto compacto versionado. El artefacto de captura contiene el RAW, ledger y snapshot completo utilizado para producir estos hashes; el artefacto de persistencia conserva los resultados de escritura y verificación de Turso.
