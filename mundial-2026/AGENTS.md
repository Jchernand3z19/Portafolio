# Instrucciones para agentes — Mundial 2026

## PROJECT / PULL REQUEST SCOPE CONTRACT

```text
PROJECT_ID=MUNDIAL
PROJECT_ROOT=mundial-2026/
PR_TITLE_PREFIX=[MUNDIAL]
FUTURE_BRANCH_PREFIX=mundial/
```

MUNDIAL es dueño de su project root y de los tres workflows
`mundial-2026-prediccion-*` registrados en `/.github/project-scopes.yml`. Puede
tocar la integración compartida del portafolio sólo junto con un cambio MUNDIAL
que la justifique. No debe modificar RPI, PAGOS ni sus workflows, automatizaciones,
outputs o secretos. Los cambios de gobernanza pertenecen a un PR `[MONOREPO]`.

## Operación

- GitHub `main`, Actions y la documentación del proyecto son la fuente de verdad.
- Los workflows programados y manuales conservan su semántica productiva.
- `SPREADSHEET_ID`, `GOOGLE_CLIENT_EMAIL` y `GOOGLE_PRIVATE_KEY` pertenecen
  lógicamente a MUNDIAL; nunca imprimir ni versionar sus valores.
- La integración del portafolio reutiliza el registro y los estilos compartidos;
  no debe borrar ni reemplazar tarjetas de otros proyectos.
