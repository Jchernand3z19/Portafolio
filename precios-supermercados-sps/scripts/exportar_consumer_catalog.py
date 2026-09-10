#!/usr/bin/env python3
"""Exporta el catálogo público B2C SPS v3 desde estado aceptado, sin escrituras."""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
import re
import sys
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Iterable, Sequence
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from exportar_modelo_analitico import (  # noqa: E402
    ExportError, QueryBackend, SQLiteBackend, TursoBackend, _scope_predicate, parse_scope,
)
from exportar_rpi_marts import _parse_utc, fetch_freshness  # noqa: E402
from precios_supermercados.price_analytics import ComparisonScope  # noqa: E402
from precios_supermercados.product_homologation_persistence import (  # noqa: E402
    NORMALIZATION_VERSION,
)
SCHEMA, MANIFEST_SCHEMA = "rpi-consumer-catalog/v3", "rpi-consumer-catalog-manifest/v3"
FACETS_SCHEMA, INDEX_SCHEMA = "rpi-consumer-facets/v3", "rpi-consumer-index/v3"
PARTITION_SCHEMA = "rpi-consumer-catalog-partition/v3"
MAX_PARTITION_ROWS = 250
EXPECTED_SCOPE = (
    ("la_colonia", "la_colonia_sps"), ("colonial", "colonial_sps"),
    ("walmart", "walmart_sps"), ("pricesmart", "pricesmart_sps"),
    ("comisariato_los_andes", "comisariato_los_andes_sps"),
)
RETAILER_NAMES = {
    "la_colonia": "La Colonia", "colonial": "Colonial", "walmart": "Walmart",
    "pricesmart": "PriceSmart",
    "comisariato_los_andes": "Los Andes",
}
PUBLIC_COMPARABILITY = {"comparable", "single_source", "individual"}
@dataclass(frozen=True, slots=True)
class VisibleOffer:
    source_product_id: str
    supermarket_id: str
    location_id: str
    product_name: str
    brand: str | None
    presentation: str | None
    current_price_minor: int | None
    reported_regular_price_minor: int | None
    is_promotion: bool | None
    availability: str
    observed_at: str
    canonical_product_id: str | None
    category: str | None
    product_type: str | None
    presentation_dimension: str | None
    presentation_total_base: str | None
    presentation_status: str
    comparison_status: str
def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split())
    return cleaned or None
def _money(minor: int | None) -> str | None:
    if minor is None or minor <= 0:
        return None
    return format(Decimal(minor) / Decimal(100), ".2f")
def _slug(value: str | None) -> str:
    raw = "sin-categoria" if value is None else value
    folded = unicodedata.normalize("NFKD", raw)
    ascii_text = "".join(char for char in folded if not unicodedata.combining(char))
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.casefold()).strip("-")
    return slug or "sin-categoria"
def _format_decimal(value: Decimal) -> str:
    return format(value.normalize(), "f")
def _derived_presentation(offer: VisibleOffer) -> str | None:
    source = _text(offer.presentation)
    if source:
        return source
    if offer.presentation_status not in {"confirmed", "name_only"}:
        return None
    if offer.presentation_dimension is None or offer.presentation_total_base is None:
        return None
    try:
        total = Decimal(offer.presentation_total_base)
    except Exception as exc:  # pragma: no cover - defensive against remote schema drift
        raise ExportError("consumer_catalog_presentation_invalid") from exc
    dimension = offer.presentation_dimension
    if dimension == "volume_ml":
        value, unit = (total / 1000, "L") if total >= 1000 and total % 1000 == 0 else (total, "ml")
    elif dimension == "mass_g":
        value, unit = (total / 1000, "kg") if total >= 1000 and total % 1000 == 0 else (total, "g")
    elif dimension == "ounce":
        value, unit = total, "oz"
    elif dimension == "count":
        value, unit = total, "unidades"
    else:
        return None
    return f"{_format_decimal(value)} {unit}"
def fetch_visible_offers(
    backend: QueryBackend,
    scope: ComparisonScope,
) -> tuple[VisibleOffer, ...]:
    """Lee una fila current por identidad fuente dentro del scope explícito."""
    predicate, scope_args = _scope_predicate(scope)
    cursor_product = -1
    cursor_location = ""
    result: list[VisibleOffer] = []
    seen: set[tuple[int, str]] = set()
    while True:
        rows = backend.query(
            f"""
            SELECT p.product_id,p.supermarket_id,p.name,p.brand,p.presentation,
                   h.location_id,h.current_price_minor,h.reported_regular_price_minor,
                   h.is_promotion,h.availability,h.valid_from_utc,
                   hp.canonical_product_id,hp.category,hp.product_type,
                   hp.presentation_dimension,hp.presentation_total_base,
                   hp.presentation_status,hp.comparison_status,hp.normalization_version
            FROM price_history AS h
            JOIN products AS p
              ON p.product_id=h.product_id AND p.supermarket_id=h.supermarket_id
            JOIN product_homologation_profiles AS hp
              ON hp.product_id=p.product_id AND hp.supermarket_id=p.supermarket_id
            WHERE h.valid_to_utc IS NULL
              AND ({predicate})
              AND (p.product_id>? OR (p.product_id=? AND h.location_id>?))
            ORDER BY p.product_id,h.location_id
            LIMIT 2000
            """,
            (*scope_args, cursor_product, cursor_product, cursor_location),
        )
        if not rows:
            break
        for row in rows:
            (
                product_id, supermarket_id, name, brand, presentation,
                location_id, current_price, regular_price, is_promotion, availability,
                observed_at, canonical_product_id, category, product_type,
                presentation_dimension, presentation_total_base, presentation_status,
                comparison_status, normalization_version,
            ) = row
            key = (product_id, str(location_id))
            if key in seen:
                raise ExportError("consumer_catalog_offer_duplicate")
            seen.add(key)
            if (
                type(product_id) is not int
                or not isinstance(supermarket_id, str)
                or not isinstance(location_id, str)
                or not _text(name)
                or (current_price is not None and type(current_price) is not int)
                or (regular_price is not None and type(regular_price) is not int)
                or (is_promotion is not None and (type(is_promotion) is not int or is_promotion not in {0, 1}))
                or availability not in {"in_stock", "out_of_stock", "unknown"}
                or not _text(observed_at)
                or comparison_status not in {"ready", "review_required", "single_source", "unmapped"}
                or normalization_version != NORMALIZATION_VERSION
            ):
                raise ExportError("consumer_catalog_offer_invalid")
            result.append(
                VisibleOffer(
                    source_product_id=f"{supermarket_id}:{product_id}",
                    supermarket_id=supermarket_id,
                    location_id=location_id,
                    product_name=_text(name) or "",
                    brand=_text(brand),
                    presentation=_text(presentation),
                    current_price_minor=current_price,
                    reported_regular_price_minor=regular_price,
                    is_promotion=None if is_promotion is None else bool(is_promotion),
                    availability=availability,
                    observed_at=_text(observed_at) or "",
                    canonical_product_id=_text(canonical_product_id),
                    category=_text(category),
                    product_type=_text(product_type),
                    presentation_dimension=_text(presentation_dimension),
                    presentation_total_base=_text(presentation_total_base),
                    presentation_status=str(presentation_status),
                    comparison_status=str(comparison_status),
                )
            )
        cursor_product = int(rows[-1][0])
        cursor_location = str(rows[-1][5])
        if len(rows) < 2000:
            break
    return tuple(result)
def _row_id(prefix: str, value: str) -> str:
    return f"{prefix}-{hashlib.sha256(value.encode('utf-8')).hexdigest()[:24]}"
def _category_key(value: str | None) -> str:
    identity = "__unknown__" if value is None else value
    return f"{_slug(value)}-{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:8]}"
def _search_prefix(value: object) -> str:
    folded = unicodedata.normalize("NFKD", str(value or ""))
    normalized = re.sub(r"[^a-z0-9]+", "", "".join(char for char in folded if not unicodedata.combining(char)).casefold())
    return normalized[:2] or "__"
def _identity_groups(offers: Iterable[VisibleOffer]) -> list[tuple[str, list[VisibleOffer]]]:
    """Agrupa sólo IDs canónicos ready sin colisiones por supermercado."""
    values = tuple(offers)
    candidates: dict[str, list[VisibleOffer]] = defaultdict(list)
    individual: list[VisibleOffer] = []
    for offer in values:
        if offer.comparison_status == "ready" and offer.canonical_product_id:
            candidates[offer.canonical_product_id].append(offer)
        else:
            individual.append(offer)
    groups: list[tuple[str, list[VisibleOffer]]] = []
    for canonical_id, grouped in candidates.items():
        retailers = [offer.supermarket_id for offer in grouped]
        if len(grouped) >= 2 and len(retailers) == len(set(retailers)):
            groups.append(("comparable", grouped))
        else:
            individual.extend(grouped)
    groups.extend(("single_source" if offer.comparison_status == "single_source" else "individual", [offer]) for offer in individual)
    if sum(len(group) for _, group in groups) != len(values):
        raise ExportError("consumer_catalog_identity_partition_invalid")
    return groups
def _relative_states(
    mode: str,
    offers: Sequence[VisibleOffer],
    freshness_by_scope: dict[tuple[str, str], str],
) -> dict[str, str]:
    result = {offer.source_product_id: "neutral" for offer in offers}
    valid = [
        offer for offer in offers
        if offer.current_price_minor is not None
        and offer.current_price_minor > 0
        and offer.availability != "out_of_stock"
    ]
    if (
        mode != "comparable"
        or len(valid) < 2
        or any(freshness_by_scope[(offer.supermarket_id, offer.location_id)] != "FRESH" for offer in valid)
    ):
        return result
    prices = [offer.current_price_minor for offer in valid]
    if len(set(prices)) == 1:
        for offer in valid:
            result[offer.source_product_id] = "equivalent"
        return result
    minimum, maximum = min(prices), max(prices)
    for offer in valid:
        price = offer.current_price_minor
        result[offer.source_product_id] = "best" if price == minimum else "highest" if price == maximum else "intermediate"
    return result
def _representative(group: Sequence[VisibleOffer]) -> VisibleOffer:
    return sorted(
        group,
        key=lambda offer: (
            offer.product_type is None,
            offer.category is None,
            offer.brand is None,
            _derived_presentation(offer) is None,
            len(offer.product_name),
            offer.supermarket_id,
        ),
    )[0]
def build_rows(
    offers: Iterable[VisibleOffer],
    freshness_by_scope: dict[tuple[str, str], str],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for mode, group in _identity_groups(offers):
        representative = _representative(group)
        canonical_id = representative.canonical_product_id if mode == "comparable" else None
        identity_value = canonical_id or representative.source_product_id
        states = _relative_states(mode, group, freshness_by_scope)
        public_offers = []
        for offer in sorted(group, key=lambda item: EXPECTED_SCOPE.index((item.supermarket_id, item.location_id))):
            freshness = freshness_by_scope[(offer.supermarket_id, offer.location_id)]
            public_offers.append(
                {
                    "source_product_id": offer.source_product_id,
                    "supermarket_id": offer.supermarket_id,
                    "location_id": offer.location_id,
                    "current_price": _money(offer.current_price_minor),
                    "reported_regular_price": _money(offer.reported_regular_price_minor),
                    "is_promotion": offer.is_promotion,
                    "availability": offer.availability,
                    "observed_at": offer.observed_at,
                    "freshness_status": freshness,
                    "relative_price_state": states[offer.source_product_id],
                }
            )
        category = representative.category
        row = {
            "row_id": _row_id("product" if canonical_id else "source", identity_value),
            "canonical_product_id": canonical_id,
            "comparability": mode,
            "category": category,
            "product_type": representative.product_type,
            "product_name": representative.product_name,
            "brand": representative.brand,
            "presentation": _derived_presentation(representative),
            "offers": public_offers,
        }
        if mode not in PUBLIC_COMPARABILITY:
            raise ExportError("consumer_catalog_public_comparability_invalid")
        rows.append(row)
    rows.sort(
        key=lambda row: tuple((str(row.get(key) or "")).casefold() for key in ("category", "product_type", "brand", "presentation", "product_name", "row_id"))
    )
    if len({str(row["row_id"]) for row in rows}) != len(rows):
        raise ExportError("consumer_catalog_row_id_collision")
    return rows
def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")
def _atomic_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(content)
    temporary.replace(path)
def _file_metadata(root: Path, relative: str) -> dict[str, object]:
    content = (root / relative).read_bytes()
    return {
        "path": relative,
        "sha256": hashlib.sha256(content).hexdigest(),
        "bytes": len(content),
        "gzip_bytes": len(gzip.compress(content, mtime=0)),
    }
def export_consumer_catalog(
    backend: QueryBackend,
    scope: ComparisonScope,
    output_directory: Path,
    *,
    as_of_utc: datetime,
    freshness_window: timedelta,
    require_products: bool = False,
) -> dict[str, object]:
    if tuple(scope.locations) != EXPECTED_SCOPE:
        raise ExportError("consumer_catalog_sps_scope_invalid")
    offers = fetch_visible_offers(backend, scope)
    retailer_offer_counts = {
        supermarket_id: sum(offer.supermarket_id == supermarket_id for offer in offers)
        for supermarket_id, _ in scope.locations
    }
    if require_products and (not offers or any(count == 0 for count in retailer_offer_counts.values())):
        raise ExportError("consumer_catalog_missing_visible_retailer")
    freshness = fetch_freshness(
        backend,
        scope,
        as_of_utc=as_of_utc,
        freshness_window=freshness_window,
    )
    freshness_by_scope = {
        (item.source_id, item.location_id): item.freshness_status.value for item in freshness
    }
    rows = build_rows(offers, freshness_by_scope)
    output_directory.mkdir(parents=True, exist_ok=True)
    categories: dict[str | None, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        categories[row["category"] if isinstance(row["category"], str) else None].append(row)
    partition_paths: list[str] = []
    for category, category_rows in sorted(categories.items(), key=lambda item: (item[0] is None, str(item[0]).casefold())):
        slug = _category_key(category)
        for number, start in enumerate(range(0, len(category_rows), MAX_PARTITION_ROWS), start=1):
            chunk = category_rows[start : start + MAX_PARTITION_ROWS]
            relative = f"catalog/{slug}/part-{number:03d}.json"
            _atomic_bytes(
                output_directory / relative,
                _json_bytes({"schema": PARTITION_SCHEMA, "partition": relative, "row_count": len(chunk), "rows": chunk}),
            )
            partition_paths.append(relative)
            for row in chunk:
                row["_partition"] = relative
    index_paths: list[str] = []
    category_facets: list[dict[str, object]] = []
    for category, category_rows in sorted(categories.items(), key=lambda item: (item[0] is None, str(item[0]).casefold())):
        category_key = _category_key(category)
        if category is None:
            prefix_groups: dict[str, list[dict[str, object]]] = defaultdict(list)
            for row in category_rows:
                prefix_groups[_search_prefix(row["product_name"])].append(row)
            search_indexes = []
            for prefix, group in sorted(prefix_groups.items()):
                relative = f"index/{category_key}/search-{prefix}.json"
                entries = [{key: row[key] for key in ("row_id", "product_name", "brand", "presentation")} | {"partition": row["_partition"]} for row in group]
                _atomic_bytes(output_directory / relative, _json_bytes({"schema": INDEX_SCHEMA, "category": None, "search_prefix": prefix, "row_count": len(entries), "rows": entries}))
                index_paths.append(relative)
                search_indexes.append({"prefix": prefix, "path": relative, "row_count": len(entries)})
            category_facets.append({"value": None, "label": "Sin categoría normalizada", "row_count": len(category_rows), "navigation": "search", "search_indexes": search_indexes})
            continue
        types: dict[str | None, list[dict[str, object]]] = defaultdict(list)
        for row in category_rows:
            types[row["product_type"] if isinstance(row["product_type"], str) else None].append(row)
        type_facets = []
        for product_type, group in sorted(types.items(), key=lambda item: (item[0] is None, str(item[0]).casefold())):
            relative = f"index/{category_key}/{_category_key(product_type)}.json"
            entries = [{key: row[key] for key in ("row_id", "product_name", "brand", "presentation")} | {"partition": row["_partition"]} for row in group]
            _atomic_bytes(output_directory / relative, _json_bytes({"schema": INDEX_SCHEMA, "category": category, "product_type": product_type, "row_count": len(entries), "rows": entries}))
            index_paths.append(relative)
            type_facets.append({"value": product_type, "label": product_type or "Sin tipo normalizado", "row_count": len(entries), "index_path": relative})
        category_facets.append({"value": category, "label": category, "row_count": len(category_rows), "navigation": "facets", "product_types": type_facets})
    for row in rows:
        row.pop("_partition", None)
    def covered(field: str) -> int:
        return sum(bool(row.get(field)) for row in rows)
    facets = {
        "schema": FACETS_SCHEMA,
        "location": {"city": "San Pedro Sula", "country_code": "HN"},
        "row_count": len(rows),
        "coverage": {
            field: {"known": covered(field), "unknown": len(rows) - covered(field)}
            for field in ("category", "product_type", "brand", "presentation")
        },
        "categories": category_facets,
    }
    _atomic_bytes(output_directory / "facets-sps.json", _json_bytes(facets))
    data_files = ["facets-sps.json", *index_paths, *partition_paths]
    metadata = [_file_metadata(output_directory, relative) for relative in data_files]
    offer_count = sum(len(row["offers"]) for row in rows)
    mode_counts = {
        mode: sum(row["comparability"] == mode for row in rows)
        for mode in sorted(PUBLIC_COMPARABILITY)
    }
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "catalog_schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "as_of": as_of_utc.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_backend": backend.kind,
        "location": {"city": "San Pedro Sula", "country_code": "HN"},
        "scope": [
            {"supermarket_id": supermarket_id, "location_id": location_id}
            for supermarket_id, location_id in scope.locations
        ],
        "retailers": [
            {"supermarket_id": supermarket_id, "location_id": location_id, "name": RETAILER_NAMES[supermarket_id]}
            for supermarket_id, location_id in scope.locations
        ],
        "visibility_policy": "accepted_current_source_offers_in_sps_scope",
        "comparison_policy": "persisted_ready_identity_without_retailer_collision_and_fresh_prices",
        "visible_rows": len(rows),
        "source_offers": offer_count,
        "retailer_offer_counts": retailer_offer_counts,
        "comparability_counts": mode_counts,
        "partition_count": len(partition_paths),
        "max_partition_rows": MAX_PARTITION_ROWS,
        "initial_files": ["facets-sps.json"],
        "files": metadata,
        "initial_payload": {
            "bytes": next(item["bytes"] for item in metadata if item["path"] == "facets-sps.json"),
            "gzip_bytes": next(item["gzip_bytes"] for item in metadata if item["path"] == "facets-sps.json"),
            "request_count": 2,
        },
        "public_boundary": {
            "direct_turso_reads": 0,
            "contains_business_mart": False,
            "contains_raw": False,
            "contains_review_queue": False,
        },
        "source_freshness": [
            {
                "supermarket_id": item.source_id,
                "location_id": item.location_id,
                "status": item.freshness_status.value,
                "last_successful_run": item.last_successful_run_id,
                "last_successful_at": None if item.observed_at_utc is None else item.observed_at_utc.isoformat().replace("+00:00", "Z"),
                "data_age_hours": item.data_age_hours,
            }
            for item in freshness
        ],
    }
    _atomic_bytes(output_directory / "manifest.json", _json_bytes(manifest))
    return manifest
def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    source = result.add_mutually_exclusive_group(required=True)
    source.add_argument("--sqlite", type=Path)
    source.add_argument("--turso", action="store_true")
    result.add_argument("--scope", action="append", required=True)
    result.add_argument("--output-directory", type=Path, required=True)
    result.add_argument("--as-of-utc")
    result.add_argument("--freshness-hours", type=int, default=48)
    result.add_argument("--require-products", action="store_true")
    return result
def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.freshness_hours <= 0:
        raise ExportError("consumer_catalog_freshness_hours_invalid")
    as_of = datetime.now(timezone.utc) if args.as_of_utc is None else _parse_utc(args.as_of_utc, "consumer_catalog_as_of_invalid")
    scope = parse_scope(args.scope)
    if args.sqlite is not None:
        if not args.sqlite.is_file():
            raise ExportError("sqlite_file_missing")
        backend = SQLiteBackend(args.sqlite)
    else:
        import os
        backend = TursoBackend(os.environ.get("TURSO_DATABASE_URL", ""), os.environ.get("TURSO_AUTH_TOKEN", ""))
    try:
        manifest = export_consumer_catalog(
            backend,
            scope,
            args.output_directory,
            as_of_utc=as_of,
            freshness_window=timedelta(hours=args.freshness_hours),
            require_products=args.require_products,
        )
    finally:
        backend.close()
    print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
