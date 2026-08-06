from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
RECOVERY = (
    REPO_ROOT
    / ".github/workflows/precios-supermercados-sps-la-colonia-dispatch-recovery.yml"
)
OBSERVER = (
    REPO_ROOT
    / "precios-supermercados-sps/scripts/validar_resultado_controlador_la_colonia.js"
)


def test_recovery_observes_every_completed_controller_run():
    text = RECOVERY.read_text(encoding="utf-8")
    assert "workflow_run:" in text
    assert "types: [completed]" in text
    assert "github.event.workflow_run.conclusion == 'success'" not in text
    assert "La Colonia - Despachador seguro por archivo" in text


def test_recovery_remains_read_only_and_never_dispatches():
    text = RECOVERY.read_text(encoding="utf-8")
    assert "permissions:\n  actions: read\n  contents: read" in text
    assert "ref: main" in text
    assert "persist-credentials: false" in text
    assert "issues: write" not in text
    assert "actions: write" not in text
    assert "workflow_dispatch:" not in text
    assert "/dispatches" not in text


def test_observer_keeps_recovery_required_without_starting_another_workflow():
    text = OBSERVER.read_text(encoding="utf-8")
    assert "RECOVERY_REQUIRED" in text
    assert "dispatch_sent" in text
    assert "comment_published" in text
    assert "workflow_dispatch" not in text
    assert "/dispatches" not in text


def test_recovery_audit_is_offline_only():
    text = Path(__file__).read_text(encoding="utf-8")
    for forbidden in ("requests.", "urllib", "httpx", "aiohttp", "socket."):
        assert forbidden not in text
