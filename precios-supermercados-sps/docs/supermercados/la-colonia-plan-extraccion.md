# La Colonia — plan de extracción posterior a la radiografía

## Estado

Este plan no autoriza ejecución. La radiografía actual es incompleta y no permite full crawl.

## Objetivo

Construir un scraper verificable para el catálogo público de La Colonia, con contexto reproducible de San Pedro Sula, identidad por SKU, cobertura demostrable y operación conservadora.

## Fase 1 — Resolver ubicación SPS

Prueba propuesta, todavía no autorizada:

1. abrir sesión pública nueva;
2. registrar el estado por defecto sin publicar cookies;
3. seleccionar San Pedro Sula mediante la UI pública;
4. identificar nombres de mecanismos: cookie/localStorage/sessionStorage/query/header/contexto VTEX;
5. registrar solo campos públicos no sensibles;
6. repetir una consulta raíz y un SKU conocido antes/después;
7. comparar precio, seller y disponibilidad;
8. clasificar ubicación como `confirmed`, `inferred` o `unknown`.

Criterio de salida: una consulta reproducible debe demostrar que corresponde a SPS. Si no, conservar `location_not_verified`.

## Fase 2 — Capturar taxonomía y facets

1. obtener raíz con página pequeña y orden `OrderByNameASC`;
2. capturar respuesta de facets sanitizada;
3. separar `category-1`, categoría, subcategoría y specifications;
4. registrar IDs, slugs, cantidades, hijos y sampling;
5. excluir marca, landing, búsqueda y product clusters como particiones estructurales;
6. marcar valores corruptos, especialmente Impuestos.

Criterio de salida: árbol estructural versionable con categorías hoja candidatas y evidencia de sampling.

## Fase 3 — Validar paginación

Usar concurrencia 1, pausa >=1.5 s y un máximo de una repetición.

Muestras:

- raíz: dos páginas consecutivas;
- categoría pequeña: primera y última página;
- categoría mediana: dos páginas;
- categoría grande: frontera controlada;
- búsqueda: una página para demostrar que no es partición.

Validar:

- `from/to` inclusivos;
- page size real;
- total estable;
- orden estable;
- firmas de página no repetidas;
- páginas parciales;
- límite máximo y sampling.

## Fase 4 — Validar campos de producto

Muestra mínima:

- normal;
- promoción;
- agotado;
- por peso;
- varios SKU/presentaciones;
- EAN ausente, si aparece.

Validar `productId`, `itemId`, references, EAN, seller, Price, ListPrice, cantidad, unidad, multiplicador, imágenes y categorías.

## Fase 5 — Cobertura y deduplicación

Estrategia recomendada: híbrida.

1. raíz paginada como universo de referencia;
2. categorías hoja como particiones operativas;
3. deduplicación por `itemId`;
4. relación secundaria por `productId`;
5. unión de hojas;
6. comparación contra raíz;
7. residuales raíz - hojas;
8. solapamientos entre hojas;
9. detección de conjuntos idénticos;
10. reporte de productos sin hoja.

No usar suma de cantidades como prueba de cobertura.

## Fase 6 — Normalización

Reglas iniciales:

- `effective_price = Price`;
- `reported_regular_price = ListPrice` solo si `ListPrice > Price`;
- promoción declarada si diferencia válida o teaser;
- `availability` combinando seller, precio y AvailableQuantity;
- presentación desde atributos SKU, fallback conservador a `nameComplete`;
- ubicación desconocida hasta evidencia SPS;
- identidad SKU por `itemId`, fallback según `select_source_key`.

## Fase 7 — Presupuesto

No calcular solicitudes definitivas hasta conocer:

- total raíz bajo SPS;
- page size seguro;
- número real de categorías hoja;
- sampling;
- solapamiento;
- necesidad de detalle individual.

Fórmula preliminar:

```text
requests_root = ceil(root_total / page_size)
requests_leaves = sum(ceil(leaf_total / page_size))
requests_validation = muestras + repeticiones
requests_total = requests_root + requests_leaves + requests_validation
```

El plan final debe minimizar duplicación y permanecer bajo un presupuesto explícito aprobado.

## Recuperación de errores

Detener ante:

- 403 persistente;
- 429;
- captcha/antibot;
- autenticación;
- JSON inválido;
- cambio estructural;
- página repetida;
- página parcial inesperada;
- total inconsistente por encima del umbral aprobado.

Conservar checkpoints sanitizados y no repetir páginas ya aceptadas.

## Orden de implementación recomendado

1. detector/contexto de ubicación pública;
2. parser de facets sanitizadas;
3. modelo de particiones estructurales;
4. pruebas offline con muestras capturadas;
5. validación de paginación pequeña;
6. validación de productos representativos;
7. cálculo de cobertura y presupuesto;
8. solo después, autorización de recorrido progresivo.

## Siguiente prueba exacta propuesta

```text
Nombre: SPS-context-and-root-facets-001
Objetivo: confirmar contexto público de San Pedro Sula y capturar una sola respuesta raíz/facets
Concurrencia: 1
Pausa: >=1.5 segundos
Reintentos: máximo 1
Productos: page size mínimo, sin recorrido adicional
Full crawl: no
Estado: propuesta, no autorizada
```

## Criterios para declarar listo para implementación

- ubicación SPS reproducible;
- precio y seller bajo ese contexto;
- facets sin sampling desconocido;
- árbol estructural identificado;
- límite de paginación confirmado;
- identidad product/SKU confirmada;
- muestra de promoción, agotado y peso;
- presupuesto calculado.

## Criterios para declarar listo para full crawl

Además de lo anterior:

- total raíz estable;
- unión de hojas medida;
- residuales explicados;
- solapamientos cuantificados;
- páginas no repetidas;
- cero 403/429 persistentes;
- umbrales aprobados;
- autorización explícita nueva.
