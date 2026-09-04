# Portafolio de datos y automatización

Portafolio profesional de **Juan Carlos Hernández Ramos**, enfocado en reportes, dashboards, preparación de datos, automatización de procesos y proyectos de datos aplicados a problemas reales.

**Sitio publicado:** https://jchernand3z19.github.io/Portafolio/

El sitio funciona en **español e inglés**, con español como idioma predeterminado.

## Organización del repositorio

`Portafolio` es el único repositorio público y funciona como un monorepositorio: cada proyecto completo vive en una carpeta propia en la raíz.

```text
Portafolio/
├── .github/workflows/          # Entradas de GitHub Actions
├── css/                        # Estilos compartidos del sitio
├── js/                         # Lógica compartida, i18n y registro de proyectos
├── docs/                       # Reglas generales del repositorio
├── precios-supermercados-sps/  # Monitoreo e inteligencia de precios
├── mundial-2026/               # Proyecto Mundial 2026 completo
├── index.html                  # Página principal de GitHub Pages
├── script.js                   # Cargador de js/main.js
├── PROJECT_TEMPLATE.md         # Plantilla para proyectos futuros
├── README.md
└── .gitignore
```

La única excepción a la regla de encapsulación es `.github/workflows/`: GitHub solo reconoce workflows ejecutables desde esa ubicación. Cada archivo debe indicar claramente el proyecto al que pertenece y trabajar dentro de su carpeta.

## Proyectos publicados

### 1. Precios de Supermercados: monitoreo e inteligencia de precios

Proyecto principal del portafolio. Reúne precios públicos de supermercados, los valida, los estructura y conserva su histórico para detectar cambios, promociones y diferencias cuando la comparación es válida.

Estado público verificado al **4 de septiembre de 2026**:

- **5 fuentes integradas**.
- **9 ubicaciones monitoreadas**.
- **47K+ productos registrados**.
- **90K+ registros históricos de precio**.
- Cobertura actual en **San Pedro Sula y Tegucigalpa**.
- El portafolio muestra una **muestra real y verificable** proveniente de un snapshot aceptado del 4 de septiembre de 2026; no carga el dataset productivo completo en el navegador.

**Carpeta completa:** [`precios-supermercados-sps/`](precios-supermercados-sps/)

La procedencia exacta de la muestra pública y las cifras utilizadas por la presentación se documenta en [`precios-supermercados-sps/docs/portfolio-showcase.md`](precios-supermercados-sps/docs/portfolio-showcase.md).

### 2. Mundial 2026: análisis histórico y predicción

Proyecto de datos que integra información histórica, calendario, ranking y resultados recientes para generar análisis, predicciones y una aplicación web interactiva.

- **Carpeta completa:** [`mundial-2026/`](mundial-2026/)
- **Dashboard:** https://script.google.com/macros/s/AKfycbzE26z7tcEbnwLPKSLLW8H_rK7UqwKV17rV8YBJVT4lB4slY0qorsf8cL4cnsys5ShGhw/exec
- **Tecnologías:** Python, Google Sheets, Google Apps Script, Chart.js y GitHub Actions.

## Regla para proyectos futuros

Cada proyecto nuevo debe crearse como otra carpeta al mismo nivel:

```text
Portafolio/
├── precios-supermercados-sps/
├── mundial-2026/
├── automatizacion-reportes/
└── nombre-del-proyecto/
```

Dentro de su carpeta deben quedar el README, código, dependencias, documentación, pruebas, datos publicables y los recursos visuales utilizados para presentarlo en el portafolio.

No se deben crear tarjetas ficticias ni carpetas vacías. Solo se publica un proyecto cuando exista contenido real y la presentación pública pueda vincularse con evidencia verificable del repositorio.

Consulta [`PROJECT_TEMPLATE.md`](PROJECT_TEMPLATE.md) y [`docs/ESTRUCTURA_REPOSITORIO.md`](docs/ESTRUCTURA_REPOSITORIO.md).
