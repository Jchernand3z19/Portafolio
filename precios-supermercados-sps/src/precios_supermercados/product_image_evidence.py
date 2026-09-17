"""Contrato determinista para evidencia de imágenes por oferta fuente.

Las imágenes son evidencia auxiliar de homologación. No crean ni confirman por sí
solas una identidad canónica y viven fuera de la tabla comercial ``products``.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from typing import Any
from urllib.parse import urlsplit

IMAGE_CAPTURE_STATUSES = frozenset({"complete", "unsupported"})
IMAGE_ROW_KEYS = frozenset(
    {
        "source_key_type",
        "source_key",
        "image_url",
        "source_position",
        "is_primary",
        "source_image_id",
    }
)


class ProductImageEvidenceError(ValueError):
    """La galería fuente no satisface el contrato de evidencia."""


def _identity(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProductImageEvidenceError(f"{field}_invalid")
    return value.strip()


def _https_url(value: object) -> str:
    if not isinstance(value, str) or value != value.strip():
        raise ProductImageEvidenceError("image_url_invalid")
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username is not None:
        raise ProductImageEvidenceError("image_url_invalid")
    return value


def build_product_image_rows(
    *,
    source_key_type: str,
    source_key: str,
    images: Iterable[tuple[str, str | None]],
) -> list[dict[str, object]]:
    """Normaliza una galería ya ordenada y elimina URLs repetidas conservando orden."""

    key_type = _identity(source_key_type, "source_key_type")
    key = _identity(source_key, "source_key")
    seen: set[str] = set()
    rows: list[dict[str, object]] = []
    for url_value, image_id_value in images:
        url = _https_url(url_value)
        if url in seen:
            continue
        seen.add(url)
        image_id = None
        if image_id_value is not None:
            image_id = _identity(image_id_value, "source_image_id")
        position = len(rows)
        rows.append(
            {
                "source_key_type": key_type,
                "source_key": key,
                "image_url": url,
                "source_position": position,
                "is_primary": position == 0,
                "source_image_id": image_id,
            }
        )
    return rows


def image_pairs_from_mappings(
    values: object,
    *,
    url_key: str,
    id_key: str | None = None,
    position_key: str | None = None,
) -> list[tuple[str, str | None]]:
    """Extrae URL/id de una galería fuente y respeta su posición declarada."""

    if values is None:
        return []
    if not isinstance(values, list):
        raise ProductImageEvidenceError("images_invalid")
    indexed: list[tuple[int, int, str, str | None]] = []
    for index, value in enumerate(values):
        if not isinstance(value, Mapping):
            raise ProductImageEvidenceError("image_entry_invalid")
        url = _https_url(value.get(url_key))
        image_id_value = value.get(id_key) if id_key is not None else None
        image_id = None if image_id_value is None else str(image_id_value).strip()
        if image_id == "":
            raise ProductImageEvidenceError("source_image_id_invalid")
        declared = value.get(position_key) if position_key is not None else None
        if declared is None:
            order = index
        elif type(declared) is int and declared >= 0:
            order = declared
        elif isinstance(declared, str) and declared.isdigit():
            order = int(declared)
        else:
            raise ProductImageEvidenceError("image_position_invalid")
        indexed.append((order, index, url, image_id))
    indexed.sort(key=lambda item: (item[0], item[1]))
    return [(url, image_id) for _, _, url, image_id in indexed]


def validate_snapshot_images(
    snapshot: Mapping[str, Any],
    *,
    product_identities: set[tuple[str, str]],
) -> tuple[dict[str, object], ...]:
    """Valida la extensión opcional y retrocompatible de imágenes del snapshot."""

    has_status = "image_capture_status" in snapshot
    has_rows = "product_images" in snapshot
    if not has_status and not has_rows:
        return ()
    if has_status != has_rows:
        raise ProductImageEvidenceError("image_contract_partial")
    status = snapshot.get("image_capture_status")
    rows = snapshot.get("product_images")
    if status not in IMAGE_CAPTURE_STATUSES or not isinstance(rows, list):
        raise ProductImageEvidenceError("image_contract_invalid")
    if status == "unsupported" and rows:
        raise ProductImageEvidenceError("unsupported_images_not_empty")

    result: list[dict[str, object]] = []
    grouped: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    unique_urls: set[tuple[str, str, str]] = set()
    for raw in rows:
        if not isinstance(raw, dict) or set(raw) != IMAGE_ROW_KEYS:
            raise ProductImageEvidenceError("image_row_schema_invalid")
        key_type = _identity(raw["source_key_type"], "source_key_type")
        key = _identity(raw["source_key"], "source_key")
        identity = (key_type, key)
        if identity not in product_identities:
            raise ProductImageEvidenceError("image_product_unknown")
        url = _https_url(raw["image_url"])
        position = raw["source_position"]
        primary = raw["is_primary"]
        image_id = raw["source_image_id"]
        if type(position) is not int or position < 0 or type(primary) is not bool:
            raise ProductImageEvidenceError("image_position_invalid")
        if image_id is not None:
            image_id = _identity(image_id, "source_image_id")
        unique_key = (key_type, key, url)
        if unique_key in unique_urls:
            raise ProductImageEvidenceError("image_url_duplicate")
        unique_urls.add(unique_key)
        row = {
            "source_key_type": key_type,
            "source_key": key,
            "image_url": url,
            "source_position": position,
            "is_primary": primary,
            "source_image_id": image_id,
        }
        grouped[identity].append(row)
        result.append(row)

    for gallery in grouped.values():
        gallery.sort(key=lambda row: int(row["source_position"]))
        if [row["source_position"] for row in gallery] != list(range(len(gallery))):
            raise ProductImageEvidenceError("image_positions_not_contiguous")
        if [row["is_primary"] for row in gallery] != [True] + [False] * (len(gallery) - 1):
            raise ProductImageEvidenceError("image_primary_invalid")
    return tuple(result)


def collect_detail_image_rows(
    products: Iterable[Mapping[str, Any]],
    source_details: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, object]]:
    """Reúne las galerías normalizadas guardadas temporalmente en source_details."""

    result: list[dict[str, object]] = []
    for product in products:
        key = _identity(product.get("source_key"), "source_key")
        detail = source_details.get(key)
        if not isinstance(detail, Mapping):
            raise ProductImageEvidenceError("source_details_missing")
        rows = detail.get("product_images", [])
        if not isinstance(rows, list):
            raise ProductImageEvidenceError("detail_product_images_invalid")
        result.extend(rows)
    return result


def detail_image_extension(
    products: Iterable[Mapping[str, Any]],
    source_details: Mapping[str, Mapping[str, Any]],
) -> dict[str, object]:
    """Extensión lista para incluir en un snapshot completo."""

    return {
        "image_capture_status": "complete",
        "product_images": collect_detail_image_rows(products, source_details),
    }


def vtex_product_image_rows(products: Iterable[Mapping[str, Any]]) -> list[dict[str, object]]:
    """Extrae todas las galerías por SKU de un resultado VTEX."""

    result: list[dict[str, object]] = []
    for product in products:
        items = product.get("items")
        if not isinstance(items, list):
            raise ProductImageEvidenceError("vtex_items_invalid")
        for item in items:
            if not isinstance(item, Mapping):
                raise ProductImageEvidenceError("vtex_item_invalid")
            source_key = _identity(item.get("itemId"), "source_key")
            result.extend(build_product_image_rows(
                source_key_type="item_id",
                source_key=source_key,
                images=image_pairs_from_mappings(
                    item.get("images"), url_key="imageUrl", id_key="imageId"
                ),
            ))
    return result


def scalar_detail_image_rows(
    products: Iterable[Mapping[str, Any]],
    source_details: Mapping[str, Mapping[str, Any]],
    *,
    field: str = "image_url",
) -> list[dict[str, object]]:
    """Convierte una imagen escalar por oferta al contrato uno-a-muchos."""

    result: list[dict[str, object]] = []
    for product in products:
        key_type = _identity(product.get("source_key_type"), "source_key_type")
        key = _identity(product.get("source_key"), "source_key")
        detail = source_details.get(key)
        if not isinstance(detail, Mapping):
            raise ProductImageEvidenceError("source_details_missing")
        value = detail.get(field)
        pairs = [] if value is None else [(_https_url(value), None)]
        result.extend(build_product_image_rows(
            source_key_type=key_type, source_key=key, images=pairs
        ))
    return result
