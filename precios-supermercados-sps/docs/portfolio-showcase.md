# Presentación del proyecto en el portafolio

Este documento define qué información de `precios-supermercados-sps` se muestra públicamente, de dónde sale y qué límites de interpretación deben respetarse.

## Prioridad de presentación

Desde el 4 de septiembre de 2026, **Precios de Supermercados** es el proyecto principal del portafolio y debe comunicar explícitamente la capacidad de **Web Scraping**. **Mundial 2026** permanece como segundo proyecto independiente.

Orden público:

1. Precios de Supermercados — Web Scraping, automatización e inteligencia de precios.
2. Mundial 2026.

## Cifras públicas verificadas

El portafolio debe reflejar el estado productivo vigente documentado en `PROJECT_STATE.md`.

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

La interfaz pública debe mostrar las seis cadenas. Una comparación de productos entre sólo algunas cadenas **no debe confundirse con la cobertura total**.

### Derivación del corte vigente

El corte público anterior documentaba 5 fuentes, 9 ubicaciones, 47,470 productos y 90,876 periodos históricos. El cierre productivo de Paiz agregó una sexta cadena, dos contextos demostrados y 9,299 identidades Paiz únicas, con 8,868 y 8,571 periodos actuales respectivamente.

```text
47,470 + 9,299 = 56,769 productos
90,876 + 8,868 + 8,571 = 108,315 periodos históricos
5 + 1 = 6 supermercados
9 + 2 = 11 ubicaciones
```

Fuentes: [`PROJECT_STATE.md`](PROJECT_STATE.md), [`../reports/paiz/2026-09-04-full/README.md`](../reports/paiz/2026-09-04-full/README.md) y [`../reports/comisariato-los-andes/2026-09-04-full/README.md`](../reports/comisariato-los-andes/2026-09-04-full/README.md).

## Extracción web comprobable

La interfaz mantiene una prueba pública concreta de que el proyecto obtiene datos desde una web real.

Captura aceptada de **Comisariato Los Andes**:

- Sitio público: <https://comisariatolosandes.com/>.
- Ciudad: San Pedro Sula.
- Captura: `2026-09-04T01:44:35.172709Z`.
- Productos con precio: `6,646`.
- Promociones detectadas: `120`.
- Artifact de GitHub Actions: `9920279680`.
- Snapshot SHA-256: `a1fe77e3c3132c96c01f7cd792084d47ae25fbb09e3eb69fb67b230d5f09f9fc`.
- Evidencia versionada: [`../reports/comisariato-los-andes/2026-09-04-full/`](../reports/comisariato-los-andes/2026-09-04-full/README.md).
- Metadatos públicos reducidos: [`../portfolio/scraping-proof.json`](../portfolio/scraping-proof.json).

La página enlaza tres niveles de comprobación:

1. página web de origen;
2. evidencia aceptada dentro del repositorio;
3. código de extracción dentro de `src/precios_supermercados/`.

No se publican credenciales, cookies, IDs internos ni el dataset productivo completo.

## Comparación pública de 10 productos

La tabla de precios presenta **10 productos representativos de consumo básico** entre **Comisariato Los Andes** y **Supermercados Colonial**.

Esta tabla **no representa toda la cobertura del proyecto**. La cobertura total ya incluye seis cadenas; aquí sólo se muestran dos porque estos 10 productos cuentan con una equivalencia curada y comprobada bajo la regla:

> misma marca + misma presentación/cantidad.

No se completan columnas para Walmart, PriceSmart, La Colonia o Paiz con coincidencias aproximadas. Hasta que exista matching cross-source validado para esos productos, dejar esas cadenas fuera de la tabla de precios es más correcto que inventar equivalencias.

La selección **no se presenta como la canasta básica oficial de Honduras**. Su propósito es demostrar una comparación comprensible usando productos cotidianos.

La interfaz ya no necesita una columna duplicada de “Mejor precio”. La lectura se resuelve directamente sobre las celdas de precio:

- **verde**: mejor precio de la fila;
- **amarillo**: precio intermedio cuando existan tres o más precios comparables;
- **rojo**: precio más alto de la fila.

El color no es la única señal: cada celda también recibe una etiqueta accesible con su clasificación y la tabla incluye una leyenda textual.

| Producto | Marca | Presentación | Ciudad | Comisariato Los Andes | Supermercados Colonial |
| --- | --- | --- | --- | ---: | ---: |
| Arroz blanco | Progreso | 1 lb / 454 g | San Pedro Sula | L 16.90 | L 15.79 |
| Huevos | Rica Yema | 15 und | San Pedro Sula | L 61.85 | L 60.79 |
| Harina de maíz | Maseca | 4.5 lb | San Pedro Sula | L 93.50 | L 85.99 |
| Harina de trigo | Gold Star | 5 lb | San Pedro Sula | L 74.50 | L 64.99 |
| Frijoles rojos volteados | La Chula | 48 oz | San Pedro Sula | L 75.50 | L 63.39 |
| Pierna muslo de pollo | Norteño | 1 lb | San Pedro Sula | L 32.90 | L 34.59 |
| Mantequilla crema | Leyde | 1 lb | San Pedro Sula | L 50.50 | L 35.29 |
| Avena mosh | Quaker | 600 g | San Pedro Sula | L 55.90 | L 49.49 |
| Pan molde | Monarca | 540 g | San Pedro Sula | L 61.50 | L 58.99 |
| Café molido | Passion | 1 lb | San Pedro Sula | L 299.50 | L 215.99 |

La versión estructurada se mantiene en [`../portfolio/sample-data.json`](../portfolio/sample-data.json).

### Procedencia de la comparación

**Comisariato Los Andes**

Los precios provienen del snapshot aceptado del proyecto capturado el 4 de septiembre de 2026 a las 01:44 UTC.

**Supermercados Colonial**

Los precios de esta muestra fueron verificados el 4 de septiembre de 2026 contra su catálogo web público oficial en <https://supercolonial.com/>. Esta comprobación pública no se presenta como parte del mismo snapshot de Los Andes ni como una captura productiva conjunta.

Los precios pueden cambiar después del corte. La tabla es evidencia de comparación y presentación del proyecto, no un servicio de precio en tiempo real.

## Qué debe comunicar la interfaz

La lectura principal debe ser:

```text
Sitios web
   ↓
Web Scraping
   ↓
Validación
   ↓
Histórico
   ↓
Análisis
```

La tarjeta y el detalle deben usar explícitamente `Web Scraping`, `Python`, `Playwright` y `GitHub Actions` para que la habilidad no dependa de una inferencia del visitante.

La sección “Cobertura productiva actual” debe mostrar las seis cadenas productivas y sus ubicaciones aceptadas antes de presentar la muestra de precios entre dos supermercados.

La sección “Qué demuestra este proyecto” traduce la implementación a cuatro capacidades contratables:

- Web Scraping.
- Automatización.
- Homologación de productos.
- Análisis histórico.

## Hallazgos públicos respaldados

Además de la muestra cross-source curada, pueden comunicarse estos hallazgos ya respaldados por evidencia del proyecto:

- `255` diferencias comerciales entre dos tiendas/contextos de una misma fuente sobre `12,042` artículos comparables.
- `115` artículos con diferencia de precio actual entre dos clubes de otra fuente, sobre `5,129` con precio en ambos.
- `120` promociones verificadas en la captura aceptada con `6,646` productos con precio.

## Reglas de comunicación

1. Mostrar primero el problema, la evidencia y el valor; dejar detalles de almacenamiento al final.
2. Decir `Web Scraping` explícitamente cuando la capacidad esté respaldada.
3. Enlazar la fuente web, la evidencia y el código para que otra persona pueda comprobarlo.
4. Mostrar todas las cadenas con datos aceptados en la sección de cobertura.
5. Mostrar marca y presentación en comparaciones cross-source.
6. No llenar una comparación con coincidencias de producto no verificadas.
7. Resaltar el ranking de precios directamente en las celdas y mantener una leyenda textual accesible.
8. No presentar la selección de 10 productos como canasta básica oficial.
9. No presentar precios históricos como tiempo real.
10. No cargar el dataset productivo completo en el navegador.
11. No mostrar secretos, cookies, tokens, IDs internos ni artefactos RAW completos en la interfaz.
12. No presentar funcionalidades futuras como terminadas.

## Actualización

Cuando cambie una cifra, evidencia o comparación pública, deben revisarse conjuntamente:

- `docs/PROJECT_STATE.md`.
- `portfolio/scraping-proof.json`.
- `portfolio/sample-data.json`.
- `portfolio/precios-portfolio.js` y cualquier adaptador de estado público asociado.
- este documento.
- el README del proyecto.
- el README raíz cuando cambie el alcance público.

No se actualiza una cifra pública a partir de un PR abierto, una captura rechazada o evidencia no integrada en `main`.