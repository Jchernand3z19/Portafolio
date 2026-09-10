# Portafolio de datos y automatización

Portafolio profesional de **Juan Carlos Hernández Ramos**, enfocado en reportes, dashboards, preparación de datos, automatización de procesos y proyectos de datos aplicados a problemas reales.

**Sitio publicado:** https://jchernand3z19.github.io/Portafolio/

El sitio funciona en **español e inglés**, con español como idioma predeterminado.

## Organización del repositorio

`Portafolio` es un monorepositorio: cada proyecto completo vive en una carpeta propia de la raíz y `.github/workflows/` concentra las automatizaciones reconocidas por GitHub.

```text
Portafolio/
├── .github/workflows/
├── css/
├── js/
├── docs/
├── precios-supermercados-sps/  # Retail Price Intelligence / Compra Inteligente
├── pagos-whatsapp-residencial/ # proyecto PAGOS
├── mundial-2026/
├── index.html
├── script.js
├── PROJECT_TEMPLATE.md
└── README.md
```

## Monorepo Project Registry

El contrato operativo está en [`.github/project-scopes.yml`](.github/project-scopes.yml). El número o antigüedad de un PR no determina su proyecto; lo hacen el registry y las rutas modificadas.

La auditoría de workflows, outputs y secretos está en [`docs/MONOREPO-GOVERNANCE.md`](docs/MONOREPO-GOVERNANCE.md).

| Project ID | Project root | PR prefix | Branch prefix |
| --- | --- | --- | --- |
| RPI | `precios-supermercados-sps/` | `[RPI]` | `rpi/` |
| PAGOS | `pagos-whatsapp-residencial/` | `[PAGOS]` | `pagos/` |
| MUNDIAL | `mundial-2026/` | `[MUNDIAL]` | `mundial/` |
| SHARED | `/` (gobernanza e integraciones declaradas) | `[MONOREPO]` | `monorepo/` |

La infraestructura shared no permite mezclar features de project roots distintos.

# Proyectos publicados

## 1. Retail Price Intelligence — Compra Inteligente

Proyecto principal de inteligencia de precios. Captura catálogos públicos de supermercados, valida cada ejecución, conserva histórico, homologa productos de forma conservadora y publica productos de datos B2B/B2C.

### Compra Inteligente

La experiencia pública B2C permite navegar precios de **La Colonia, Supermercados Colonial, Walmart, PriceSmart y Comisariato Los Andes en SPS**, seleccionar ofertas exactas, construir `Mi Compra`, revisar historia de precios y exportar la lista.

El Consumer Catalog v3 publicado el **10 de septiembre de 2026** contiene como snapshot verificado:

- **44,042 filas visibles**;
- **46,680 ofertas fuente**;
- 2,638 filas comparables;
- 45,420 ofertas con resumen histórico;
- 484 particiones de máximo 250 filas.

La aplicación separa visibilidad de comparabilidad: mostrar un producto no significa afirmar que es equivalente a otro. El matching y las recomendaciones se autorizan en Python bajo una política fail-closed; la web no une productos por nombre, marca o presentación.

### Retail Price Intelligence B2B

El proyecto también genera `rpi-business-mart/v1`, con comparación actual, histórico, promociones, canastas, cobertura y freshness. Los activos reproducibles de Power BI están versionados dentro del proyecto.

### Cobertura operativa

El pipeline recurrente general integra **6 cadenas y 11 contextos productivos** en San Pedro Sula y Tegucigalpa: La Colonia, Supermercados Colonial, Walmart, PriceSmart, Comisariato Los Andes y Paiz.

El web scraping es una capacidad técnica demostrada de la plataforma, pero el producto final abarca adquisición, calidad, histórico, homologación, analítica, data marts, publicación y experiencia B2C.

**Proyecto:** [`precios-supermercados-sps/`](precios-supermercados-sps/)

**Estado vigente:** [`precios-supermercados-sps/docs/PROJECT_STATE.md`](precios-supermercados-sps/docs/PROJECT_STATE.md)

**Presentación pública:** [`precios-supermercados-sps/docs/portfolio-showcase.md`](precios-supermercados-sps/docs/portfolio-showcase.md)

**Metodología del comparador:** [`precios-supermercados-sps/docs/COMPARATOR-METHODOLOGY.md`](precios-supermercados-sps/docs/COMPARATOR-METHODOLOGY.md)

## 2. Mundial 2026: análisis histórico y predicción

Proyecto de datos que integra información histórica, calendario, ranking y resultados recientes para generar análisis, predicciones y una aplicación web interactiva.

- **Carpeta completa:** [`mundial-2026/`](mundial-2026/)
- **Dashboard:** https://script.google.com/macros/s/AKfycbzE26z7tcEbnwLPKSLLW8H_rK7UqwKV17rV8YBJVT4lB4slY0qorsf8cL4cnsys5ShGhw/exec
- **Tecnologías:** Python, Google Sheets, Google Apps Script, Chart.js y GitHub Actions.

## Regla para proyectos futuros

Cada proyecto nuevo debe crearse como otra carpeta al mismo nivel. Dentro de su root deben vivir README, código, dependencias, documentación, pruebas, datos publicables y recursos visuales propios.

No se crean tarjetas ficticias ni carpetas vacías. Un proyecto se publica cuando existe contenido real y la presentación pública puede vincularse con evidencia verificable.

Consultar [`PROJECT_TEMPLATE.md`](PROJECT_TEMPLATE.md) y [`docs/ESTRUCTURA_REPOSITORIO.md`](docs/ESTRUCTURA_REPOSITORIO.md).
