# Walmart TGU — decisión final desde los catálogos completos

**Conservar ambos contextos para persistencia productiva:** `walmart_tgu_ffaa` y
`walmart_tgu_el_sauce`. La comparación completa confirma diferencias comerciales;
la disponibilidad no se usa como motivo de separación. No se ejecutó tráfico live,
SQL Turso ni una nueva observación; se reutilizan exclusivamente snapshots y RAW.

Auditoría: main `b4fa1e942b0c73d1cdb72cd0a47528f26b3bbe68` (PR #354), CI de main
33347966162 verde y ningún PR abierto al iniciar esta comparación. Biblioteca
reusable sin cambios en `252b245e0f416b57c324db97bc9cee868fc8124d`. No existía una
comparación exhaustiva: la evidencia anterior era la muestra de 41 SKU, su control
de región y la repetición del SKU control en full. Este informe completa ese análisis.

## Cobertura y comparación comercial

Identidad comparada: `walmart + item_id + source_key`, sin matching por nombre ni
EAN, y sin unir variantes distintas. Los 12,867 SKU compartidos coinciden también
en padre, item, EAN/referencia cuando existen, unidad y multiplicador; cero conflictos.
Comparación monetaria exacta con Decimal, sin tolerancia ni conversión de unidades;
`is_promotion` se compara como booleano. No se compara precio conocido con NULL.

| Métrica | SKU |
| --- | ---: |
| Catálogo FFAA | 14,091 |
| Catálogo El Sauce | 13,997 |
| Identidades compartidas | 12,867 |
| Sólo FFAA / sólo El Sauce | 1,224 / 1,130 |
| Comparables: efectivo, regular y promoción conocidos en ambos | **12,042** |
| Iguales en los tres campos comerciales | **11,787** |
| Al menos una diferencia comercial | **255** |
| Diferente `current_price` | **218** |
| Diferente `reported_regular_price` | **197** |
| Diferente `is_promotion` | **57** |

Los tres conteos de campos **se superponen**: no suman SKU distintos. La unión es
255, el 2.118% de los 12,042 comparables. Aunque el 97.882% coincide en esta
observación, no hay equivalencia consistente de todo el catálogo: la regla del
usuario conserva dos contextos ante una diferencia real reproducible atribuible
al contexto, no aplica un umbral de mayoría. Los 255 SKU con diferencia comercial
figuran **in_stock en ambas tiendas**.

Desglose disjunto de los 255:

| Campos diferentes | SKU |
| --- | ---: |
| Sólo efectivo | 49 |
| Sólo regular | 1 |
| Efectivo y regular | 148 |
| Efectivo y promoción | 9 |
| Regular y promoción | 36 |
| Efectivo, regular y promoción | 12 |

## Disponibilidad y precios desconocidos: análisis separado

| Caso dentro de la intersección | SKU | Tratamiento |
| --- | ---: | --- |
| Precio/regular/promoción iguales, distinta disponibilidad | **331** | Sólo disponibilidad; no justifica dos TGU |
| FFAA sin precio; El Sauce con precio | **602** | No comparables comercialmente; no contar como diferencia ni igualdad de precio |
| Precio desconocido en ambos | **223** | No demuestra equivalencia de precio/promoción |
| Distinta disponibilidad total | **933** | 331 comparables + 602 sin precio en FFAA |

Los 331 casos de disponibilidad solamente pasan de in_stock FFAA a out_of_stock
El Sauce, conservando precio efectivo/regular/promoción conocidos e iguales.
Los 602 restantes pasan de out_of_stock FFAA (oferta sin precio) a in_stock El
Sauce; no se afirma que disponibilidad sea su **única** diferencia porque faltan
los valores comerciales de FFAA. Los 223 sin precio en ambos figuran agotados.
No hay casos compartidos con precio conocido sólo en FFAA.

De los 11,787 comercialmente iguales, 11,456 también comparten disponibilidad y
331 difieren sólo en disponibilidad. Los 825 con algún precio desconocido se
excluyen de la comparación comercial, pero permanecen en sus snapshots. NULL no
es cero, igualdad demostrada ni una diferencia de precio. Los 2,354 SKU fuera de
la intersección tampoco se convierten en agotados ni justifican separar contextos.

## Diferencias y atribución al contexto

Ejemplos observados en los snapshots; moneda HNL, precios sin transformación:

| SKU / producto | Efectivo FFAA | Efectivo El Sauce | Regular FFAA | Regular El Sauce | Promoción FFAA / El Sauce |
| --- | ---: | ---: | ---: | ---: | --- |
| 10063 · Frijol Verde Habichuela 454 g | 20.50 | 29.90 | 20.50 | 29.90 | no / no |
| 10082 · Harina de Trigo Suli 2268 g | 57.00 | 47.30 | 57.00 | 47.30 | no / no |
| 10465 · Gotas Panadol Bebés 15 ml | 65.92 | 76.00 | 82.40 | 76.00 | sí / no |
| 11343 · Lubriderm Reparación Intensiva 400 ml | 297.00 | 372.70 | 372.70 | 372.70 | sí / no |
| **68100 · Enfriador Mainstays 65 W 12 L** | **1,895.00** | **1,895.00** | **2,195.00** | **1,895.00** | **sí / no** |

Los 255 casos completos, con valores de ambos lados, SKU, padre, nombre, EAN y
URL/SHA/fecha de ambas páginas RAW están en [tgu-comparison.json](tgu-comparison.json).
No se eligieron sólo ejemplos favorables para calcular el resultado.

El binding en cada página aceptada es la faceta de membership de su tienda y su
`regionId`, con el mismo canal 1, país HND y dominio público. Se verificaron los
**28,088 SKU de ambos snapshots contra 319 páginas RAW aceptadas**, incluyendo sus
detalles fuente. No se usaron las páginas incompletas descartadas de la captura.

El SKU `68100` ya tiene un [control previo reproducible](../2026-08-31-probe/README.md):
solicitudes 7/8 (muestra), 9/10 (búsqueda puntual), y 9/12 (mismo membership y demás
parámetros, cambiando **sólo `regionId`**). Cambió regular/promoción de 2,195/sí a
1,895/no, con efectivo 1,895. Ambos fulls reproducen esos valores. Este control,
reverificado desde el RAW existente, demuestra al menos una diferencia comercial
atribuible al contexto y basta para conservar ambos según la regla acordada.

Límite de la conclusión: FFAA se observó 00:55:48–00:58:43 UTC; El Sauce
00:58:44–01:04:45 UTC del 31/8/2026. No son capturas simultáneas ni un experimento
cambiando sólo región para cada uno de los 255 SKU. El informe demuestra 255
diferencias entre esos snapshots y la atribución causal ya controlada para el
SKU 68100; no atribuye causalmente cada diferencia individual ni garantiza que
permanezca en el futuro. Esa limitación no requiere recrawl para esta decisión.

## Reproducción y consecuencia para persistencia

Desde la raíz del repositorio:

```bash
python precios-supermercados-sps/reports/walmart/2026-08-31-full/compare_tgu.py --check
PYTHONPATH=precios-supermercados-sps/src pytest precios-supermercados-sps/tests/test_walmart_tgu_full_comparison.py -q
```

El verificador puntual usa las capacidades existentes de validación y parseo.
Comprueba hashes de ambos JSON comprimidos/descomprimidos y archivo RAW; contrasta
cada fila con la página correspondiente; reproduce el control anterior; recalcula
conteos, diferencias y decisión; compara el informe versionado y todas las filas
CSV. Sin `--check` regenera únicamente estos dos archivos derivados; no hace red
ni ejecuta SQL. No es un framework o updater nuevo.

[tgu-comparison.csv.gz](tgu-comparison.csv.gz) contiene **las 12,867 identidades
compartidas**, incluidos casos iguales y no comparables, con los tres campos de
cada tienda, disponibilidad, clasificación, SHA de página y fecha. Celdas vacías
de diferencias comerciales significan *no comparable*, no False. Los hashes de
entrada y SHA del CSV descomprimido constan en el JSON; los snapshots y RAW originales
no cambiaron. Las pruebas bloquean HTTP y cubren disponibilidad sola, NULL en uno/
ambos contextos, comparación monetaria y evidencia alterada.

Validación local: **51 pruebas pasaron** de comparación, captura y persistencia
Walmart, incluido el chequeo byte a byte del informe y CSV. No cambia el SQL; CI
debe validar además la suite completa del proyecto antes de fusionar.

**Decisión final:** mantener `walmart_tgu_ffaa` y `walmart_tgu_el_sauce` para la futura
persistencia productiva. No consolidar ni elegir una tienda representativa porque
se perderían diferencias comerciales demostradas. No modificar SQL, esquema,
identidades, snapshots ni cantidades de la carga preparada; la migración puntual y
las pruebas de aislamiento previas siguen siendo aplicables. No ampliar a todas las
zonas de entrega ni afirmar precio universal de Tegucigalpa.

Trabajo offline de catálogo y persistencia concluido; la entrega de esta comparación
se valida mediante tests/CI. Pendiente operativo: comprobar reset y esquema remoto,
backup, migración única, primera carga controlada y segunda observación real según
autorización vigente. No se ejecutó Turso, no se activaron overages y no se diseñó
recurrencia. Reproducir RAW no sustituye segunda observación real.
