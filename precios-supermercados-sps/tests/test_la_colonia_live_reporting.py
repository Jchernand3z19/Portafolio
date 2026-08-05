from precios_supermercados.automation.la_colonia_live_reporting import (
    MAX_COMMENT_LENGTH,
    build_live_result_comment,
    load_summary,
)


def metadata():
    return {
        "workflow": "La Colonia - Recorrido live manual",
        "run_number": "15",
        "run_id": "123456",
        "run_url": "https://github.com/o/r/actions/runs/123456",
        "branch": "feature/la-colonia-full-crawl-validation",
        "sha": "abc123",
        "mode": "smoke",
        "page_size": "10",
        "max_pages": "2",
        "max_products": "0",
        "delay_seconds": "1.5",
        "profile": "baseline",
        "exit_code": "0",
        "artifact_name": "la-colonia-smoke-summary",
        "artifacts_url": "https://github.com/o/r/actions/runs/123456#artifacts",
    }


def summary(accepted=True):
    return {
        "metrics": {
            "accepted": accepted,
            "pages_expected": 2,
            "pages_attempted": 2,
            "pages_completed": 2 if accepted else 1,
            "page_coverage": 1.0 if accepted else 0.5,
            "products_reported_initial": 5000,
            "products_reported_final": 5000,
            "products_returned": 20,
            "products_processed": 20,
            "skus_returned": 22,
            "skus_extracted": 22,
            "skus_with_price": 21,
            "skus_without_price": 1,
            "promotional_skus": 2,
            "weighted_skus": 1,
            "duplicate_skus": 0,
            "duplicate_products": 0,
            "http_403": 0,
            "http_429": 0,
            "persistent_http_429": 0,
            "http_5xx": 0,
            "retries": 0,
            "errors": 0 if accepted else 1,
            "structural_events": 0,
            "duration_seconds": 2.5,
            "average_response_seconds": 0.4,
            "average_response_bytes": 15000,
            "warnings": [],
            "rejection_reasons": [] if accepted else ["partial_product_page"],
            "proposed_thresholds": {"max_missing_price_ratio": 0.05},
        },
        "products": [{"name": "NO DEBE APARECER", "price": 12.34}],
        "sample_source_key_hashes": ["abc"],
    }


def test_formateador_resultado_aceptado():
    comment = build_live_result_comment(summary(True), metadata())
    assert "`accepted` | `True`" in comment
    assert "la-colonia-live-result:123456" in comment
    assert "Código de salida | `0`" in comment


def test_formateador_resultado_rechazado():
    data = metadata()
    data["exit_code"] = "2"
    comment = build_live_result_comment(summary(False), data)
    assert "`accepted` | `False`" in comment
    assert "partial_product_page" in comment
    assert "Código de salida | `2`" in comment


def test_ausencia_run_summary(tmp_path):
    missing = tmp_path / "missing.json"
    assert load_summary(missing) is None
    comment = build_live_result_comment(None, metadata())
    assert "no estaba disponible" in comment
    assert "`accepted` | `no disponible`" in comment


def test_comentario_sin_datos_comerciales():
    comment = build_live_result_comment(summary(True), metadata())
    assert "NO DEBE APARECER" not in comment
    assert "12.34" not in comment
    assert "sample_source_key_hashes" not in comment


def test_longitud_limitada_del_comentario():
    data = summary(False)
    data["metrics"]["warnings"] = ["x" * 3000 for _ in range(100)]
    comment = build_live_result_comment(data, metadata(), max_length=2_000)
    assert len(comment) <= 2_000
    assert comment.endswith("<!-- la-colonia-live-result:123456 -->")
    assert MAX_COMMENT_LENGTH >= 60_000
