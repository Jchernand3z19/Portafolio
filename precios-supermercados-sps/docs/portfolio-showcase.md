# Presentación del proyecto en el portafolio

Este documento define qué información de `precios-supermercados-sps` se muestra públicamente, de dónde sale y qué límites de interpretación deben respetarse.

## Prioridad de presentación

Desde el 4 de septiembre de 2026, **Precios de Supermercados** es el proyecto principal del portafolio y comunica explícitamente la capacidad de **Web Scraping**. **Mundial 2026** permanece como segundo proyecto independiente.

Orden público:

1. Precios de Supermercados — Web Scraping, automatización e inteligencia de precios.
2. Mundial 2026.

## Cifras públicas verificadas

El portafolio debe reflejar el último estado productivo confirmado en `PROJECT_STATE.md`. Hasta que una ejecución más reciente termine y sea verificada, el corte público vigente es:

| Métrica | Valor exacto de soporte | Valor mostrado |
| --- | ---: | ---: |
| Supermercados / cadenas productivas | 6 | 6 |
| Ubicaciones monitoreadas | 11 | 11 |
| Productos registrados | 56,769 | 56K+ |
| Periodos históricos de precio | 108,315 | 108K+ |
| Ciudades con cobertura integrada | 2 | 2 |

### Cobertura por supermercado

| Supermercado | Ubicaciones con datos productivos aceptados |
| --- | --- |
| La Colonia | SPS, Tegucigalpa |
| Supermercados Colonial | SPS |
| Walmart | SPS, TGU FFAA, TGU El Sauce |
| PriceSmart | SPS 6603, Florencia 6602 |
| Comisariato Los Andes | SPS |
| Paiz | TGU Multiplaza, TGU Próceres |

La interfaz muestra las seis cadenas. La cobertura de scraping **no equivale** a cobertura de comparación cross-source.

## Extracción web comprobable

La interfaz mantiene una prueba pública concreta de que el proyecto obtiene datos desde una web real.

Captura aceptada de **Comisariato Los Andes**:

- sitio público: <https://comisariatolosandes.com/>;
- ciudad: San Pedro Sula;
- captura: `2026-09-04T01:44:35.172709Z`;
- productos con precio: `6,646`;
- promociones detectadas: `120`;
- artifact de GitHub Actions: `9920279680`;
- snapshot SHA-256: `a1fe77e3c3132c96c01f7cd792084d47ae25fbb09e3eb69fb67b230d5f09f9fc`;
- evidencia versionada: [`../reports/comisariato-los-andes/2026-09-04-full/`](../reports/comisariato-los-andes/2026-09-04-full/README.md);
- metadatos públicos reducidos: [`../portfolio/scraping-proof.json`](../portfolio/scraping-proof.json).

La página enlaza tres niveles de comprobación: fuente web, evidencia aceptada y código. No publica credenciales, cookies ni el dataset productivo completo.

## Comparación cross-source: política pública

La comparación directa de precios entre supermercados es fail-closed.

La antigua muestra de 10 productos entre Comisariato Los Andes y Supermercados Colonial se retiró porque la regla utilizada —**misma marca + misma presentación/cantidad**— no demuestra que dos registros sean el mismo producto comercial. En particular, `Passion Jaguar` y `Passion Especial` no deben transformarse en una comparación automática sólo porque comparten marca y presentación.

Por tanto:

- [`../portfolio/sample-data.json`](../portfolio/sample-data.json) publica actualmente `rows: []`;
- no se muestra un “mejor precio” cross-source mientras la fila no supere el gate seguro;
- falta de comparación no se interpreta como precio cero, empate ni ausencia del supermercado;
- una coincidencia textual puede servir como candidato de revisión, pero no como autorización analítica.

La política que autoriza una comparación exige identidad fuerte y coherencia de marca, tipo, presentación y descriptores comerciales. El detalle está en [`COMPARATOR-METHODOLOGY.md`](COMPARATOR-METHODOLOGY.md).

El contrato público derivado es [`PUBLICATION-DATA-DICTIONARY.md`](PUBLICATION-DATA-DICTIONARY.md). Los consumidores —incluido Power BI— no vuelven a reconstruir matching por nombre, marca o presentación.

## Evidencia analítica segura que sí puede mostrarse

Mientras la muestra cross-source se mantiene cerrada, el portafolio puede mostrar hallazgos reproducibles donde la identidad ya está demostrada dentro de una misma cadena.

### Walmart TGU

La comparación exhaustiva de FFAA y El Sauce usa identidad `walmart + item_id + source_key`, no matching por nombre o EAN. Evidencia: [`../reports/walmart/2026-08-31-full/TGU-COMPARISON.md`](../reports/walmart/2026-08-31-full/TGU-COMPARISON.md).

Resultados respaldados:

- 12,867 identidades compartidas;
- 12,042 artículos con efectivo, regular y promoción conocidos en ambos contextos;
- 11,787 iguales en los tres campos comerciales;
- 255 con al menos una diferencia comercial;
- 218 con diferente `current_price`.

Estas cifras son evidencia intra-cadena; no se presentan como matching entre supermercados diferentes.

### PriceSmart

Puede mantenerse el hallazgo versionado de `115` artículos con diferencia de precio actual entre dos clubes dentro del universo documentado de `5,129` productos con precio en ambos, siempre que la interfaz conserve su procedencia intra-cadena y el corte histórico correspondiente.

### Comisariato Los Andes

La captura pública demostrable registra `120` promociones dentro de `6,646` productos con precio.

## Qué debe comunicar la interfaz

Lectura principal:

```text
Sitios web
   ↓
Web Scraping
   ↓
Validación
   ↓
Histórico
   ↓
Homologación
   ↓
Gate seguro de comparación
   ↓
Analítica / publicación
```

La tarjeta y el detalle usan explícitamente `Web Scraping`, `Python`, `Playwright` y `GitHub Actions` para que la habilidad sea visible.

La sección de cobertura productiva muestra todas las cadenas antes de cualquier resultado analítico. Una sección de comparación vacía debe explicar que el bloqueo es una decisión de calidad de datos, no ocultar la ausencia con una tabla dudosa.

## Capacidades demostradas

- **Web Scraping:** extracción automatizada desde sitios web y catálogos públicos.
- **Automatización:** workflows reproducibles y controlados.
- **Homologación conservadora:** identidad fuerte + reglas de coherencia, no marca/presentación como sustituto de identidad.
- **Histórico:** periodos comerciales aceptados y trazables.
- **Analítica:** mejores precios, canastas, variabilidad y cambios sólo sobre universo comparable.
- **Publicación BI:** JSON/CSV derivados sin secretos y con denominadores explícitos.

## Reglas de comunicación

1. Mostrar primero problema, evidencia y valor; dejar almacenamiento al final.
2. Decir `Web Scraping` explícitamente cuando esté respaldado.
3. Enlazar fuente, evidencia y código.
4. Mostrar todas las cadenas con datos aceptados en cobertura.
5. No afirmar equivalencia cross-source por marca + presentación.
6. No mostrar `best_price` para grupos `review_required` o `not_comparable`.
7. Un universo comparable vacío no tiene supermercado ganador.
8. Reconocer empates reales como empates, no forzar un único ganador visual.
9. No presentar productos seleccionados como canasta básica oficial.
10. No presentar precios históricos como tiempo real.
11. No cargar dataset productivo completo, secretos, cookies, tokens o RAW sensible en el navegador.
12. No presentar funcionalidades futuras como terminadas.
13. Toda cifra nueva debe provenir de una ejecución aceptada e integrada; un PR abierto o una captura rechazada no actualiza el estado público.

## Power BI

La implementación reproducible se documenta en [`BI-IMPLEMENTATION-GUIDE.md`](BI-IMPLEMENTATION-GUIDE.md) y los activos versionables viven en [`../powerbi/`](../powerbi/).

Power BI consume datos que ya pasaron el gate. DAX/Power Query no deben convertirse en una segunda implementación del matching.

## Actualización coordinada

Cuando cambie una cifra, evidencia o comparación pública, revisar conjuntamente:

- `docs/PROJECT_STATE.md`;
- `portfolio/scraping-proof.json`;
- `portfolio/sample-data.json`;
- `portfolio/precios-portfolio.js` y adaptadores de estado;
- este documento;
- README del proyecto;
- README raíz cuando cambie el alcance público.

No se actualiza una cifra pública hasta que la ejecución correspondiente sea terminal, aceptada y comprobada.