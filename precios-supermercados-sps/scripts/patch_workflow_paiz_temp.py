#!/usr/bin/env python3
# Temporal: se elimina en el mismo commit que publica el workflow final.
from pathlib import Path

path = Path('../.github/workflows/precios-supermercados-sps-la-colonia-mvp-update.yml')
text = path.read_text(encoding='utf-8')

capture_marker = '      - name: Aceptar sólo snapshots completos\n'
capture = '''      - name: Descargar catálogos TGU Paiz
        id: paiz
        shell: bash
        run: |
          set +e
          python scripts/obtener_catalogo_paiz_operativo.py \\
            --live-read-only \\
            --allow-full-catalog \\
            --delay-seconds 1.0 \\
            --max-requests 500 \\
            --output-directory run-artifacts/paiz \\
            --raw-directory run-artifacts/paiz/raw \\
            --evidence-output run-artifacts/paiz/evidence.json
          code=$?
          echo "exit_code=$code" >> "$GITHUB_OUTPUT"
          exit 0

'''
if 'Descargar catálogos TGU Paiz' not in text:
    if capture_marker not in text:
        raise SystemExit('capture_marker_missing')
    text = text.replace(capture_marker, capture + capture_marker, 1)

persist_marker = '      - name: Verificar commits exactos en Turso\n'
paiz_persist = '''      - name: Validar snapshots completos Paiz
        shell: bash
        env:
          PAIZ_EXIT: ${{ steps.paiz.outputs.exit_code }}
        run: |
          set -euo pipefail
          test "$PAIZ_EXIT" = "0"
          python - <<'PY'
          from pathlib import Path
          import sys
          sys.path.insert(0, 'scripts')
          from actualizar_mvp_turso_paiz import validate_snapshot_bytes
          for name in ('multiplaza', 'proceres'):
              snapshot = validate_snapshot_bytes(Path(f'run-artifacts/paiz/snapshot-paiz-{name}.json').read_bytes())
              assert snapshot['catalog_complete'] is True
              assert snapshot['location_verified_same_run'] is True
              assert snapshot['catalog_products_reported'] == snapshot['unique_products_extracted']
          PY

      - name: Asegurar esquema Paiz en Turso
        shell: bash
        env:
          TURSO_DATABASE_URL: ${{ secrets.TURSO_DATABASE_URL }}
          TURSO_AUTH_TOKEN: ${{ secrets.TURSO_AUTH_TOKEN }}
        run: python scripts/migrar_mvp_paiz.py --turso

      - name: Persistir Paiz Multiplaza en Turso
        shell: bash
        env:
          TURSO_DATABASE_URL: ${{ secrets.TURSO_DATABASE_URL }}
          TURSO_AUTH_TOKEN: ${{ secrets.TURSO_AUTH_TOKEN }}
        run: |
          set -euo pipefail
          python scripts/actualizar_mvp_turso_paiz.py \\
            run-artifacts/paiz/snapshot-paiz-multiplaza.json \\
            --run-id "${GITHUB_RUN_ID}-paiz-multiplaza" \\
            --verify

      - name: Persistir Paiz Próceres en Turso
        shell: bash
        env:
          TURSO_DATABASE_URL: ${{ secrets.TURSO_DATABASE_URL }}
          TURSO_AUTH_TOKEN: ${{ secrets.TURSO_AUTH_TOKEN }}
        run: |
          set -euo pipefail
          python scripts/actualizar_mvp_turso_paiz.py \\
            run-artifacts/paiz/snapshot-paiz-proceres.json \\
            --run-id "${GITHUB_RUN_ID}-paiz-proceres" \\
            --verify

'''
if 'Persistir Paiz Multiplaza en Turso' not in text:
    if persist_marker not in text:
        raise SystemExit('persist_marker_missing')
    text = text.replace(persist_marker, paiz_persist + persist_marker, 1)

artifact_marker = '      - name: Publicar evidencia\n'
verify = '''      - name: Verificar estado Paiz en Turso
        shell: bash
        env:
          TURSO_DATABASE_URL: ${{ secrets.TURSO_DATABASE_URL }}
          TURSO_AUTH_TOKEN: ${{ secrets.TURSO_AUTH_TOKEN }}
        run: |
          set -euo pipefail
          python - <<'PY'
          import json
          import os
          import sys
          from pathlib import Path
          sys.path.insert(0, 'scripts')
          from actualizar_mvp_turso_la_colonia import _execute_rows, _pipeline, _stmt
          from actualizar_mvp_turso_paiz import validate_snapshot_bytes

          expected = []
          for name, location in (
              ('multiplaza', 'paiz_tgu_multiplaza'),
              ('proceres', 'paiz_tgu_proceres'),
          ):
              snap = validate_snapshot_bytes(Path(f'run-artifacts/paiz/snapshot-paiz-{name}.json').read_bytes())
              expected.append([location, snap['skus_extracted']])
          data = _pipeline(
              os.environ['TURSO_DATABASE_URL'], os.environ['TURSO_AUTH_TOKEN'],
              [
                  {'type':'execute','stmt':_stmt('''SELECT location_id,COUNT(*) FROM price_history WHERE supermarket_id='paiz' AND location_id IN ('paiz_tgu_multiplaza','paiz_tgu_proceres') AND valid_to_utc IS NULL GROUP BY location_id ORDER BY location_id''')},
                  {'type':'execute','stmt':_stmt('''SELECT COUNT(*) FROM (SELECT product_id,location_id FROM price_history WHERE supermarket_id='paiz' AND valid_to_utc IS NULL GROUP BY product_id,location_id HAVING COUNT(*)>1)''')},
                  {'type':'execute','stmt':_stmt('SELECT COUNT(*) FROM pragma_foreign_key_check')},
                  {'type':'execute','stmt':_stmt('PRAGMA integrity_check')},
                  {'type':'close'},
              ],
          )
          rows = _execute_rows(data['results'][0])
          duplicates = _execute_rows(data['results'][1])
          fk = _execute_rows(data['results'][2])
          integrity = _execute_rows(data['results'][3])
          if [row[0] for row in rows] != [row[0] for row in expected]:
              raise SystemExit(f'paiz_location_state_missing:{rows}')
          if any(actual[1] < minimum[1] for actual, minimum in zip(rows, expected, strict=True)):
              raise SystemExit(f'paiz_current_state_incomplete:minimum={expected}:actual={rows}')
          if duplicates != [[0]] or fk != [[0]] or integrity != [['ok']]:
              raise SystemExit(f'paiz_integrity_failed:{duplicates}:{fk}:{integrity}')
          print(json.dumps({'open_by_location': rows, 'duplicate_open_periods': 0, 'foreign_key_violations': 0, 'integrity_check': 'ok'}, sort_keys=True))
          PY

'''
if 'Verificar estado Paiz en Turso' not in text:
    if artifact_marker not in text:
        raise SystemExit('artifact_marker_missing')
    text = text.replace(artifact_marker, verify + artifact_marker, 1)

path.write_text(text, encoding='utf-8')
