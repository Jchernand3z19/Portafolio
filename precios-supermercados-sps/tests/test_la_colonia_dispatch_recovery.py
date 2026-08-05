from pathlib import Path


def _workflow_text() -> str:
    repo_root = Path(__file__).resolve().parents[2]
    return (
        repo_root
        / ".github/workflows/precios-supermercados-sps-la-colonia-dispatch-recovery.yml"
    ).read_text(encoding="utf-8")


def test_observador_solo_lee_resultado_del_controlador():
    workflow = _workflow_text()

    assert "workflow_run:" in workflow
    assert "La Colonia - Despachador seguro por archivo" in workflow
    assert "actions: read" in workflow
    assert "contents: read" in workflow
    assert "issues: write" not in workflow
    assert "actions: write" not in workflow
    assert "actions/download-artifact@v4" in workflow
    assert "dispatcher-result.json" in workflow


def test_observador_no_hace_checkout_ni_ejecuta_codigo_del_pr():
    workflow = _workflow_text()

    assert "actions/checkout" not in workflow
    assert "pull_request.head" not in workflow
    assert "eval " not in workflow
    assert "createWorkflowDispatch" not in workflow
    assert "/dispatches" not in workflow


def test_observador_expone_identificadores_sanitizados():
    workflow = _workflow_text()

    assert "RECOVERY_REQUIRED" in workflow
    assert "controller_run_id=${sourceRunId}" in workflow
    assert "live_run_id=${liveRunId}" in workflow
    assert "request_id=${safeRequestId}" in workflow
    assert "const numericId = /^[0-9]+$/;" in workflow
    assert "const requestId = /^[a-z0-9]" in workflow


def test_observador_solo_falla_cuando_dispatch_aceptado_no_comento():
    workflow = _workflow_text()

    assert "if (accepted && dispatchSent && !commentPublished)" in workflow
    assert "El dispatch fue enviado, pero el comentario requiere recuperación controlada." in workflow
