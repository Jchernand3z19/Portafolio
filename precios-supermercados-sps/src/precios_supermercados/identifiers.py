"""Identificadores deterministas y hash de estado para ofertas."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from decimal import Decimal
from typing import Any, Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .enums import SourceKeyType
from .models import NormalizedOffer

_TRACKING_KEYS = {
    "fbclid",
    "gclid",
    "msclkid",
    "mc_cid",
    "mc_eid",
    "ref",
    "referrer",
}
_TRACKING_PREFIXES = ("utm_",)
_WHITESPACE = re.compile(r"\s+")


def canonicalize_text(value: str | None) -> str | None:
    """Normaliza Unicode, espacios y mayúsculas sin alterar el significado."""

    if value is None:
        return None
    normalized = unicodedata.normalize("NFKC", str(value))
    collapsed = _WHITESPACE.sub(" ", normalized).strip().casefold()
    return collapsed or None


def canonicalize_url(value: str) -> str:
    """Quita fragmentos y parámetros de seguimiento de una URL estable."""

    parsed = urlsplit(value.strip())
    filtered_query = [
        (key, item_value)
        for key, item_value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.casefold() not in _TRACKING_KEYS
        and not key.casefold().startswith(_TRACKING_PREFIXES)
    ]
    filtered_query.sort(key=lambda item: (item[0].casefold(), item[1]))
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit(
        (
            parsed.scheme.casefold(),
            parsed.netloc.casefold(),
            path,
            urlencode(filtered_query, doseq=True),
            "",
        )
    )


def select_source_key(
    *,
    internal_id: str | None = None,
    sku: str | None = None,
    barcode: str | None = None,
    api_id: str | None = None,
    stable_url: str | None = None,
) -> tuple[SourceKeyType, str]:
    """Selecciona la primera llave disponible según la prioridad aprobada."""

    candidates = (
        (SourceKeyType.INTERNAL_ID, internal_id),
        (SourceKeyType.SKU, sku),
        (SourceKeyType.BARCODE, barcode),
        (SourceKeyType.API_ID, api_id),
        (SourceKeyType.STABLE_URL, stable_url),
    )
    for key_type, value in candidates:
        if value is not None and str(value).strip():
            selected = str(value).strip()
            if key_type is SourceKeyType.STABLE_URL:
                selected = canonicalize_url(selected)
            return key_type, selected
    raise ValueError("No existe una llave fuente estable disponible")


def _stable_digest(prefix: str, payload: Mapping[str, Any], length: int = 32) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return f"{prefix}{digest[:length]}"


def generate_source_product_id(
    supermarket_id: str,
    source_key_type: SourceKeyType | str,
    source_key: str,
) -> str:
    """Genera identidad fuente sin usar precio, promoción ni disponibilidad."""

    key_type = source_key_type if isinstance(source_key_type, SourceKeyType) else SourceKeyType(source_key_type)
    normalized_key = source_key.strip()
    if not normalized_key:
        raise ValueError("source_key no puede estar vacío")
    if key_type is SourceKeyType.STABLE_URL:
        normalized_key = canonicalize_url(normalized_key)
    else:
        normalized_key = canonicalize_text(normalized_key) or ""

    return _stable_digest(
        "sp_",
        {
            "supermarket_id": canonicalize_text(supermarket_id),
            "source_key_type": key_type.value,
            "source_key": normalized_key,
        },
    )


def generate_offer_id(supermarket_id: str, location_id: str, source_product_id: str) -> str:
    """Genera la identidad de una oferta por supermercado, ubicación y producto fuente."""

    return _stable_digest(
        "of_",
        {
            "supermarket_id": canonicalize_text(supermarket_id),
            "location_id": canonicalize_text(location_id),
            "source_product_id": canonicalize_text(source_product_id),
        },
    )


def _decimal_string(value: Any) -> str | None:
    if value is None:
        return None
    decimal_value = value if isinstance(value, Decimal) else Decimal(str(value))
    normalized = decimal_value.normalize()
    rendered = format(normalized, "f")
    return "0" if rendered in {"-0", ""} else rendered


def _value(source: NormalizedOffer | Mapping[str, Any], field_name: str) -> Any:
    if isinstance(source, NormalizedOffer):
        return getattr(source, field_name)
    return source.get(field_name)


def generate_state_hash(offer: NormalizedOffer | Mapping[str, Any]) -> str:
    """Resume únicamente atributos que abren o cierran periodos históricos."""

    availability = _value(offer, "availability")
    if hasattr(availability, "value"):
        availability = availability.value

    state = {
        "current_price": _decimal_string(_value(offer, "current_price")),
        "reported_regular_price": _decimal_string(_value(offer, "reported_regular_price")),
        "is_promotion": bool(_value(offer, "is_promotion")),
        "availability": canonicalize_text(availability),
        "normalized_brand": canonicalize_text(_value(offer, "normalized_brand")),
        "unit_count": int(_value(offer, "unit_count")),
        "total_content": _decimal_string(_value(offer, "total_content")),
        "measurement_unit": canonicalize_text(_value(offer, "measurement_unit")),
    }
    serialized = json.dumps(state, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
