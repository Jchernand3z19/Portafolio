# Plantilla para un proyecto nuevo

Reemplaza `<slug>` y los textos entre corchetes antes de publicar.

## Nombre y ubicación

```text
<slug>/
```

Ejemplo:

```text
precios-supermercados-sps/
```

## Estructura sugerida

```text
<slug>/
├── README.md
├── requirements.txt
├── .env.example
├── src/
├── scripts/
├── data/
│   ├── samples/
│   └── README.md
├── dashboard/
├── docs/
└── tests/
```

Crea únicamente las carpetas que el proyecto realmente necesite.

## Contenido del README del proyecto

```markdown
# [Nombre profesional del proyecto]

[Descripción de una o dos líneas sobre el producto analítico.]

## Estado

[Planificado / En desarrollo / Publicado / Mantenimiento]

## Problema

[Situación concreta que origina el proyecto.]

## Objetivo

[Resultado medible o producto que se busca construir.]

## Usuarios

[Quién utilizaría el dashboard, proceso o análisis.]

## Fuentes de datos

- [Fuente 1]
- [Fuente 2]

## Proceso

1. [Extracción]
2. [Limpieza]
3. [Modelado]
4. [Validación]
5. [Publicación]

## Arquitectura

[Diagrama o explicación del flujo de datos.]

## Tecnologías

- [Herramienta]
- [Herramienta]

## Estructura del proyecto

[Árbol de carpetas y función de cada componente.]

## Ejecución local

[Pasos reproducibles.]

## Resultados

[Indicadores, mejoras o entregables alcanzados.]

## Seguridad y privacidad

[Qué datos o credenciales fueron excluidos.]

## Próximos pasos

[Mejoras pendientes reales.]
```

## Módulo del portafolio

Crear en la raíz:

```text
project-<slug>.js
project-<slug>.css
```

Estructura mínima del JavaScript:

```javascript
(() => {
  function card() {
    return `
      <article class="card">
        <h3>Nombre del proyecto</h3>
        <p>Descripción breve.</p>
        <button id="abrir-mi-proyecto" type="button">Ver proyecto</button>
      </article>`;
  }

  function detail() {
    return `
      <section id="mi-proyecto-detalle" hidden>
        <button id="cerrar-mi-proyecto" type="button">Cerrar</button>
        <h2>Nombre del proyecto</h2>
      </section>`;
  }

  function setup() {
    const detailView = document.getElementById('mi-proyecto-detalle');
    document.getElementById('abrir-mi-proyecto').onclick = () => {
      detailView.hidden = false;
    };
    document.getElementById('cerrar-mi-proyecto').onclick = () => {
      detailView.hidden = true;
    };
  }

  window.PortfolioProjects.register({
    id: '<slug>',
    cardHtml: card(),
    detailHtml: detail(),
    setup
  });
})();
```

Después agregar ambos archivos en `script.js`:

```javascript
const projectStyles = [
  'project-mundial.css',
  'project-<slug>.css'
];

const projectModules = [
  'project-mundial.js',
  'project-<slug>.js'
];
```

## Checklist antes de publicar

- [ ] Nombre claro y consistente.
- [ ] README completo.
- [ ] Enlaces funcionales.
- [ ] Datos privados excluidos.
- [ ] Variables de entorno documentadas.
- [ ] Dependencias definidas.
- [ ] Capturas optimizadas.
- [ ] Tarjeta y detalle responsive.
- [ ] Código específico dentro de su carpeta.
- [ ] Workflow separado, cuando aplique.
