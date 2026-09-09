# Router de proyectos del monorepo

Este repositorio es un monorepo. Antes de actuar, resuelve `PROJECT_ID` y
`PROJECT_ROOT` con [`.github/project-scopes.yml`](.github/project-scopes.yml), los
paths modificados y el objetivo del usuario. Después lee el `AGENTS.md` del
proyecto correspondiente.

- Un número de PR o que un PR sea reciente no determina su proyecto.
- Los changed paths y workflows registrados son la evidencia primaria de scope.
- PRs de otro project root quedan fuera de alcance: no modificarlos, fusionarlos,
  cerrarlos, comentarlos ni usarlos como checkpoint.
- Un cambio entre proyectos requiere intención explícita y un PR de gobernanza
  separado cuando afecte infraestructura compartida.
- Los paths shared son integraciones concretas, no un permiso para mezclar roots.
- `.agents/skills` contiene metodología compartida y nunca estado mutable de RPI,
  PAGOS o MUNDIAL.

Convenciones nuevas: `[RPI]` + `rpi/`, `[PAGOS]` + `pagos/`, `[MUNDIAL]` +
`mundial/`, o `[MONOREPO]` + `monorepo/`. Sólo las ramas históricas registradas
en el contrato están exentas del prefijo de rama.
