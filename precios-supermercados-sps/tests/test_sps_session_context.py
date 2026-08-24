from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import precios_supermercados.sps_session_context as module


def _fingerprint(value: str) -> str:
    rendered = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def test_constantes_de_sesion_coinciden_con_radiografia_canonica() -> None:
    report_path = (
        Path(__file__).resolve().parents[1]
        / "reports"
        / "discovery"
        / "la-colonia-location-binding-2026-08-24.json"
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    signals = {
        item["key"]: item["city_fingerprint"]
        for item in report["binding_report"]["signals"]
        if item["channel"] == "cookie" and item["changed_after_city"] is True
    }
    assert signals == dict(module.SPS_SESSION_SIGNAL_FINGERPRINTS)
    assert report["binding_report"]["source_location_key_candidate"].startswith(
        "request:regionid:sha256:"
    )
    assert module.SPS_BINDING_EVIDENCE == (
        "location_binding_radiography:sha256:"
        "80f2e4d333043a38954603c9c72086d241ac9b5a1cc1f10b71a9fde772588d95"
    )


def test_contexto_sintetico_verifica_ambas_cookies_y_no_expone_raw(monkeypatch) -> None:
    segment = "synthetic-segment-value"
    session = "synthetic-session-value"
    expected = {
        "vtexsegment": _fingerprint(segment),
        "vtexsession": _fingerprint(session),
    }
    monkeypatch.setattr(module, "SPS_SESSION_SIGNAL_FINGERPRINTS", expected)

    context = module.verify_sps_session_context(
        {
            "VTEXSEGMENT": segment,
            "vtexsession": session,
            "unrelated": "ignored",
        }
    )

    assert context.complete is True
    assert context.public_dict()["session_context_complete"] is True
    assert context.public_dict()["signal_fingerprints"] == expected
    assert context.public_dict()["raw_values_exposed"] is False
    assert segment not in repr(context)
    assert session not in repr(context)
    rendered = json.dumps(context.public_dict(), sort_keys=True)
    assert segment not in rendered
    assert session not in rendered
    assert context.wire_signals() == {
        "vtexsegment": {"fingerprint": expected["vtexsegment"], "rawValue": segment},
        "vtexsession": {"fingerprint": expected["vtexsession"], "rawValue": session},
    }
    assert context.cookie_header() == (
        f"vtexsegment={segment}; vtexsession={session}"
    )


def test_contexto_incompleto_o_alterado_falla_cerrado(monkeypatch) -> None:
    segment = "synthetic-segment"
    session = "synthetic-session"
    monkeypatch.setattr(
        module,
        "SPS_SESSION_SIGNAL_FINGERPRINTS",
        {
            "vtexsegment": _fingerprint(segment),
            "vtexsession": _fingerprint(session),
        },
    )

    with pytest.raises(module.SpsSessionContextError) as missing:
        module.verify_sps_session_context({"vtexsegment": segment})
    assert missing.value.code == "sps_session_vtexsession_missing"

    with pytest.raises(module.SpsSessionContextError) as changed:
        module.verify_sps_session_context(
            {"vtexsegment": segment, "vtexsession": "different"}
        )
    assert changed.value.code == "sps_session_vtexsession_fingerprint_mismatch"


def test_cookie_no_permite_inyeccion_de_headers(monkeypatch) -> None:
    safe_session = "synthetic-session"
    unsafe_segment = "bad; injected=1"
    monkeypatch.setattr(
        module,
        "SPS_SESSION_SIGNAL_FINGERPRINTS",
        {
            "vtexsegment": _fingerprint(unsafe_segment),
            "vtexsession": _fingerprint(safe_session),
        },
    )
    with pytest.raises(module.SpsSessionContextError) as captured:
        module.verify_sps_session_context(
            {"vtexsegment": unsafe_segment, "vtexsession": safe_session}
        )
    assert captured.value.code == "sps_session_vtexsegment_invalid"
