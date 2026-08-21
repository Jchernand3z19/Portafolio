from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from precios_supermercados.cloudflare_script_settings import (
    CloudflareScriptSettingsError,
    immutable_settings_snapshot,
    parse_cloudflare_script_settings,
)


def _response(*, trace_rate: object = 1, request_rate: object = 1) -> dict[str, object]:
    return {
        "success": True,
        "errors": [],
        "messages": [],
        "result": {
            "observability": {
                "enabled": True,
                "head_sampling_rate": request_rate,
                "traces": {
                    "enabled": True,
                    "head_sampling_rate": trace_rate,
                    "persist": True,
                    "propagation_policy": "authenticated",
                },
            }
        },
    }


def test_parsea_settings_oficiales_sin_inferir_autoridad_productiva() -> None:
    evidence = parse_cloudflare_script_settings(_response())

    assert evidence.observability_enabled is True
    assert evidence.request_head_sampling_rate_ppm == 1_000_000
    assert evidence.traces_enabled is True
    assert evidence.traces_head_sampling_rate_ppm == 1_000_000
    assert evidence.full_trace_sampling is True
    assert evidence.traces_persist is True
    assert evidence.traces_propagation_policy == "authenticated"
    assert evidence.source == "cloudflare_rest_api"
    assert evidence.production_authority is False
    assert len(evidence.digest) == 64


def test_acepta_json_textual_y_normaliza_decimal_exacto() -> None:
    raw = '{"success":true,"errors":[],"result":{"observability":{"enabled":true,"head_sampling_rate":0.5,"traces":{"enabled":true,"head_sampling_rate":0.25}}}}'
    evidence = parse_cloudflare_script_settings(raw)

    assert evidence.request_head_sampling_rate_ppm == 500_000
    assert evidence.traces_head_sampling_rate_ppm == 250_000
    assert evidence.full_trace_sampling is False


def test_acepta_decimal_y_rechaza_precision_no_representable_en_ppm() -> None:
    evidence = parse_cloudflare_script_settings(_response(trace_rate=Decimal("0.123456")))
    assert evidence.traces_head_sampling_rate_ppm == 123_456

    with pytest.raises(CloudflareScriptSettingsError) as captured:
        parse_cloudflare_script_settings(_response(trace_rate="0.1234567"))
    assert captured.value.code == "settings_traces_sampling_invalid"


@pytest.mark.parametrize("value", [-0.1, 1.1, "NaN", "Infinity", True, None])
def test_sampling_fuera_de_contrato_falla(value: object) -> None:
    with pytest.raises(CloudflareScriptSettingsError) as captured:
        parse_cloudflare_script_settings(_response(trace_rate=value))
    assert captured.value.code == "settings_traces_sampling_invalid"


def test_api_unsuccessful_o_con_errors_falla() -> None:
    failed = _response()
    failed["success"] = False
    with pytest.raises(CloudflareScriptSettingsError) as captured:
        parse_cloudflare_script_settings(failed)
    assert captured.value.code == "settings_api_unsuccessful"

    errors = _response()
    errors["errors"] = [{"code": 1000, "message": "boom"}]
    with pytest.raises(CloudflareScriptSettingsError) as captured:
        parse_cloudflare_script_settings(errors)
    assert captured.value.code == "settings_api_errors_present"


def test_no_materializa_defaults_documentados_si_el_api_omite_campos() -> None:
    missing_trace_enabled = _response()
    del missing_trace_enabled["result"]["observability"]["traces"]["enabled"]
    with pytest.raises(CloudflareScriptSettingsError) as captured:
        parse_cloudflare_script_settings(missing_trace_enabled)
    assert captured.value.code == "settings_traces_enabled_missing"

    missing_trace_rate = _response()
    del missing_trace_rate["result"]["observability"]["traces"]["head_sampling_rate"]
    with pytest.raises(CloudflareScriptSettingsError) as captured:
        parse_cloudflare_script_settings(missing_trace_rate)
    assert captured.value.code == "settings_traces_sampling_missing"


def test_no_infiere_tracing_desde_observability_global() -> None:
    response = _response()
    response["result"]["observability"]["traces"]["enabled"] = False
    evidence = parse_cloudflare_script_settings(response)

    assert evidence.observability_enabled is True
    assert evidence.traces_enabled is False


def test_propagation_desconocida_y_tipos_booleanos_invalidos_fallan() -> None:
    response = _response()
    response["result"]["observability"]["traces"]["propagation_policy"] = "unsafe"
    with pytest.raises(CloudflareScriptSettingsError) as captured:
        parse_cloudflare_script_settings(response)
    assert captured.value.code == "settings_traces_propagation_policy_invalid"

    response = _response()
    response["result"]["observability"]["enabled"] = 1
    with pytest.raises(CloudflareScriptSettingsError) as captured:
        parse_cloudflare_script_settings(response)
    assert captured.value.code == "settings_observability_enabled_invalid"


def test_snapshot_es_solo_lectura_y_autoridad_no_puede_fabricarse() -> None:
    evidence = parse_cloudflare_script_settings(_response())
    snapshot = immutable_settings_snapshot(evidence)
    with pytest.raises(TypeError):
        snapshot["traces_enabled"] = False

    with pytest.raises(CloudflareScriptSettingsError) as captured:
        replace(evidence, production_authority=True)
    assert captured.value.code == "settings_production_authority_forbidden"
