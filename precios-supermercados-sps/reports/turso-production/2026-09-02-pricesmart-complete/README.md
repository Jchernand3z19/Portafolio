# Turso producción — PriceSmart completo

El catálogo público completo de PriceSmart fue persistido incrementalmente desde
`main` `d32d099b94e9a185964317a545a9585d2bd1e1c3`, PR #369. Sólo se cargaron SPS
club 6603 y Florencia club 6602. No hubo recrawl, El Sauce, recurrencia, cambio de
esquema, billing ni overages.

## Resultado

| Ubicación | Run ID | Productos fuente | SKU actuales | Nuevos | Sin cambio | Cerrados |
|---|---|---:|---:|---:|---:|---:|
| SPS 6603 | `pricesmart-complete-20260902-sps-6603-eeabfa9f35f9` | 2,766 | 6,078 | 4,951 | 1,127 | 0 |
| Florencia 6602 | `pricesmart-complete-20260902-tgu-6602-2d09bfe3e17f` | 2,766 | 6,078 | 4,951 | 1,127 | 0 |

Los hashes JSON persistidos son `eeabfa9f35f9cfce269aa6a196fcbe471654cfb26754431001cf7cc37593aaec`
para SPS y `2d09bfe3e17f65197008e9392a16af3e99802a8f3b36753f5c901b14aacc44e6`
para Florencia. Cada run quedó ligado a
`github-main-d32d099-pr369-pricesmart-complete`.

Los 1,127 periodos previos de Alimentos por ubicación permanecen abiertos y
ligados a sus runs originales. Los runs nuevos abrieron exactamente 4,951
periodos cada uno. PriceSmart termina con 6,078 productos persistibles, 2,766
productos fuente y 12,156 periodos actuales; no tiene periodos cerrados.

## Estado final

La base conserva cinco tablas, cuatro supermercados y ocho ubicaciones. Los
conteos finales son 40,824 productos, 84,230 filas de historial y 15 runs. Hay
cero periodos actuales duplicados, cero violaciones FK e `integrity_check=ok`.
Los conteos de La Colonia, Colonial y Walmart coinciden con el checkpoint previo.

## Consumo

| Punto | Filas leídas | Filas escritas | Storage |
|---|---:|---:|---:|
| Antes | 2,175,665 | 545,341 | 25 MB |
| SPS + verificación | 2,948,298 | 598,248 | 28 MB |
| Florencia + verificación final | 3,041,775 | 631,351 | 29 MB |

La operación completa, incluidas sus verificaciones adyacentes, consumió 866,110
filas leídas y 86,010 escritas. Quedan 496,958,225 lecturas y 9,368,649 escrituras
de las cuotas Starter. El uso final es 0.608355% de lecturas y 6.31351% de
escrituras. Overages permanecen deshabilitados; la cuota indica reset el
30 de septiembre de 2026 a las 18:00 CST.

El token temporal no se publica y su archivo local fue eliminado. La evidencia
estructurada está en `evidence.json`; `verify.py` comprueba hashes, aritmética,
snapshots y los invariantes documentados sin conectarse a Turso.
