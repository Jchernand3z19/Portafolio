# Plantilla para un proyecto nuevo

Cada proyecto nuevo se crea como una carpeta independiente en la raíz del repositorio `Portafolio`.

Usa un nombre en minúsculas, sin espacios y separado por guiones:

```text
nombre-del-proyecto/
```

## Estructura base

Crea únicamente las carpetas que tendrán contenido real.

```text
nombre-del-proyecto/
├── README.md
├── requirements.txt           # Cuando utilice Python
├── .env.example               # Cuando requiera variables de entorno
├── .gitignore                 # Reglas exclusivas, cuando sean necesarias
├── portfolio/
│   ├── nombre-del-proyecto.js
│   ├── nombre-del-proyecto.css
│   └── assets/
├── config/
├── data/
│   ├── samples/
│   └── README.md
├── dashboard/
├── docs/
├── notebooks/
├── reports/
├── scripts/
├── src/
└── tests/
```

No todas las carpetas son obligatorias. Un proyecto de Power BI, por ejemplo, puede no necesitar `src/`; un análisis pequeño puede no necesitar `dashboard/`.

## Contenido mínimo del README

```markdown
# Nombre del proyecto

Descripción clara de una o dos líneas.

## Estado

Planificado / En desarrollo / Publicado / Mantenimiento / Archivado.

## Problema

Situación concreta que se busca resolver.

## Objetivo

Resultado esperado.

## Alcance

Qué incluye y qué no incluye.

## Fuentes de datos

Origen, condiciones de uso y restricciones.

## Arquitectura y proceso

Extracción, limpieza, transformación, validación, almacenamiento y publicación.

## Tecnologías

Herramientas realmente utilizadas.

## Estructura del proyecto

Árbol de carpetas y función de cada componente.

## Instalación y ejecución

Pasos reproducibles.

## Pruebas

Cómo validar el funcionamiento.

## Resultados

Entregables o resultados reales.

## Seguridad y privacidad

Datos y credenciales excluidos.

## Limitaciones y próximos pasos

Pendientes reales.
```

## Integración con la página principal

La presentación del proyecto debe permanecer dentro de su propia carpeta:

```text
nombre-del-proyecto/portfolio/nombre-del-proyecto.js
nombre-del-proyecto/portfolio/nombre-del-proyecto.css
nombre-del-proyecto/portfolio/assets/
```

Después se agregan el CSS y el JavaScript en `js/main.js`:

```javascript
const projectStyles = [
  'mundial-2026/portfolio/mundial-2026.css',
  'nombre-del-proyecto/portfolio/nombre-del-proyecto.css'
];

const projectModules = [
  'mundial-2026/portfolio/mundial-2026.js',
  'nombre-del-proyecto/portfolio/nombre-del-proyecto.js'
];
```

El módulo debe registrarse con `window.PortfolioProjects.register(...)` y no debe borrar las tarjetas de los demás proyectos.

## GitHub Actions

Los workflows ejecutables deben estar en:

```text
.github/workflows/
```

Usa un nombre que identifique el proyecto:

```text
.github/workflows/nombre-del-proyecto-validacion.yml
```

El workflow debe apuntar a la carpeta correspondiente mediante `working-directory` y `PYTHONPATH` cuando aplique.

## Checklist

- [ ] Carpeta principal en la raíz.
- [ ] Nombre en minúsculas y guiones.
- [ ] README completo.
- [ ] Código y recursos exclusivos dentro del proyecto.
- [ ] Datos privados excluidos.
- [ ] `.env.example` sin valores reales.
- [ ] Dependencias definidas.
- [ ] Pruebas de funciones críticas.
- [ ] Capturas optimizadas.
- [ ] Tarjeta y detalle responsive.
- [ ] Workflow identificado y limitado al proyecto.
- [ ] Sin carpetas vacías ni proyectos ficticios.
