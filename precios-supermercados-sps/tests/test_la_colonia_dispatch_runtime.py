from pathlib import Path


def _workflow_text() -> str:
    repo_root = Path(__file__).resolve().parents[2]
    return (
        repo_root / ".github/workflows/precios-supermercados-sps-la-colonia-command.yml"
    ).read_text(encoding="utf-8")


def test_dispatch_usa_nombre_de_archivo_y_api_actual():
    workflow = _workflow_text()

    assert "const liveWorkflowFile = 'precios-supermercados-sps-la-colonia-live.yml';" in workflow
    assert "workflow_id: liveWorkflowFile" in workflow
    assert "return_run_details: true" in workflow
    assert "'X-GitHub-Api-Version': apiVersion" in workflow
    assert "const apiVersion = '2026-03-10';" in workflow


def test_resultado_expone_run_live_sin_datos_comerciales():
    workflow = _workflow_text()

    assert "dispatcher-result.json" in workflow
    assert "live_run_id" in workflow
    assert "live_run_url" in workflow
    assert "retention-days: 1" in workflow
    assert "product_name" not in workflow
    assert "price" not in workflow.lower()


def test_comentario_intenta_graphql_y_rest_con_fallback_seguro():
    workflow = _workflow_text()

    assert "addComment(input: {subjectId: $subjectId, body: $body})" in workflow
    assert "github.rest.issues.createComment" in workflow
    assert "comentario pendiente de recuperación por el conector" in workflow
    assert "core.setFailed('La solicitud fue rechazada" in workflow


def test_no_ejecuta_datos_del_pr_en_shell():
    workflow = _workflow_text()

    assert "ref: main" in workflow
    assert "persist-credentials: false" in workflow
    assert "eval " not in workflow
    assert "github.event.pull_request.head" not in workflow
    assert "workflow_id: decision.workflow" not in workflow
