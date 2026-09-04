# Estándar de tarjetas de proyecto

Todas las tarjetas publicadas en la sección `Proyectos` deben compartir la misma arquitectura visual y el mismo vocabulario de navegación. El contenido puede variar por proyecto; la experiencia de uso no.

## Estructura obligatoria

Cada tarjeta debe presentar, en este orden:

1. Jerarquía del proyecto (`PROYECTO PRINCIPAL · 01`, `PROYECTO · 02`, etc.).
2. Visual principal del proyecto.
3. Tipo de proyecto o capacidad principal.
4. Tecnologías relevantes.
5. Título.
6. Descripción breve.
7. Acciones.

El visual puede ser distinto según el proyecto —por ejemplo KPIs, captura de dashboard o una visualización—, pero debe ocupar el mismo bloque estructural de la tarjeta.

## Vocabulario de acciones

Las acciones principales se nombran siempre igual cuando cumplen la misma función:

| Orden | Español | Inglés | Función |
| --- | --- | --- | --- |
| 1 | `Explorar proyecto` | `Explore project` | Abre el detalle completo dentro del portafolio. |
| 2 | `Ver resultado` | `View result` | Abre el entregable o evidencia principal: dashboard, extracción, demo o resultado equivalente. |
| 3 | `Ver código` | `View code` | Abre la implementación en GitHub. |

No usar variantes como `Ver proyecto completo`, `Abrir proyecto`, `Explorar solución` o `Abrir dashboard` para una acción que ya corresponde a una de estas tres funciones.

## Componentes compartidos

El estándar está implementado mediante:

```text
css/project-card-standard.css
js/project-card-standard.js
```

El cargador raíz (`script.js`) aplica estos componentes después de cargar los módulos de proyecto. Las clases compartidas son:

```text
portfolio-card-standard
portfolio-card__visual
portfolio-card__body
portfolio-card__kind
portfolio-card__tags
portfolio-card__actions
portfolio-card__action
portfolio-card__action--primary
portfolio-card__action--secondary
portfolio-card__action--tertiary
```

Los CSS propios de cada proyecto deben limitarse a su visual y detalle específico. No deben redefinir la estructura general de la tarjeta ni crear un sistema alternativo de botones, tags, espaciado o jerarquía.

## Jerarquía visual

El proyecto principal puede tener un énfasis ligeramente superior en la barra de jerarquía, pero no debe usar una tarjeta completamente distinta. La prioridad se comunica con el rótulo y el orden, no rompiendo el sistema visual.

## Responsive y accesibilidad

- Las tarjetas deben conservar el mismo orden semántico en escritorio y móvil.
- Los botones y enlaces deben tener estados `focus-visible`.
- El visual no puede provocar overflow horizontal global.
- En móvil, las acciones se apilan a ancho completo.
- La jerarquía y las acciones deben actualizarse también al cambiar de idioma.

## Regla para proyectos futuros

Un proyecto nuevo puede tener identidad propia en su imagen, datos y contenido, pero no debe inventar otra tarjeta. Antes de publicarlo debe reutilizar este estándar y pasar el smoke test del portafolio.