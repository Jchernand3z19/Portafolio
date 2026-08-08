from pathlib import Path


def _workflow_text() -> str:
    repo_root = Path(__file__).resolve().parents[2]
    return (
        repo_root / ".github/workflows/precios-supermercados-sps-la-colonia-command.yml"
    ).read_text(encoding="utf-8")


def test_controlador_esta_globalmente_bloqueado_y_no_puede_despachar():
    workflow = _workflow_text()

    assert "actions: write" not in workflow
    assert "/actions/workflows/" not in workflow


def test_resultado_expone_run_modo_y_workflow_sin_datos_comerciales():
    workflow = _workflow_text()

    assert "dispatcher-result.json" in workflow
    assert "retention-days: 1" in workflow
    assert "product_name" not in workflow
    assert "price" not in workflow.lower()


def test_controlador_no_escribe_comentarios_desde_contexto_privilegiado():
    workflow = _workflow_text()

    assert "issues: write" not in workflow
    assert "addComment" not in workflow
    assert "createComment" not in workflow


def test_no_ejecuta_datos_del_pr_en_shell():
    workflow = _workflow_text()

    assert "ref: ${{ github.workflow_sha }}" in workflow
    assert "persist-credentials: false" in workflow
    assert "eval " not in workflow
    assert "github.event.pull_request.head" not in workflow
    assert "/dispatches" not in workflow
