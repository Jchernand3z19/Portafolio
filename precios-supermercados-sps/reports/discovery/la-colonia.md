# Descubrimiento técnico — La Colonia

## Alcance

Prueba controlada del catálogo público de La Colonia. No incluye extracción completa, persistencia, carrito, cuenta ni pedidos.

## Fuente confirmada

- Plataforma: VTEX Store Framework.
- Catálogo público: `https://www.lacolonia.com/supermercado`.
- Operación: `productSearchV3`, derivada de `QueryProductSearchV3` del paquete oficial `vtex.store-resources`.
- Ruta pública: `https://www.lacolonia.com/_v/segment/graphql/v1`.
- Método: consulta GraphQL GET explícita, limitada a una página y cinco SKU.
- No utiliza cookies, tokens, cuentas ni datos personales.

Un hash persistido candidato fue descartado después de que La Colonia respondiera `PERSISTED_QUERY_NOT_FOUND`. No se probaron hashes adicionales. La consulta explícita mínima fue aceptada por la misma ruta pública y devolvió productos y precios.

## Cumplimiento de robots.txt

`robots.txt` excluye, entre otras, las rutas `/api*`, `/busca*` y `/buscapagina*`. No excluye `/_v/`.

El cliente bloquea antes de enviar cualquier petición a:

- rutas excluidas configuradas;
- `mobile.lacolonia.com`;
- hosts diferentes de `www.lacolonia.com`;
- URLs que no utilicen HTTPS.

## Ubicación provisional aprobada

```text
location_id = la_colonia_online
location_status = unknown
location_evidence = Catálogo público en línea sin selección obligatoria de ciudad o sucursal.
location_confidence = null
```

No se asocia el catálogo con Plaza Pedregal, una tienda física, un seller regional o un `regionId`.

## Resultado live controlado

Fecha UTC de validación: 2026-08-05.

```text
productos informados por la fuente: 9291
páginas procesadas: 1
productos solicitados: 5
productos extraídos: 5
productos con precio: 5
duplicados: 0
errores: 0
eventos estructurales: 0
bloqueos: 0
```

### Muestra sanitizada

| ID interno | Producto | Marca | Presentación | Precio actual | Precio regular informado | Promoción |
|---|---|---|---|---:|---:|---|
| `18346` | Alimento Líquido Pediasure 10+ Vainilla 220 Ml | Pediasure | 220 Ml | 108.15 | — | No |
| `18347` | Alimento En Polvo Enterex Kids Vainilla 400 Gr | Enterex | 400 Gr | 638.35 | — | No |
| `18348` | Alimento En Polvo Enterex Kids Vainilla 800 Gr | Enterex | 800 Gr | 1346.35 | — | No |
| `18349` | Alimento En Polvo Enterex Total Vainilla 800G | Enterex | 800G | 1057.95 | — | No |
| `18350` | Arena Para Gatos Biomaa 6 Kg | Biomaa | 6 Kg | 274.95 | — | No |

Los cinco productos incluyeron URL individual y categoría jerárquica.

## Disponibilidad

La respuesta live devolvió simultáneamente precio positivo y cantidad `0` para los cinco productos. Esa combinación no se considera prueba inequívoca de agotado porque la consulta no posee contexto regional confirmado.

Regla adoptada:

```text
precio positivo + cantidad positiva
→ in_stock

precio ausente + cantidad explícita cero
→ out_of_stock

precio positivo + cantidad cero
→ unknown + quality:availability_conflict_price_with_zero_quantity
```

La extracción de precios fue aceptada, pero los cinco productos quedaron pendientes de revisión de disponibilidad.

## Paginación

La fuente informó 9,291 productos. Con el límite de cinco usado exclusivamente en la prueba se calculan 1,859 páginas. Esto no representa la estrategia futura de extracción completa; antes de ampliarla deberá validarse un tamaño de página mayor permitido y umbrales de cobertura.

La paginación usa índices inclusivos `from` y `to`:

```text
página 1: 0–4
página 2: 5–9
```

## Campos confirmados

- ID interno del SKU;
- ID interno del producto;
- referencia/SKU cuando existe;
- EAN cuando existe;
- nombre;
- marca;
- categoría y subcategoría derivadas de la ruta original;
- presentación;
- imagen;
- URL individual;
- precio actual;
- precio regular informado cuando supera el actual;
- evidencia estructurada de promoción;
- seller original en auditoría;
- unidad comercial;
- multiplicador;
- cantidad publicada;
- valores originales de auditoría.

## Riesgos y limitaciones

- La disponibilidad pública sin región puede ser ambigua.
- La muestra live no incluyó un producto promocional ni pesable; ambos casos están cubiertos por fixtures offline, pero requieren muestra live dirigida antes de una extracción completa.
- El total del catálogo es dinámico.
- La consulta explícita depende del esquema público de `vtex.search-graphql` y debe detectar cambios estructurales.
- No se validó todavía un tamaño de página superior a cinco.
- No se validó recorrido completo, persistencia ni comparación entre ejecuciones.

## Decisión

La prueba demuestra que es posible obtener productos, precios, IDs y URLs desde una fuente pública permitida. El scraper puede continuar a una siguiente fase controlada, con la condición de mantener `availability = unknown` cuando exista conflicto entre precio y cantidad y de validar después productos promocionales y pesables en vivo.
