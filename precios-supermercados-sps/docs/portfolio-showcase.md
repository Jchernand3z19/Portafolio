# Presentación del proyecto en el portafolio

Este documento define qué información de `precios-supermercados-sps` se muestra públicamente, de dónde sale y qué límites de interpretación deben respetarse.

## Prioridad de presentación

Desde el 4 de septiembre de 2026, **Precios de Supermercados** es el proyecto principal del portafolio y debe comunicar explícitamente la capacidad de **Web Scraping**. **Mundial 2026** permanece como segundo proyecto independiente.

Orden público:

1. Precios de Supermercados — Web Scraping, automatización e inteligencia de precios.
2. Mundial 2026.

## Cifras públicas verificadas

| Métrica | Valor exacto de soporte | Valor mostrado |
| --- | ---: | ---: |
| Fuentes integradas | 5 | 5 |
| Ubicaciones monitoreadas | 9 | 9 |
| Productos registrados | 47,470 | 47K+ |
| Periodos históricos de precio | 90,876 | 90K+ |
| Ciudades con cobertura integrada | 2 | 2 |

### Derivación

El estado productivo verificado del 2 de septiembre de 2026 documenta 4 fuentes, 8 ubicaciones, 40,824 productos y 84,230 periodos históricos. La integración aceptada del 4 de septiembre agrega 1 fuente, 1 ubicación en San Pedro Sula, 6,646 productos con precio y 6,646 periodos iniciales.

```text
40,824 + 6,646 = 47,470 productos
84,230 + 6,646 = 90,876 periodos históricos
4 + 1 = 5 fuentes
8 + 1 = 9 ubicaciones
```

Fuentes: [`PROJECT_STATE.md`](PROJECT_STATE.md) y [`../reports/comisariato-los-andes/2026-09-04-full/README.md`](../reports/comisariato-los-andes/2026-09-04-full/README.md).

## Extracción web comprobable

La interfaz muestra una prueba pública concreta de que el proyecto obtiene datos desde una web real.

Captura aceptada de **Comisariato Los Andes**:

- Sitio público: <https://comisariatolosandes.com/>.
- Ciudad: San Pedro Sula.
- Captura: `2026-09-04T01:44:35.172709Z`.
- Productos con precio: `6,646`.
- Promociones detectadas: `120`.
- Artifact de GitHub Actions: `9920279680`.
- Snapshot SHA-256: `a1fe77e3c3132c96c01f7cd792084d47ae25fbb09e3eb69fb67b230d5f09f9fc`.
- Evidencia versionada: [`../reports/comisariato-los-andes/2026-09-04-full/`](../reports/comisariato-los-andes/2026-09-04-full/).
- Metadatos públicos reducidos: [`../portfolio/scraping-proof.json`](../portfolio/scraping-proof.json).

La página enlaza tres niveles de comprobación:

1. página web de origen;
2. evidencia aceptada dentro del repositorio;
3. código de extracción dentro de `src/precios_supermercados/`.

No se publican credenciales, cookies, IDs internos ni el dataset productivo completo.

## Comparación pública de 10 productos

La tabla del portafolio ya no usa tres filas aleatorias. Presenta **10 productos representativos de consumo básico** para explicar de forma inmediata qué valor tienen los datos.

La selección **no se presenta como la canasta básica oficial de Honduras**. Su propósito es demostrar una comparación comprensible usando productos cotidianos.

Regla obligatoria de matching para esta muestra:

> misma marca + misma presentación/cantidad.

No se comparan tamaños, marcas o variantes diferentes sólo porque el nombre se parezca.

| Producto | Marca | Presentación | Ciudad | Comisariato Los Andes | Supermercados Colonial | Mejor precio |
| --- | --- | --- | --- | ---: | ---: | ---: |
| Arroz blanco | Progreso | 1 lb / 454 g | San Pedro Sula | L 16.90 | L 15.79 | L 15.79 |
| Huevos | Rica Yema | 15 und | San Pedro Sula | L 61.85 | L 60.79 | L 60.79 |
| Harina de maíz | Maseca | 4.5 lb | San Pedro Sula | L 93.50 | L 85.99 | L 85.99 |
| Harina de trigo | Gold Star | 5 lb | San Pedro Sula | L 74.50 | L 64.99 | L 64.99 |
| Frijoles rojos volteados | La Chula | 48 oz | San Pedro Sula | L 75.50 | L 63.39 | L 63.39 |
| Pierna muslo de pollo | Norteño | 1 lb | San Pedro Sula | L 32.90 | L 34.59 | L 32.90 |
| Mantequilla crema | Leyde | 1 lb | San Pedro Sula | L 50.50 | L 35.29 | L 35.29 |
| Avena mosh | Quaker | 600 g | San Pedro Sula | L 55.90 | L 49.49 | L 49.49 |
| Pan molde | Monarca | 540 g | San Pedro Sula | L 61.50 | L 58.99 | L 58.99 |
| Café molido | Passion | 1 lb | San Pedro Sula | L 299.50 | L 215.99 | L 215.99 |

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
4. Mostrar marca y presentación en comparaciones cross-source.
5. No presentar la selección de 10 productos como canasta básica oficial.
6. No presentar precios históricos como tiempo real.
7. No cargar el dataset productivo completo en el navegador.
8. No mostrar secretos, cookies, tokens, IDs internos ni artefactos RAW completos en la interfaz.
9. No presentar funcionalidades futuras como terminadas.

## Actualización

Cuando cambie una cifra, evidencia o comparación pública, deben revisarse conjuntamente:

- `portfolio/scraping-proof.json`.
- `portfolio/sample-data.json`.
- `portfolio/precios-portfolio.js`.
- este documento.
- el README del proyecto.
- el README raíz cuando cambie el alcance público.

No se actualiza una cifra pública a partir de un PR abierto, una captura rechazada o evidencia no integrada en `main`.
