# Estructura del repositorio

## Objetivo

Mantener el portafolio preparado para crecer sin mezclar la página pública con el código técnico de cada proyecto.

## Decisión de arquitectura

`Portafolio` funciona como sitio central de presentación. Los proyectos de datos, automatización o dashboards deben utilizar repositorios independientes.

El sitio puede conservar módulos visuales de cada proyecto, pero no sus pipelines completos, datasets, notebooks ni dependencias.

## Estructura del sitio

```text
Portafolio/
├── index.html
├── script.js
├── css/
│   ├── base.css
│   ├── detail.css
│   ├── projects.css
│   ├── responsive.css
│   └── projects/
│       └── <slug>.css
├── js/
│   ├── main.js
│   └── projects/
│       ├── registry.js
│       └── <slug>.js
├── assets/
│   └── projects/
│       └── <slug>/
├── docs/
├── PROJECT_TEMPLATE.md
├── README.md
└── .gitignore
```

## Qué permanece en la raíz

- `index.html`: página publicada por GitHub Pages.
- `script.js`: cargador pequeño de la aplicación principal.
- `README.md`: explicación general del portafolio.
- `PROJECT_TEMPLATE.md`: guía reutilizable.
- `.gitignore`: exclusiones generales.

No deben colocarse en la raíz archivos como `project-algo.js`, `dashboard-final.pbix`, notebooks, exportaciones, scripts de extracción o datasets.

## Código del sitio

### JavaScript general

```text
js/main.js
```

Administra navegación, animaciones, progreso y carga de los módulos de proyectos.

### Registro de proyectos

```text
js/projects/registry.js
```

Evita que un módulo reemplace o elimine las tarjetas de los demás.

### Módulo visual de cada proyecto

```text
js/projects/<slug>.js
css/projects/<slug>.css
```

El módulo contiene solamente:

- Tarjeta del proyecto.
- Vista detallada.
- Enlaces al repositorio y demostración.
- Eventos propios de la presentación.

## Recursos visuales

```text
assets/projects/<slug>/
```

Ejemplo:

```text
assets/projects/precios-supermercados-sps/
├── portada.webp
├── dashboard-01.webp
└── arquitectura.svg
```

## Repositorio técnico independiente

Cada proyecto debe organizarse fuera de `Portafolio`:

```text
<slug>/
├── .github/workflows/
├── config/
├── data/
│   ├── samples/
│   └── schemas/
├── docs/
├── src/
├── tests/
├── README.md
├── requirements.txt
└── .gitignore
```

Se crean únicamente las carpetas que el proyecto realmente necesita.

## Convención de nombres

Usar minúsculas y guiones:

```text
mundial-2026-analytics
precios-supermercados-sps
automatizacion-reportes
```

Evitar:

```text
Proyecto1
prueba-final
version-2
carpeta-juan
```

## Flujo para agregar un proyecto

1. Crear su repositorio independiente.
2. Completar su README y estructura técnica.
3. Publicar una demostración o capturas verificables.
4. Guardar las imágenes del portafolio en `assets/projects/<slug>/`.
5. Crear `js/projects/<slug>.js`.
6. Crear `css/projects/<slug>.css`.
7. Registrar ambos recursos en `js/main.js`.
8. Verificar enlaces, responsive y accesibilidad.

## Estado transitorio del Mundial

`mundial-2026-predicciones/` todavía permanece en este repositorio para evitar pérdida de código o ruptura de rutas existentes. Su migración debe realizarse hacia `mundial-2026-analytics` antes de eliminar la carpeta heredada.

## Reglas

- No guardar credenciales, tokens ni llaves privadas.
- No mezclar código técnico de varios proyectos.
- No subir archivos temporales o duplicados.
- No utilizar nombres ambiguos.
- Mantener un README completo por proyecto.
- Eliminar ramas temporales después de fusionarlas.
