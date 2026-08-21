from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import pytest

from precios_supermercados.la_colonia_edge_structural_request import (
    CATEGORY_TREE_QUERY_SHA256,
    ROOT_TOTAL_QUERY_SHA256,
    LaColoniaEdgeStructuralRequestError,
    build_structural_discovery_url,
    validate_la_colonia_structural_request,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLI = PROJECT_ROOT / "edge" / "cloudflare" / "test" / "structural-fixture-cli.mjs"


def _node() -> str:
    executable = shutil.which("node")
    assert executable is not None, "Node.js es obligatorio para el contrato cross-runtime"
    return executable


def _javascript_validate(url: str) -> dict[str, object]:
    completed = subprocess.run(
        [_node(), str(CLI)],
        cwd=PROJECT_ROOT,
        input=json.dumps(
            {
                "url": url,
                "expectedQuerySha256ByKind": {
                    "root_total": ROOT_TOTAL_QUERY_SHA256,
                    "category_tree": CATEGORY_TREE_QUERY_SHA256,
                },
            }
        ),
        capture_output=True,
        text=True,
        timeout=20,
    )
    result = json.loads(completed.stdout)
    if completed.returncode != 0:
        result["stderr"] = completed.stderr
    return result


def _replace_param(url: str, key: str, value: str) -> str:
    parsed = urlsplit(url)
    pairs = parse_qsl(parsed.query, keep_blank_values=True)
    changed = [(name, value if name == key else current) for name, current in pairs]
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(changed), parsed.fragment))


def test_hashes_de_queries_estructurales_quedan_fijados() -> None:
    assert ROOT_TOTAL_QUERY_SHA256 == "00441ce39ffbb02803351b96826fb86feafad3b3870137f01f074b11260e8163"
    assert CATEGORY_TREE_QUERY_SHA256 == "0a9265b63af869850fac217238fc82aaa3b9fa396ca77f35ee98679e4bb066cb"


@pytest.mark.parametrize("kind", ["root_total", "category_tree"])
def test_python_y_javascript_reconstruyen_el_mismo_digest(kind: str) -> None:
    url = build_structural_discovery_url(kind)
    python_result = validate_la_colonia_structural_request(url)
    javascript_result = _javascript_validate(url)

    assert javascript_result["ok"] is True, javascript_result
    assert javascript_result["requestKind"] == python_result.request_kind
    assert javascript_result["operationName"] == python_result.operation_name
    assert javascript_result["canonicalRequestSha256"] == python_result.canonical_request_sha256


@pytest.mark.parametrize("kind", ["root_total", "category_tree"])
def test_builder_solo_emite_forma_canonica(kind: str) -> None:
    result = validate_la_colonia_structural_request(build_structural_discovery_url(kind))
    assert result.request_kind == kind
    assert result.variables == {
        "query": "",
        "fullText": "",
        "selectedFacets": [],
        "from": 0,
        "to": 0,
    }
    assert len(result.canonical_request_sha256) == 64


def test_kind_desconocido_falla_cerrado() -> None:
    with pytest.raises(LaColoniaEdgeStructuralRequestError) as exc:
        build_structural_discovery_url("inventado")
    assert exc.value.code == "structural_request_kind_invalid"


def test_query_alterada_falla_en_ambos_runtimes() -> None:
    url = build_structural_discovery_url("root_total")
    tampered = _replace_param(url, "query", "query Maliciosa { __typename }")

    with pytest.raises(LaColoniaEdgeStructuralRequestError) as exc:
        validate_la_colonia_structural_request(tampered)
    assert exc.value.code == "structural_graphql_query_mismatch"

    javascript_result = _javascript_validate(tampered)
    assert javascript_result["ok"] is False
    assert javascript_result["code"] == "structural_graphql_query_mismatch"


def test_variables_alteradas_fallan_en_ambos_runtimes() -> None:
    url = build_structural_discovery_url("category_tree")
    altered_variables = json.dumps(
        {
            "query": "",
            "fullText": "",
            "selectedFacets": [],
            "from": 0,
            "to": 1,
        },
        separators=(",", ":"),
    )
    tampered = _replace_param(url, "variables", altered_variables)

    with pytest.raises(LaColoniaEdgeStructuralRequestError) as exc:
        validate_la_colonia_structural_request(tampered)
    assert exc.value.code == "structural_variables_values_invalid"

    javascript_result = _javascript_validate(tampered)
    assert javascript_result["ok"] is False
    assert javascript_result["code"] == "structural_variables_values_invalid"


def test_operacion_y_query_no_se_pueden_mezclar() -> None:
    root = build_structural_discovery_url("root_total")
    tree = validate_la_colonia_structural_request(build_structural_discovery_url("category_tree"))
    parsed_tree = urlsplit(tree.source_url)
    tree_params = dict(parse_qsl(parsed_tree.query, keep_blank_values=True))
    tampered = _replace_param(root, "query", tree_params["query"])

    with pytest.raises(LaColoniaEdgeStructuralRequestError) as exc:
        validate_la_colonia_structural_request(tampered)
    assert exc.value.code == "structural_graphql_query_mismatch"


def test_parametro_duplicado_falla_cerrado() -> None:
    url = build_structural_discovery_url("root_total")
    tampered = f"{url}&workspace=master"
    with pytest.raises(LaColoniaEdgeStructuralRequestError) as exc:
        validate_la_colonia_structural_request(tampered)
    assert exc.value.code == "structural_origin_query_parameter_duplicate"
