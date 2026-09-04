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
├── precios-supermercados-sps/  # Web scraping, monitoreo e inteligencia de precios
├── mundial-2026/               # Proyecto Mundial 2026 completo
├── index.html                  # Página principal de GitHub Pages
├── script.js                   # Cargador de js/main.js
├── PROJECT_TEMPLATE.md         # Plantilla para proyectos futuros
├── README.md
└── .gitignore
```

La única excepción a la regla de encapsulación es `.github/workflows/`: GitHub solo reconoce workflows ejecutables desde esa ubicación. Cada archivo debe indicar claramente el proyecto al que pertenece y trabajar dentro de su carpeta.

## Proyectos publicados

### 1. Monitoreo automatizado de precios — Web Scraping

Proyecto principal del portafolio. Obtiene precios y promociones desde sitios web públicos de supermercados, valida las capturas, estructura los datos y conserva su histórico para análisis.

Estado público verificado al **4 de septiembre de 2026**:

- **5 fuentes web integradas**.
- **9 ubicaciones monitoreadas**.
- **47K+ productos registrados**.
- **90K+ registros históricos de precio**.
- Cobertura actual en **San Pedro Sula y Tegucigalpa**.
- Evidencia pública de una captura aceptada con **6,646 productos con precio** y **120 promociones**.
- Comparación pública de **10 productos representativos de consumo básico**, usando misma marca y presentación entre Comisariato Los Andes y Supermercados Colonial.

El detalle del sitio enlaza la **página de origen**, la **evidencia versionada en GitHub** y el **código de extracción** para que la capacidad de web scraping sea comprobable y no sólo declarativa.

**Carpeta completa:** [`precios-supermercados-sps/`](precios-supermercados-sps/)

**Procedencia de la presentación:** [`precios-supermercados-sps/docs/portfolio-showcase.md`](precios-supermercados-sps/docs/portfolio-showcase.md)

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
