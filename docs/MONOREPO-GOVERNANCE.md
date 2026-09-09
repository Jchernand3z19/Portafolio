# Gobernanza y aislamiento del monorepo

La autoridad ejecutable es `.github/project-scopes.yml`; este documento explica
las decisiones verificadas durante la migración del 9 de septiembre de 2026.

## Registro auditado

`main` contiene dos project roots reales: RPI y MUNDIAL. PAGOS existe en el PR
#436 y su root queda reservado desde ahora para que el validator lo reconozca antes
de su integración. `css/`, `js/`, `docs/`, `tests/`, `.agents/` y `.github/` no son
proyectos; cumplen funciones compartidas o de integración enumeradas de forma
explícita.

## Workflows y ejecución

- Los 20 workflows de precios y Cloudflare pertenecen a RPI. El workflow
  `cloudflare-controlled-probe-evidence-verify.yml` se clasificó por sus módulos,
  artifact `precios-sps-*`, request y variables, no sólo por el nombre.
- Los tres workflows `mundial-2026-prediccion-*` pertenecen a MUNDIAL.
- `pagos-whatsapp-residencial-ci.yml`, todavía introducido por #436, pertenece a
  PAGOS y ya limita sus triggers y `working-directory` a ese root.
- `portfolio-frontend-qa.yml` es shared porque valida la integración visible de
  todos los proyectos.
- Los grupos de concurrency existentes son distintos entre workflows. No se
  renombraron grupos ni artifacts productivos que ya tienen consumidores; sus
  nombres actuales identifican el flujo RPI y no colisionan con PAGOS o MUNDIAL.
- Los caches detectados usan el dependency path o working directory del proyecto.
  No existe cache compartido entre runtimes incompatibles.

El path filter de la suite RPI ya no observa `.github/workflows/**`: ahora sólo
responde al root RPI o a su propio workflow. Un cambio PAGOS/MUNDIAL deja de lanzar
esa suite.

El ruleset de `main` exige el contexto `tests`. Ese nombre pertenece al gate
universal de project scope; la suite funcional aparece como `rpi-tests`. Así todos
los PR reciben el control de aislamiento y cada proyecto ejecuta su CI sólo cuando
sus paths cambian.

## Publicación, hosting y secretos

RPI publica sólo bajo `precios-supermercados-sps/**` en `portfolio-data`. Su
Business Mart permanece en el límite privado de artifacts. MUNDIAL publica desde
su propio Apps Script. En `main` no existen `vercel.json`, configuración de Vercel,
CODEOWNERS, Dependabot/Renovate ni issue templates que necesiten migración.

El registry documenta ownership lógico de nombres/prefijos de secrets sin guardar
valores. Los workflows RPI consumen Turso, `PRECIOS_SPS_*` y Cloudflare; MUNDIAL
consume sus tres secretos de Google. El CI demo de PAGOS no recibe secretos. Un
workflow productivo futuro de PAGOS deberá mapear credenciales desde nombres
`PAGOS_*` propios, aunque la aplicación mantenga nombres internos de variables de
entorno.

## Pull requests

El check global obtiene changed files desde GitHub y ejecuta el validator de la
revisión base, sin ejecutar código del PR ni recibir secretos. Rechaza roots
mezclados, workflows ajenos, prefijos incorrectos, paths desconocidos y el uso de
shared como bypass. Las ramas abiertas `feat/rpi-controlled-publication-request`
y `feat/pagos-whatsapp-residencial-mvp` son las únicas excepciones históricas al
prefijo de rama; sus títulos sí deben adoptar el prefijo de proyecto.
