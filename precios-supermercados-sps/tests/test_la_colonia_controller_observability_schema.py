from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
WRAPPER = (
    REPO_ROOT
    / "precios-supermercados-sps/scripts/controlar_solicitud_archivo_la_colonia_observable.js"
)


def test_resultado_inicial_usa_el_esquema_legacy_del_observador():
    text = WRAPPER.read_text(encoding="utf-8")
    initial = text.split("function initialResult", 1)[1].split(
        "function trustedDispatchDetails", 1
    )[0]
    assert "mode:" not in initial
    assert "workflow:" not in initial
    assert "dispatch_sent: false" in initial
    assert "controller_run_id: runId" in initial


def test_checkpoint_facet_exige_workflow_inputs_y_ref_main_cerrados():
    text = WRAPPER.read_text(encoding="utf-8")
    trusted = text.split("function trustedDispatchDetails", 1)[1].split(
        "function checkpointDispatch", 1
    )[0]
    assert "workflowId === FACET_WORKFLOW_FILE" in trusted
    assert 'ref === "main"' in trusted
    assert 'requestId === "la-colonia-facet-discovery-001"' in trusted
    assert 'inputs.discovery_plan === "catalog_categories_v1"' in trusted
    assert 'inputs.delay_seconds === "1.5"' in trusted


def test_prueba_de_esquema_no_utiliza_internet():
    text = Path(__file__).read_text(encoding="utf-8")
    for forbidden in ("requests.", "urllib", "httpx", "aiohttp", "socket."):
        assert forbidden not in text
