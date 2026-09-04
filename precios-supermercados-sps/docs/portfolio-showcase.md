# Presentación del proyecto en el portafolio

Este documento define qué información del proyecto `precios-supermercados-sps` puede mostrarse públicamente en el portafolio, de dónde sale y cómo se mantiene verificable.

## Prioridad de presentación

Desde el corte del 4 de septiembre de 2026, **Precios de Supermercados** es el proyecto principal de la sección `Proyectos` del portafolio. **Mundial 2026** permanece publicado como segundo proyecto independiente.

La interfaz debe dejar clara la separación entre ambos proyectos. El registro dinámico los presenta en este orden:

1. Precios de Supermercados.
2. Mundial 2026.

## Cifras públicas verificadas

La presentación utiliza estas cifras:

| Métrica | Valor exacto de soporte | Valor mostrado |
| --- | ---: | ---: |
| Fuentes integradas | 5 | 5 |
| Ubicaciones monitoreadas | 9 | 9 |
| Productos registrados | 47,470 | 47K+ |
| Periodos históricos de precio | 90,876 | 90K+ |
| Ciudades con cobertura integrada | 2 | 2 |

### Derivación

El estado productivo verificado del 2 de septiembre de 2026 documenta:

- 4 supermercados.
- 8 ubicaciones.
- 40,824 productos.
- 84,230 periodos históricos.

Fuente: [`PROJECT_STATE.md`](PROJECT_STATE.md), sección `Estado productivo verificado — 2026-09-02`.

La integración aceptada del 4 de septiembre de 2026 agrega:

- 1 fuente.
- 1 ubicación en San Pedro Sula.
- 6,646 productos únicos con precio.
- 6,646 periodos históricos abiertos en la carga inicial.
- 120 promociones verificadas.

Fuente: [`../reports/comisariato-los-andes/2026-09-04-full/README.md`](../reports/comisariato-los-andes/2026-09-04-full/README.md) y [`../reports/comisariato-los-andes/2026-09-04-full/evidence.json`](../reports/comisariato-los-andes/2026-09-04-full/evidence.json).

Por lo tanto:

```text
40,824 + 6,646 = 47,470 productos
84,230 + 6,646 = 90,876 periodos históricos
4 + 1 = 5 fuentes
8 + 1 = 9 ubicaciones
```

La interfaz redondea `47,470` a `47K+` y `90,876` a `90K+` para comunicar escala sin aparentar una precisión que pueda quedar obsoleta en una tarjeta estática.

## Muestra real publicada

La tabla visible en el portafolio usa datos reales del snapshot aceptado el **4 de septiembre de 2026 a las 01:44:35 UTC**, correspondiente a una fuente pública verificada en San Pedro Sula.

Metadatos de procedencia:

- Artifact de captura: `9920279680`.
- Snapshot SHA-256: `a1fe77e3c3132c96c01f7cd792084d47ae25fbb09e3eb69fb67b230d5f09f9fc`.
- Productos reportados y reconciliados: `6,646`.
- Productos con precio: `6,646`.
- Promociones verificadas: `120`.

La selección pública se versiona en [`../portfolio/sample-data.json`](../portfolio/sample-data.json).

| Producto fuente | Ciudad | Precio actual | Precio regular | Promoción | Disponibilidad pública |
| --- | --- | ---: | ---: | --- | --- |
| Rica yema huevos 15 unds | San Pedro Sula | L 61.85 | L 88.50 | Sí | No confirmada |
| Arroz progreso grano largo 5 lb | San Pedro Sula | L 84.50 | — | No | No confirmada |
| Nestle agua purificada 0.5 ltr | San Pedro Sula | L 8.95 | — | No | No confirmada |

Los tres nombres y precios proceden directamente del snapshot. El portafolio no sustituye el nombre del producto por un `SKU` ni muestra IDs internos porque esos campos no ayudan a una persona que sólo quiere entender el resultado.

La columna `Ubicación` tampoco se presenta en esta muestra; `Ciudad` es suficiente para el objetivo explicativo de la tabla.

## Disponibilidad

En la fuente utilizada para la muestra, la semántica de disponibilidad no quedó demostrada de forma fiable. Por eso el dato se presenta en lenguaje simple como **“No confirmada”** / **“Not confirmed”** y nunca como disponible o agotado por inferencia.

## Hallazgos públicos

La presentación puede comunicar estos hallazgos porque están respaldados por evidencia reproducible:

- `255` diferencias comerciales entre dos tiendas/contextos de una misma fuente sobre `12,042` artículos comparables.
- `115` artículos con diferencia de precio actual entre dos clubes de otra fuente, sobre `5,129` con precio en ambos.
- `120` promociones verificadas en la captura del 4 de septiembre de 2026 de una fuente de San Pedro Sula con `6,646` productos con precio.

En el texto público se usa **“artículos”** o **“productos”** en lugar de `SKU` cuando el término técnico no es necesario para entender el hallazgo.

No se afirma equivalencia entre cadenas distintas mientras el matching cross-source no esté demostrado.

## Decisiones de comunicación

La presentación pública sigue estas reglas:

1. Explicar primero el problema y el valor; dejar la tecnología al final.
2. Usar lenguaje entendible para una persona no técnica.
3. Mostrar fecha de la muestra real para no presentarla como precio en tiempo real.
4. No cargar el dataset productivo completo en el navegador.
5. No mostrar secretos, cookies, tokens, artefactos RAW completos ni identificadores internos en la interfaz.
6. No presentar funcionalidades futuras como si ya estuvieran terminadas.
7. El bloque “Calidad antes que cobertura” se retiró del portafolio porque era una decisión interna válida pero no aportaba suficiente valor a la explicación pública.

## Actualización

Cuando un nuevo estado productivo sea aceptado y cambien las cifras públicas o exista una muestra más reciente apropiada para portafolio, deben revisarse conjuntamente:

- `portfolio/sample-data.json`.
- `portfolio/precios-portfolio.js`.
- este documento.
- el README del proyecto si cambian cifras de presentación.
- el README raíz si cambia el orden o el alcance público de los proyectos.

No se actualiza una cifra pública a partir de un PR abierto, una captura rechazada o evidencia no integrada en `main`.
