# Portafolio de datos y automatización

Portafolio profesional de **Juan Carlos Hernández Ramos**, enfocado en reportes, dashboards, preparación de datos y automatización de procesos.

**Portafolio publicado:** https://jchernand3z19.github.io/Portafolio/

## Proyecto publicado

### Mundial 2026: análisis histórico y predicción

Solución de datos de extremo a extremo que integra información histórica, calendario, ranking y resultados recientes para generar análisis, predicciones y una experiencia web interactiva.

- **Análisis:** Python y modelos estadísticos.
- **Datos:** Google Sheets y estructuras normalizadas.
- **Automatización:** GitHub Actions.
- **Aplicación:** Google Apps Script y Chart.js.
- **Código técnico:** [`mundial-2026-predicciones/`](mundial-2026-predicciones/)
- **Dashboard:** [abrir experiencia interactiva](https://script.google.com/macros/s/AKfycbzE26z7tcEbnwLPKSLLW8H_rK7UqwKV17rV8YBJVT4lB4slY0qorsf8cL4cnsys5ShGhw/exec)

## Cómo está organizado el repositorio

El repositorio reúne dos capas diferentes:

1. **Sitio del portafolio:** vive en la raíz porque se publica con GitHub Pages.
2. **Proyectos técnicos:** cada proyecto utiliza una carpeta independiente, al mismo nivel que los demás proyectos.

```text
Portafolio/
├── index.html                       # Página principal publicada
├── css/                             # Estilos generales del sitio
├── script.js                        # Navegación y carga de módulos
├── project-registry.js              # Registro común de proyectos
├── project-mundial.js               # Presentación del proyecto Mundial
├── project-mundial.css              # Estilos del proyecto Mundial
├── assets/                          # Imágenes y recursos publicados
├── mundial-2026-predicciones/       # Código técnico del primer proyecto
├── docs/                            # Convenciones y documentación
├── PROJECT_TEMPLATE.md              # Plantilla para nuevos proyectos
└── .github/workflows/               # Automatizaciones independientes
```

La explicación completa se encuentra en [`docs/ESTRUCTURA_REPOSITORIO.md`](docs/ESTRUCTURA_REPOSITORIO.md).

## Cómo agregar otro proyecto

Un proyecto nuevo **no debe crearse dentro de `mundial-2026-predicciones/`**. Debe ser una carpeta hermana con un nombre claro y estable:

```text
Portafolio/
├── mundial-2026-predicciones/
└── precios-supermercados-sps/
```

Cada proyecto debe tener como mínimo:

- `README.md` con problema, objetivo, proceso, tecnologías y resultados.
- Código separado por responsabilidad.
- Dependencias reproducibles.
- Datos de ejemplo cuando sea posible, nunca información privada.
- Variables sensibles administradas mediante entorno o GitHub Secrets.
- Un módulo visual propio cuando se publique en el sitio.

La plantilla reutilizable está en [`PROJECT_TEMPLATE.md`](PROJECT_TEMPLATE.md).

## Arquitectura de la sección de proyectos

La página utiliza `project-registry.js` para registrar cada caso sin que un proyecto elimine o reemplace a los demás. `script.js` mantiene las listas de estilos y módulos que deben cargarse.

Para publicar un segundo proyecto se agrega su CSS y su JavaScript a estas listas:

```javascript
const projectStyles = [
  'project-mundial.css',
  'project-precios-supermercados.css'
];

const projectModules = [
  'project-mundial.js',
  'project-precios-supermercados.js'
];
```

El módulo nuevo registra su tarjeta y su vista detallada mediante:

```javascript
window.PortfolioProjects.register({
  id: 'precios-supermercados-sps',
  cardHtml,
  detailHtml,
  setup
});
```

## Principios del repositorio

- Mostrar únicamente proyectos reales y navegables.
- Mantener cada solución técnica aislada.
- No publicar credenciales, IDs privados ni datos sensibles.
- Documentar entradas, transformaciones, salidas y resultados.
- Conservar enlaces estables desde el portafolio hacia el código específico.
- Usar automatizaciones separadas por proyecto.

## Tecnologías representadas

Python, SQL, Power BI, Looker Studio, Google Sheets, Google Apps Script, Chart.js, Qlik Cloud, Oracle, BigQuery y GitHub Actions.
