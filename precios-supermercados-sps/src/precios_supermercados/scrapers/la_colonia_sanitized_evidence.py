"""Contrato sanitizado de evidencia operativa para La Colonia SPS.

La extracción fuente contiene detalles útiles para explicar disponibilidad y
normalización, pero también ``source_url`` y contexto técnico que no deben formar
parte del artifact descargable. Este módulo crea una proyección explícita por
whitelist: no copia ``raw_values`` completos, cookies, headers, sesión, regionId
ni URLs GraphQL.

No hace red, no persiste y no concede autoridad comercial.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlsplit

from precios_supermercados.models import RawProduct

OPERATIONAL_ARTIFACT_SCHEMA_VERSION = "8"

SANITIZED_PRODUCT_FIELDS = (
    "source_key_type",
    "source_key",
    "source_name",
    "product_url",
    "brand",
    "presentation",
    "category",
    "subcategory",
    "product_id",
    "item_id",
    "reference",
    "ean",
    "current_price",
    "reported_regular_price",
    "source_list_price",
    "is_promotion",
    "promotion_evidence",
    "availability",
    "availability_evidence",
    "available_quantity",
    "measurement_unit",
    "unit_multiplier",
    "weighted_product",
)

ALLOWED_AVAILABILITY_EVIDENCE = frozenset(
    {
        "price_positive_quantity_positive",
        "price_positive_quantity_zero",
        "price_absent_quantity_zero",
        "insufficient_evidence",
    }
)


class SanitizedEvidenceError(ValueError):
    """La observación no puede proyectarse al contrato público v8."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _text(value: object) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _decimal_text(value: object, *, allow_zero: bool = False) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value).strip())
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise SanitizedEvidenceError("decimal_evidence_invalid") from exc
    if not result.is_finite() or (result < 0 if allow_zero else result <= 0):
        raise SanitizedEvidenceError("decimal_evidence_invalid")
    rendered = format(result.normalize(), "f")
    return "0" if rendered in {"", "-0"} else rendered


def _public_product_url(value: object) -> str:
    text = _text(value)
    if text is None:
        raise SanitizedEvidenceError("product_url_missing")
    parsed = urlsplit(text)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "www.lacolonia.com"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port is not None
        or parsed.query
        or parsed.fragment
        or not parsed.path.endswith("/p")
    ):
        raise SanitizedEvidenceError("product_url_not_public_canonical")
    return text


def _promotion_evidence(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise SanitizedEvidenceError("promotion_evidence_invalid")
    result: list[str] = []
    for item in value:
        text = _text(item)
        if text is None:
            raise SanitizedEvidenceError("promotion_evidence_invalid")
        result.append(text)
    return list(dict.fromkeys(result))


def sanitize_operational_product(raw: RawProduct) -> dict[str, Any]:
    """Proyecta un ``RawProduct`` a evidencia descargable mínima y explicable.

    Sólo se leen campos enumerados de ``raw_values``. ``raw.source_url`` se omite
    intencionalmente porque puede contener variables/contexto del request. La URL
    pública canónica del producto sí se conserva como evidencia navegable.
    """

    if not isinstance(raw, RawProduct):
        raise SanitizedEvidenceError("raw_product_required")

    values: Mapping[str, Any] = raw.raw_values
    availability = _text(values.get("availability"))
    evidence = _text(values.get("availability_evidence"))
    if evidence not in ALLOWED_AVAILABILITY_EVIDENCE:
        raise SanitizedEvidenceError("availability_evidence_invalid")

    is_promotion = values.get("is_promotion")
    weighted_product = values.get("weighted_product")
    if not isinstance(is_promotion, bool):
        raise SanitizedEvidenceError("is_promotion_invalid")
    if not isinstance(weighted_product, bool):
        raise SanitizedEvidenceError("weighted_product_invalid")

    result = {
        "source_key_type": raw.source_key_type.value,
        "source_key": raw.source_key,
        "source_name": raw.source_name,
        "product_url": _public_product_url(raw.product_url),
        "brand": raw.source_brand,
        "presentation": raw.source_presentation,
        "category": raw.source_category,
        "subcategory": _text(values.get("subcategory")),
        "product_id": _text(values.get("product_id")),
        "item_id": _text(values.get("item_id")),
        "reference": _text(values.get("reference")),
        "ean": _text(values.get("ean")),
        "current_price": _decimal_text(values.get("current_price")),
        "reported_regular_price": _decimal_text(
            values.get("reported_regular_price")
        ),
        "source_list_price": _decimal_text(values.get("source_list_price")),
        "is_promotion": is_promotion,
        "promotion_evidence": _promotion_evidence(values.get("promotion_evidence")),
        "availability": availability,
        "availability_evidence": evidence,
        "available_quantity": _decimal_text(
            values.get("available_quantity"), allow_zero=True
        ),
        "measurement_unit": _text(values.get("measurement_unit")),
        "unit_multiplier": _decimal_text(values.get("unit_multiplier")),
        "weighted_product": weighted_product,
    }

    if tuple(result) != SANITIZED_PRODUCT_FIELDS:
        raise SanitizedEvidenceError("sanitized_product_schema_internal_mismatch")
    return result
