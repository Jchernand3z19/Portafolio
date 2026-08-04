# Plantilla para publicar un proyecto nuevo

Reemplaza `<slug>` y los textos entre corchetes antes de publicar.

## 1. Repositorio técnico

Crea un repositorio independiente:

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

Ejemplo:

```text
precios-supermercados-sps
```

Crea únicamente las carpetas que tengan contenido real.

## 2. README del proyecto

```markdown
# [Nombre profesional del proyecto]

[Descripción de una o dos líneas.]

## Estado

[Planificado / En desarrollo / Publicado / Mantenimiento]

## Problema

[Situación concreta que origina el proyecto.]

## Objetivo

[Resultado que se busca construir.]

## Usuarios

[Quién utilizaría el dashboard, proceso o análisis.]

## Fuentes de datos

- [Fuente 1]
- [Fuente 2]

## Proceso

1. [Extracción]
2. [Limpieza]
3. [Estandarización]
4. [Validación]
5. [Publicación]

## Arquitectura

[Diagrama o explicación del flujo.]

## Tecnologías

- [Herramienta]
- [Herramienta]

## Estructura del proyecto

[Árbol de carpetas y función de cada componente.]

## Ejecución

[Pasos reproducibles.]

## Resultados

[Indicadores, mejoras o entregables alcanzados.]

## Seguridad y privacidad

[Datos, credenciales y variables excluidas.]

## Próximos pasos

[Mejoras pendientes reales.]
```

## 3. Recursos dentro del portafolio

Guardar imágenes en:

```text
assets/projects/<slug>/
```

Crear el módulo visual en:

```text
js/projects/<slug>.js
```

Crear sus estilos en:

```text
css/projects/<slug>.css
```

## 4. Registro en `js/main.js`

```javascript
const projectStyles = [
  'css/projects/mundial.css',
  'css/projects/<slug>.css'
];

const projectModules = [
  'js/projects/mundial.js',
  'js/projects/<slug>.js'
];
```

## 5. Estructura mínima del módulo visual

```javascript
(() => {
  function card() {
    return `
      <article class="card">
        <h3>Nombre del proyecto</h3>
        <p>Descripción breve.</p>
        <a href="https://github.com/Jchernand3z19/<slug>">Ver repositorio</a>
      </article>`;
  }

  function detail() {
    return `
      <section id="<slug>-detalle" hidden>
        <button id="cerrar-<slug>" type="button">Cerrar</button>
        <h2>Nombre del proyecto</h2>
      </section>`;
  }

  function setup() {
    // Eventos exclusivos de esta presentación.
  }

  window.PortfolioProjects.register({
    id: '<slug>',
    cardHtml: card(),
    detailHtml: detail(),
    setup
  });
})();
```

## Checklist

- [ ] Repositorio independiente creado.
- [ ] Nombre claro en minúsculas y guiones.
- [ ] README completo.
- [ ] Enlaces funcionales.
- [ ] Datos privados excluidos.
- [ ] Variables de entorno documentadas.
- [ ] Dependencias definidas.
- [ ] Capturas optimizadas.
- [ ] Tarjeta y detalle responsive.
- [ ] JavaScript dentro de `js/projects/`.
- [ ] CSS dentro de `css/projects/`.
- [ ] Recursos dentro de `assets/projects/<slug>/`.
- [ ] Código técnico fuera del repositorio `Portafolio`.
