# Portafolio de datos y automatización

Portafolio profesional de **Juan Carlos Hernández Ramos**, enfocado en reportes, dashboards, preparación de datos y automatización de procesos.

**Sitio publicado:** https://jchernand3z19.github.io/Portafolio/

## Propósito de este repositorio

Este repositorio contiene únicamente la presentación web del portafolio y los recursos necesarios para publicarla con GitHub Pages.

Cada proyecto técnico de tamaño relevante debe vivir en un repositorio independiente. El portafolio solamente conserva su tarjeta, descripción, capturas y enlaces.

> Estado transitorio: el código técnico de Mundial 2026 todavía se encuentra en `mundial-2026-predicciones/`. Se mantendrá allí hasta completar su migración a un repositorio independiente, sin eliminar historial ni romper el dashboard publicado.

## Estructura

```text
Portafolio/
├── .github/workflows/        # Publicación y automatizaciones todavía vinculadas al sitio
├── assets/                   # Imágenes y recursos públicos
├── css/
│   ├── base.css
│   ├── detail.css
│   ├── projects.css
│   ├── responsive.css
│   └── projects/
│       └── mundial.css       # Estilos exclusivos del proyecto Mundial
├── js/
│   ├── main.js               # Comportamiento general y carga de módulos
│   └── projects/
│       ├── registry.js       # Registro común de proyectos
│       └── mundial.js        # Tarjeta y vista detallada del Mundial
├── docs/                     # Convenciones del portafolio
├── mundial-2026-predicciones/# Código técnico heredado, pendiente de extracción
├── index.html                # Entrada de GitHub Pages
├── script.js                 # Cargador mínimo de js/main.js
├── PROJECT_TEMPLATE.md       # Plantilla para publicar proyectos nuevos
├── README.md
└── .gitignore
```

## Repositorios de proyectos

La organización recomendada del perfil es:

```text
Jchernand3z19/
├── Portafolio
├── mundial-2026-analytics
├── precios-supermercados-sps
├── automatizacion-reportes
└── dashboard-comercial-powerbi
```

No se debe agregar el código de un proyecto nuevo dentro de `mundial-2026-predicciones/` ni colocar archivos específicos en la raíz del portafolio.

## Cómo publicar un proyecto nuevo

1. Crear un repositorio independiente con nombre descriptivo en minúsculas y guiones.
2. Documentar problema, fuentes, proceso, arquitectura, resultados y ejecución.
3. Guardar en este repositorio solamente sus imágenes dentro de `assets/projects/<slug>/`.
4. Crear su módulo visual en `js/projects/<slug>.js`.
5. Crear sus estilos en `css/projects/<slug>.css`.
6. Agregar ambos recursos a las listas de `js/main.js`.
7. Enlazar la tarjeta al repositorio técnico y a la demostración publicada.

Consulta [`PROJECT_TEMPLATE.md`](PROJECT_TEMPLATE.md) y [`docs/ESTRUCTURA_REPOSITORIO.md`](docs/ESTRUCTURA_REPOSITORIO.md).

## Proyecto publicado

### Mundial 2026: análisis histórico y predicción

Solución de datos que integra información histórica, calendario, ranking y resultados recientes para generar análisis, predicciones y una aplicación web interactiva.

- **Tecnologías:** Python, Google Sheets, Google Apps Script, Chart.js y GitHub Actions.
- **Código técnico actual:** [`mundial-2026-predicciones/`](mundial-2026-predicciones/)
- **Dashboard:** https://script.google.com/macros/s/AKfycbzE26z7tcEbnwLPKSLLW8H_rK7UqwKV17rV8YBJVT4lB4slY0qorsf8cL4cnsys5ShGhw/exec

## Principios

- La raíz permanece limpia y contiene solo entradas generales.
- El CSS y JavaScript específico se agrupan por proyecto.
- Los proyectos técnicos no se mezclan entre sí.
- No se publican credenciales ni datos privados.
- Cada proyecto debe ser entendible y ejecutable desde su propio README.
