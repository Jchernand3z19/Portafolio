# Estructura del repositorio

## Objetivo

Mantener un único repositorio público y permitir que cada proyecto se revise sin mezclar sus archivos con los demás.

## Decisión de arquitectura

`Portafolio` es un monorepositorio. Cada proyecto completo se guarda en una carpeta principal de la raíz.

```text
Portafolio/
├── .github/workflows/
├── css/
├── js/
├── docs/
├── mundial-2026/
├── <proyecto-futuro>/
├── index.html
├── script.js
├── PROJECT_TEMPLATE.md
├── README.md
└── .gitignore
```

## Archivos compartidos

La raíz y las carpetas compartidas contienen solamente elementos utilizados por todo el sitio:

- `index.html`: página principal publicada con GitHub Pages.
- `script.js`: cargador mínimo de `js/main.js`.
- `js/main.js`: navegación, animaciones y carga de proyectos.
- `js/projects/registry.js`: registro común de tarjetas y vistas.
- `css/base.css`: base visual del sitio.
- `css/detail.css`: componentes compartidos de detalle.
- `css/projects.css`: tarjetas compartidas.
- `css/responsive.css`: reglas responsive generales.
- `docs/`: decisiones y reglas generales.

No se deben guardar en la raíz notebooks, datasets, capturas o scripts exclusivos de un proyecto.

## Carpeta de cada proyecto

La estructura se adapta al trabajo real:

```text
<slug-del-proyecto>/
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── portfolio/
│   ├── <slug>.js
│   ├── <slug>.css
│   └── assets/
├── config/
├── data/
├── dashboard/
├── docs/
├── notebooks/
├── reports/
├── scripts/
├── src/
└── tests/
```

Solo se crean carpetas con contenido real.

## Proyecto Mundial 2026

La organización actual es:

```text
mundial-2026/
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── portfolio/
│   ├── mundial-2026.js
│   ├── mundial-2026.css
│   └── assets/
│       ├── mundial-dashboard-preview.svg
│       └── dashboard/
├── dashboard/
│   └── apps-script/
├── scripts/
└── src/
```

Todos los recursos exclusivos que antes estaban en `assets/mundial/`, `assets/code/apps-script/`, `css/projects/mundial.css`, `js/projects/mundial.js` y `mundial-2026-predicciones/` quedan consolidados dentro de `mundial-2026/`.

## GitHub Actions

GitHub solo ejecuta workflows ubicados en `.github/workflows/`. Esta es la única excepción a la regla de que todo archivo específico permanezca dentro de la carpeta del proyecto.

Los nombres deben identificar el proyecto:

```text
.github/workflows/mundial-2026-prediccion-diaria.yml
.github/workflows/mundial-2026-prediccion-completa.yml
.github/workflows/mundial-2026-prediccion-viva.yml
```

Cada workflow debe usar:

```yaml
defaults:
  run:
    working-directory: mundial-2026
```

## Convenciones

- Carpetas y repositorios en minúsculas y guiones.
- Python en `snake_case.py`.
- Un README por proyecto.
- No publicar credenciales, tokens, cookies o datos privados.
- No crear proyectos ficticios ni carpetas vacías.
- Trabajar mediante rama y Pull Request para reorganizaciones importantes.

## Proceso para agregar un proyecto

1. Crear `<slug>/` en la raíz.
2. Agregar su README y estructura real.
3. Guardar sus archivos visuales en `<slug>/portfolio/`.
4. Registrar sus rutas en `js/main.js`.
5. Crear su workflow en `.github/workflows/` cuando sea necesario.
6. Verificar enlaces, consola, diseño responsive y seguridad.
7. Crear un Pull Request hacia `main`.
