# Maxi Despensa + Despensa Familiar — probe conjunto cerrado

**No apto para full ni persistencia con la fuente observada.** Se demuestran web
compartida, formatos y un directorio, pero no precio efectivo/regular/promoción ni
binding comercial de tienda. No se crean catálogos ficticios, ubicaciones productivas
ni integración SQL. Esto no prueba que jamás exista otra fuente pública útil.

Base auditada: main `9592901c95aa2cb447effe1c514fe85eb5e74265`, PR #356 fusionado,
[CI main verde](https://github.com/Jchernand3z19/Portafolio/actions/runs/33355963991),
cero PRs abiertos. Biblioteca reusable sin cambios en
`252b245e0f416b57c324db97bc9cee868fc8124d`; continúan las seis skills web y
production-data-engineering. No se modifican implementaciones anteriores.

## Autorización y tráfico

El usuario aprobó por 24 horas el probe conjunto propuesto; registro al comenzar
el turno: **2026-08-31T04:20:37Z → 2026-09-01T04:20:37Z**. Techo acordado de 40 GET,
dos redirects y cuatro retries incluidos, concurrencia 1 y 15 minutos por ejecución.
No full, recurrencia, SQL Turso, billing ni bypass. La aprobación no amplía esos
límites a un crawl de 24 horas.

Primer GET 04:22:28.777807Z; último 04:26:09.363334Z. Cierre temprano a los
**273.325 segundos** por falta de precio/contexto demostrable, sin gastar el saldo
en repetir páginas sin evidencia de utilidad. Captura cerrada; el ledger no se
reinicia ni el saldo se convierte en permiso para otro full/probe.

| Métrica | Resultado |
| --- | ---: |
| Solicitudes GET totales, reintento incluido | 21 |
| HTTP 200 | 17 |
| Respuestas 301 | 2 |
| Redirects seguidos | 0 |
| Timeouts | 2 |
| Retries | 1 |
| Concurrencia | 1 |
| Scripts descargados | 1 |
| Recargas del inicio evitadas por cache de redirects | 2 |
| Filas de producto en los dos listados | 97 |
| Códigos candidatos distintos | 96 |
| Filas por request de listado de producto | 48.5 |
| Requests totales por código candidato | 0.21875 |
| Productos aceptados para persistencia | 0 |
| Requests por catálogo completo | No aplica |

No browser, imágenes, CSS, fonts, analytics, tiles de mapa, formularios enviados,
login, carrito, checkout ni mutaciones. Los dos redirects de delivery/pickup vuelven
al inicio ya capturado. El único destino externo consultado fue el enlace público
«Compra en línea» del propio catálogo, dos GET al mismo URL; ambos terminaron en
timeout, sin respuesta HTTP capturada y sin conclusión sobre autenticación o bloqueo remoto.

## Fuente y contrato realmente observados

- [Inicio](https://maxidespensa.com.hn/) (`01.raw`) presenta ambas marcas. HTML
  renderizado por servidor con assets Webflow/jQuery; el patrón de formularios
  sugiere CakePHP, sin comprobar backend/versión. No se demostró VTEX ni API común
  con Walmart. El script `action_home.js?v2` (`04.raw`) sólo añade interacción UI.
- [Localizador](https://maxidespensa.com.hn/encuentra-tu-tienda-despensa-y-maxi-despensa-honduras)
  (`03.raw`): literal JavaScript con **99 entradas**, **71 formato `4` = Despensa**
  y **28 formato `6` = Maxi Despensa**. Campos `title`, `formato`, `ubicacion`,
  `horario`, `geometry`; no store_id, SKU, precio, city_id ni warehouse_id.
  El selector filtra marcadores Leaflet por formato: **no es prueba de selector
  de precios**, sesión comercial ni disponibilidad de producto por sucursal.
- [Abarrotes de campaña](https://maxidespensa.com.hn/accion-comercial/aqui-si-te-alcanza-tu-suelto/aqui-si-te-alcanza-tu-suelto-26-abarrotes)
  (`06.raw`): 90 tarjetas con nombre y código visible; **cero nodos activos de
  precio**. Hay 90 ejemplos `Q20.00` dentro de comentarios HTML, con fecha de 2019:
  no son precios, ni HNL observado, ni promociones aceptables.
- [Arroz y frijol regular](https://maxidespensa.com.hn/precio-bajo-siempre-despensa-y-maxi-despensa-honduras/alacena/arroz-y-frijol)
  (`09.raw`): siete tarjetas, sin precio. El código es candidato derivado del sufijo
  de URL; no se transforma automáticamente en GTIN válido. Un código, `70751700208`,
  coincide con campaña: **97 filas, 96 códigos**, sin ocultar el solapamiento.
- Una ficha de campaña y una regular (`10.raw`, `19.raw`) tampoco ofrecen precio
  numérico activo. La regular contiene otro precio de plantilla comentado,
  `Q30.50`, que se descarta. Vigencia de campaña hasta 15/10/2026 no demuestra
  descuento, precio anterior ni estado `is_promotion=true` por SKU.
- La búsqueda GET declarada por el formulario, con el código conocido
  `85041800708` (`20.raw`), no devolvió resultados. No se infiere ausencia/OOS.
- El CTA público [Compra en línea](https://centroamerica.walmart.com/1/account?countryId=5&formatId=18)
  (`13` y `14` en ledger) es el único indicio de otra superficie comercial. Dos
  timeouts de ~20 s, un retry, ningún RAW de respuesta. `countryId=5&formatId=18`
  se conserva como query del enlace, **no se equipara** al formato `6` del mapa
  ni a un store ID. Otra ficha contiene incluso un enlace `countryId=3&formatId=10`;
  no se siguió ni se atribuyó a Honduras por analogía.

No se demostró endpoint batch, paginación de catálogo comercial, totales
autoritativos, disponibilidad por SKU, canal/tienda en cookies, headers o storage.
No se modificaron cookies/contextos manualmente ni se ejecutó browser para observar
storage. Presencia de logo/formato, texto «Disponible en» y campañas no sustituyen
precio, stock ni binding. Todos esos campos comerciales quedan desconocidos.

## Tiendas y decisión de granularidad

[Candidatos geográficos](store-candidates.json): 29 entradas, localizadas a partir
de direcciones/coordenadas del RAW, **no un censo municipal autoritativo**. El
directorio no aporta city_id; límites urbanos/municipales y casos periféricos
siguen pendientes. No se consultaron catálogos de otras ciudades. Las 99 entradas
del localizador se preservan en RAW como metadata incidental del mismo recurso.

| Grupo candidato | Entradas | Comparación comercial | Representantes aceptados |
| --- | ---: | --- | --- |
| Maxi SPS | 3 | No demostrada | Ninguno |
| Maxi TGU | 6 | No demostrada | Ninguno |
| DF SPS | 6 | No demostrada | Ninguno |
| DF TGU | 14 | No demostrada | Ninguno |

Detalles públicos de Salida La Lima, Arturo Quesada, Siete Calle y Guanacaste
(`15`–`18`) confirman directorios/direcciones, sin price context. Incluso las
fichas Maxi usan rutas `ubicaciones-despensa-familiar-honduras`; **el slug no
identifica formato ni tienda comercial**. Los listados Maxi/DF tienen rutas
colisionantes como `/kennedy`; no se usarán como identidad común sin prueba.

**SKU comparables por tienda: 0.** Diferencias de efectivo, regular, promoción y
sólo disponibilidad: **no evaluables (`null`), no cero diferencias**. No existen
20–50 SKU válidos comparables por formato/ciudad. No se consolida ninguna tienda,
no se justifica separarlas por stock y no se fabrican cuatro locations nominales.
La decisión de granularidad queda pendiente de fuente comercial demostrada.

## Evidencia, seguridad y reproducción offline

- [evidence.json](evidence.json): 97 observaciones fuente, códigos, URLs, referencias
  RAW, unknowns, métricas y decisión. Ninguna fila está aceptada para persistencia.
- [raw-capture.tar.gz](raw-capture.tar.gz): 19 respuestas, ledger de 21 solicitudes
  y manifiesto de redacción. **141,745 bytes**, SHA-256
  `eacae1b532ad6d9151aae0e72e326bec6709c58ae5397be67fdfcf7dc37221d3`.
- Se redactaron **28 valores de formularios CSRF** antes de publicar. El ledger
  diferencia SHA/tamaño original de SHA/tamaño publicado y contabiliza redacciones.
  Originales íntegros quedan en el directorio privado de captura; no se cambió
  ningún dato de producto, precio o localizador. La verificación pública comprueba
  los bytes publicados, no afirma recuperar tokens ni comprobar originales ausentes.
- [verify.py](verify.py) reproduce la evidencia sin red; no es un scraper productivo.
  Verifica hashes, límites, fechas, pacing, redacción y estructura observada.
  Ocho pruebas impiden aceptar precios comentados, unknowns como igualdad,
  códigos incoherentes y RAW alterado. Los fixes del analizador fueron offline.

```sh
python precios-supermercados-sps/reports/maxi-df/2026-08-31-probe/verify.py
```

## Siguiente frontera

**No solicitar full con esta evidencia.** Hace falta una URL/fuente pública que
muestre precio de producto y permita demostrar su formato/contexto, o resolver el
acceso público al destino de compra enlazado. No afirmar que un timeout exige login
ni intentar otro método para sortear un control. Una URL aportada por el usuario
permitirá precisar el siguiente probe; no extender alcance a otra cadena.

Después de esa prueba: misma muestra entre todas las tiendas relevantes, grupos
por efectivo/regular/promoción (availability aparte), full sólo de representantes
con autorización específica y presupuesto medido. Persistencia y matriz de
aislamiento/escala se validarán offline sólo después de contrato y catálogo reales.
Hoy no hay bug compartido demostrado que justifique cambiar SQL, esquema, parsers
o fixtures anteriores. Turso permanece sin consultas; su bloqueo no causa ni
resuelve la falta de precios en esta fuente.
