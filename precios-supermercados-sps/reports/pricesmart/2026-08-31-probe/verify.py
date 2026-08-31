#!/usr/bin/env python3
"""Reproduce la evidencia publicada del probe PriceSmart sin tráfico de red."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import tarfile
from pathlib import Path

REPORT = Path(__file__).resolve().parent
ARCHIVE = REPORT / "raw-capture.tar.gz"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _match_balanced(text: str, position: int, opening: str, closing: str) -> int:
    depth = 1
    quote = None
    escaped = False
    for index in range(position + 1, len(text)):
        char = text[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        elif char in "'\"`":
            quote = char
        elif char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                return index
    raise ValueError("unbalanced_nuxt_state")


def _split_arguments(text: str) -> list[str]:
    arguments = []
    last = 0
    stack = []
    quote = None
    escaped = False
    for index, char in enumerate(text):
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        elif char in "'\"`":
            quote = char
        elif char in "([{":
            stack.append(char)
        elif char in ")]}":
            stack.pop()
        elif char == "," and not stack:
            arguments.append(text[last:index].strip())
            last = index + 1
    arguments.append(text[last:].strip())
    return arguments


def _literal(value: str):
    if value == "void 0":
        return None
    if value == "!0":
        return True
    if value == "!1":
        return False
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def _nuxt_properties(html: bytes, keys: list[str]) -> dict:
    text = html.decode("utf-8", "replace")
    marker = "window.__NUXT__=(function("
    start = text.index(marker) + len(marker)
    params_end = _match_balanced(text, start - 1, "(", ")")
    parameters = [item.strip() for item in text[start:params_end].split(",")]
    body_start = text.index("{", params_end)
    body_end = _match_balanced(text, body_start, "{", "}")
    args_end = _match_balanced(text, body_end + 1, "(", ")")
    arguments = _split_arguments(text[body_end + 2 : args_end])
    if len(parameters) != len(arguments):
        raise ValueError("nuxt_parameter_argument_mismatch")
    values = {name: _literal(value) for name, value in zip(parameters, arguments)}
    body = text[body_start : body_end + 1]
    result = {}
    for key in keys:
        match = re.search(
            rf"(?<![A-Za-z0-9_$]){re.escape(key)}:([A-Za-z_$][A-Za-z0-9_$]*)",
            body,
        )
        if not match:
            raise ValueError(f"missing_nuxt_property:{key}")
        result[key] = values[match.group(1)]
    return result


def reproduce(archive_path: Path = ARCHIVE) -> dict:
    archive_bytes = archive_path.read_bytes()
    with tarfile.open(archive_path, "r:gz") as archive:
        members = {member.name: member for member in archive.getmembers() if member.isfile()}
        if any(name.startswith("/") or ".." in Path(name).parts for name in members):
            raise ValueError("unsafe_archive_path")
        payload = {name: archive.extractfile(member).read() for name, member in members.items()}

    manifest = json.loads(payload["manifest.json"])
    ledger = json.loads(payload["ledger.json"])
    if _sha256(payload["ledger.json"]) != manifest["ledger_sha256"]:
        raise ValueError("ledger_sha256_mismatch")
    for item in manifest["files"]:
        if _sha256(payload[item["path"]]) != item["published_sha256"]:
            raise ValueError(f"published_sha256_mismatch:{item['path']}")

    starts = [dt.datetime.fromisoformat(row["started_at"].replace("Z", "+00:00")) for row in ledger]
    finishes = [dt.datetime.fromisoformat(row["finished_at"].replace("Z", "+00:00")) for row in ledger]
    gaps = [(starts[index] - finishes[index - 1]).total_seconds() for index in range(1, len(ledger))]
    if any(row["method"] != "GET" for row in ledger):
        raise ValueError("non_get_request_in_capture")
    if any(gap < 1 for gap in gaps):
        raise ValueError("pacing_violation")
    if len(ledger) > manifest["budget"]["get_total_max"]:
        raise ValueError("get_budget_exceeded")

    search_bags = payload["raw/02-search_bolsas_retry.html"]
    search_vegetables = payload["raw/03-search_vegetables_page3.html"]
    product = payload["raw/04-product_516411.html"]
    vendor = payload["raw/08-asset_commerce_vendor.html"]
    config = _nuxt_properties(
        product,
        [
            "graphql_baseurl",
            "discoveryAccountId",
            "discoveryRealm",
            "graphqlTenantName",
            "externalLocale",
            "discoveryDomainKey",
            "discoveryViewId",
            "brDiscoveryAuthKey",
            "brDiscoveryCountryClubParams",
            "brDiscoveryCountryParams",
            "brDiscoveryFlParam",
            "clubs",
            "defaultClub",
            "territoryId",
            "alpha3",
        ],
    )
    clubs = json.loads(config["clubs"])
    club_rows = [
        {
            "source_club_key": str(club["id"]),
            "name": club["description"],
            "ecommerce_enabled": club["ecommerceEnabled"] == "true",
        }
        for club in clubs
    ]
    expected_clubs = [("6602", "Florencia"), ("6603", "San Pedro Sula"), ("6604", "El Sauce")]
    if [(row["source_club_key"], row["name"]) for row in club_rows] != expected_clubs:
        raise ValueError("unexpected_honduras_clubs")
    if config["brDiscoveryAuthKey"] != "[REDACTED:brDiscoveryAuthKey]":
        raise ValueError("public_auth_key_not_redacted")

    operations = ["channels", "productProjectionsSearch", "inventoryEntries", "products"]
    missing_operations = [name for name in operations if f"query {name}".encode() not in vendor]
    if missing_operations:
        raise ValueError(f"missing_graphql_operations:{missing_operations}")
    required_schema = [
        b"fragment DefaultProductPrice on ProductPrice",
        b"discounted",
        b"currencyCode",
        b"centAmount",
        b"fractionDigits",
        b"isActive",
        b"channelId",
        b"availableQuantity",
    ]
    if any(field not in vendor for field in required_schema):
        raise ValueError("incomplete_graphql_price_or_availability_schema")

    return {
        "schema_version": 1,
        "authorization": manifest["authorization"],
        "budget": manifest["budget"],
        "capture": {
            "get_attempts": len(ledger),
            "http_200": sum(row["status"] == 200 for row in ledger),
            "pre_response_errors": sum(row["status"] is None for row in ledger),
            "redirect_responses": sum(row["status"] in {301, 302, 303, 307, 308} for row in ledger),
            "transient_retries": 1,
            "asset_gets": sum("/_nuxt/" in row["url"] for row in ledger),
            "concurrency": 1,
            "minimum_observed_gap_seconds": min(gaps),
            "elapsed_seconds": (finishes[-1] - starts[0]).total_seconds(),
            "closed_reason": manifest["closed_reason"],
        },
        "get_surface": {
            "frontend": "Nuxt_Vue_Storefront_2",
            "requested_searches_bound_to_response": False,
            "mismatches": [
                {"requested": "q=Bolsas", "observed_embedded_query": "q=Huevos"},
                {"requested": "page=3&q=Vegetables", "observed_embedded_query": "page=1&q=jabon dove"},
            ],
            "mismatch_assertions": {
                "bags_response_contains_huevos": b"q=Huevos" in search_bags,
                "bags_response_contains_bolsas": b"q=Bolsas" in search_bags,
                "vegetables_response_contains_jabon_dove": b"jabon%20dove" in search_vegetables,
                "vegetables_response_contains_vegetables": b"Vegetables" in search_vegetables,
            },
            "product_page": {
                "requested_sku": "516411",
                "identity_and_title_present": b"Mountain Dew Soda Cans 24 Units / 355 mL" in product,
                "numeric_price_407_95_present_in_get_body": b"407.95" in product,
            },
        },
        "structured_source": {
            "kind": "GraphQL_client_contract_embedded_in_public_Nuxt_state_and_assets",
            "base_url": config["graphql_baseurl"],
            "tenant": config["graphqlTenantName"],
            "locale": config["externalLocale"],
            "country_alpha3": config["alpha3"],
            "territory_id": config["territoryId"],
            "discovery_account_id": config["discoveryAccountId"],
            "discovery_realm": config["discoveryRealm"],
            "discovery_domain_key": config["discoveryDomainKey"],
            "discovery_view_id": config["discoveryViewId"],
            "public_auth_config_redacted": True,
            "operations_observed": operations,
            "country_club_params": config["brDiscoveryCountryClubParams"].split(","),
            "country_params": config["brDiscoveryCountryParams"].split(","),
            "fields": config["brDiscoveryFlParam"].split(","),
            "price_contract": {
                "effective_candidate": "discounted.value_when_active_else_value",
                "regular_candidate": "value_when_discounted_is_present",
                "promotion_candidate": "discount.isActive",
                "money": ["currencyCode", "centAmount", "fractionDigits"],
                "status": "schema_observed_response_not_yet_called",
            },
        },
        "clubs": {
            "default_source_club_key": config["defaultClub"],
            "rows": club_rows,
            "price_comparable_skus": 0,
            "price_differences": None,
            "reported_regular_price_differences": None,
            "promotion_differences": None,
            "availability_only_differences": None,
        },
        "decision": {
            "candidate": "GO_TO_READ_ONLY_GRAPHQL_EXTENSION_GATE",
            "probe_status": "PAUSED_PENDING_EXPLICIT_POST_AND_DOMAIN_AUTHORIZATION",
            "reason": "public_get_proves_contract_and_clubs_but_not_a_price_response_or_context_binding",
            "production_scraper": False,
            "full_crawl": False,
            "persistence": False,
            "model_change": False,
            "turso_access": False,
        },
        "redactions": manifest["redaction_totals"],
        "raw_archive": {
            "bytes": len(archive_bytes),
            "sha256": _sha256(archive_bytes),
            "published_files": len(manifest["files"]),
        },
    }


if __name__ == "__main__":
    print(json.dumps(reproduce(), ensure_ascii=False, indent=2, sort_keys=True))
