# Verificación productiva de GATE-17

Fecha de verificación: 2026-08-20 (Honduras) / 2026-08-21 UTC.

Este documento registra evidencia estable de que la rama `main` dejó de estar desprotegida antes de continuar con las dependencias productivas del proyecto.

## Evidencia observada

- GitHub reporta `main` con `protected: true` después de crear el ruleset `main-protection`.
- El ruleset fue configurado activo y dirigido a la rama por defecto (`main`).
- La configuración humana declarada incluye: PR obligatorio antes de merge, `tests` como status check requerido, resolución de conversaciones, bloqueo de force-pushes, restricción de borrado, cero aprobaciones obligatorias y bypass vacío.
- PR de verificación: `#29 — Verifica enforcement productivo de GATE-17`.
- Primer intento de merge, con el check todavía ejecutándose: GitHub respondió `405 Repository rule violations found` y `Required status check "tests" is in progress.`
- Workflow de la prueba: `Precios Supermercados SPS - Pruebas base`, run `32444018972`; el job `tests` terminó en `success`.
- Con `tests` ya verde se creó deliberadamente un hilo de review sin resolver y se reintentó el merge. GitHub respondió `405 Repository rule violations found` y `A conversation must be resolved before this pull request can be merged.`
- El hilo temporal se resuelve antes del merge final.

## Resultado

`GATE-17 = PASS_PRODUCTIVE_EVIDENCE`.

La evidencia funcional demuestra que el ruleset no es sólo declarativo: GitHub impide integrar en `main` mientras el status check requerido no esté verde y también impide el merge con conversaciones de review sin resolver.

Esta verificación no autoriza tráfico live, no confirma SPS, no crea trusted collector físico y no conecta persistencia productiva.
