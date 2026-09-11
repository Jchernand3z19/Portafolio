"""Normalización de presentación y marca para superficies públicas B2C.

La identidad y la magnitud canónica se resuelven aguas arriba. Esta capa sólo
elige un ``display_value`` legible, preservando cuando es posible la unidad
comercial escrita por la fuente (por ejemplo ``1.2 lb``) en lugar de exponer el
valor técnico de conversión (por ejemplo ``544.310844 g``).
"""
from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation


_GENERIC_BRAND_KEYS = frozenset(
    {
        "rms",
        "marca comandes",
        "sin marca",
        "sin marca definida",
        "generico",
        "generica",
        "generic",
        "no aplica",
        "n a",
        "na",
        "none",
    }
)

_BRAND_CANONICAL = {
    "bonovo": "Bonovo",
    "don cristobal": "Don Cristobal",
    "el ranchero": "El Ranchero",
    "gallina feliz": "Gallina Feliz",
    "great value": "Great Value",
    "hellmann s": "Hellmann's",
    "hellmanns": "Hellmann's",
    "kraft": "Kraft",
    "marca marketside": "Marketside",
    "marketside": "Marketside",
    "mccormick": "McCormick",
    "member s selection": "Member's Selection",
    "members selection": "Member's Selection",
    "mister huevo": "Mister Huevo",
    "norteno": "Norteño",
    "nutri yema": "Nutri Yema",
    "nutriyema": "Nutri Yema",
    "regia": "Regia",
    "rica yema": "Rica Yema",
    "suli": "Suli",
}

_COUNT_UNIT_PATTERN = r"(?:u|uni|un|und|unds|unid|unids|ud|uds|unidad|unidades)"
_EGG_COUNT_UNIT_PATTERN = rf"(?:{_COUNT_UNIT_PATTERN}|pack|packs|paquete|paquetes)"
_COUNT_RE = re.compile(
    rf"(?<!\w)(?P<amount>\d+(?:[.,]\d+)?)\s*(?P<unit>{_COUNT_UNIT_PATTERN})(?!\w)",
    re.IGNORECASE,
)
_MASS_RE = re.compile(
    r"(?<!\w)(?P<amount>\d+(?:[.,]\d+)?)\s*(?P<unit>mg|kg|kilogramos?|g|grs?|gramos?|lb|lbs|libra|libras)(?!\w)",
    re.IGNORECASE,
)
_VOLUME_RE = re.compile(
    r"(?<!\w)(?P<amount>\d+(?:[.,]\d+)?)\s*(?P<unit>ml|l|lt|lts|litros?)(?!\w)",
    re.IGNORECASE,
)
_OUNCE_RE = re.compile(
    r"(?<!\w)(?P<amount>\d+(?:[.,]\d+)?)\s*(?P<unit>oz|onza|onzas)(?!\w)",
    re.IGNORECASE,
)
_GALLON_RE = re.compile(
    r"(?<!\w)(?P<amount>\d+(?:[.,]\d+)?)\s*(?P<unit>gal|gl|galon|galones)(?!\w)",
    re.IGNORECASE,
)
_EGG_COUNT_RE = re.compile(
    rf"(?<!\w)(?P<count>\d{{1,3}})\s*(?:p|m|g|l|xl|jumbo)?\s*{_EGG_COUNT_UNIT_PATTERN}(?!\w)",
    re.IGNORECASE,
)

_VALID_PROFILE_PRESENTATION = frozenset(
    {"confirmed", "name_only", "source_only", "name_preferred_source_conflict"}
)
_EGG_FALSE_POSITIVES = frozenset(
    {"tallarin", "tallarines", "fideo", "fideos", "mayonesa", "claras", "clara", "kinder", "toro"}
)
_GENERIC_PRESENTATIONS = frozenset({"un", "unidad", "unidades"})


def _clean(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split())
    return cleaned or None


def _fold(value: object) -> str | None:
    cleaned = _clean(value)
    if cleaned is None:
        return None
    decomposed = unicodedata.normalize("NFKD", cleaned)
    without_marks = "".join(char for char in decomposed if not unicodedata.combining(char))
    normalized = re.sub(r"[^0-9a-zA-Z]+", " ", without_marks).casefold()
    return " ".join(normalized.split()) or None


def _decimal(value: object) -> Decimal | None:
    try:
        parsed = Decimal(str(value).replace(",", "."))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return parsed if parsed.is_finite() and parsed > 0 else None


def _format_decimal(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _smart_brand_case(value: str) -> str:
    if value.isupper() or value.islower():
        value = value.title()
        value = re.sub(r"'S\b", "'s", value)
    return value


def _brand_from_name(product_name: object) -> str | None:
    name = _fold(product_name) or ""
    matches = {
        display
        for alias, display in _BRAND_CANONICAL.items()
        if re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", name)
    }
    return next(iter(matches)) if len(matches) == 1 else None


def canonical_brand(raw_brand: object, product_name: object) -> str | None:
    """Capitaliza la marca canónica y oculta placeholders conocidos."""
    raw = _clean(raw_brand)
    key = _fold(raw)
    name_brand = _brand_from_name(product_name)
    if key is not None and key not in _GENERIC_BRAND_KEYS:
        raw_brand_display = _BRAND_CANONICAL.get(key, _smart_brand_case(raw))
        if name_brand is not None and name_brand != raw_brand_display:
            return name_brand
        return raw_brand_display
    return name_brand


def _is_shell_egg(product_name: object, product_type: object) -> bool:
    name = _fold(product_name) or ""
    tokens = name.split()
    if _EGG_FALSE_POSITIVES.intersection(tokens):
        return False
    type_is_egg = _fold(product_type) == "huevo"
    limit = 6 if type_is_egg else 4
    return any(token in {"huevo", "huevos"} for token in tokens[:limit])


def canonical_egg_size(product_name: object, product_type: object) -> str | None:
    if not _is_shell_egg(product_name, product_type):
        return None
    name = _fold(product_name) or ""
    if re.search(r"\b(?:extra grande|extra grandes|xl)\b", name) or re.search(
        rf"\d+\s*xl\s*{_COUNT_UNIT_PATTERN}\b", name
    ):
        return "Extra grande"
    if re.search(r"\bjumbo\b", name):
        return "Jumbo"
    if re.search(r"\b(?:pequeno|pequenos|pequena|pequenas)\b", name) or re.search(r"\bcarton\s+p\b", name):
        return "Pequeño"
    if re.search(r"\b(?:mediano|medianos|mediana|medianas)\b", name) or re.search(r"\bcarton\s+m\b", name) or re.search(r"\bhuevo(?:s)?\s+(?:liso\s+)?m\b", name):
        return "Mediano"
    if re.search(r"\b(?:grande|grandes)\b", name) or re.search(r"\bcarton\s+g\b", name) or re.search(r"\bhuevo(?:s)?\s+g\b", name) or re.search(
        rf"\d+\s*g\s*{_COUNT_UNIT_PATTERN}\b", name
    ):
        return "Grande"
    return None


def _egg_count(product_name: object, source_presentation: object, product_type: object) -> int | None:
    if not _is_shell_egg(product_name, product_type):
        return None
    combined = " ".join(value for value in (_clean(product_name), _clean(source_presentation)) if value)
    matches = list(_EGG_COUNT_RE.finditer(combined))
    if not matches:
        return None
    value = int(matches[-1].group("count"))
    return value if value > 0 else None


def _from_dimension(dimension: object, total_base: object) -> str | None:
    total = _decimal(total_base)
    if total is None:
        return None
    if dimension == "count":
        if total != total.to_integral_value():
            return None
        return f"{int(total)} unidades"
    if dimension == "mass_g":
        if total >= 1000 and total % 1000 == 0:
            return f"{_format_decimal(total / 1000)} kg"
        # La base canónica puede venir de una conversión imperial con muchos
        # decimales. Si no existe texto comercial, redondeamos sólo display.
        rounded = total.quantize(Decimal("0.01"))
        return f"{_format_decimal(rounded)} g"
    if dimension == "volume_ml":
        if total >= 1000 and total % 1000 == 0:
            return f"{_format_decimal(total / 1000)} L"
        rounded = total.quantize(Decimal("0.01"))
        return f"{_format_decimal(rounded)} ml"
    if dimension == "ounce":
        return f"{_format_decimal(total)} oz"
    return None


def _from_text(value: object) -> str | None:
    text = _clean(value)
    if text is None:
        return None
    matches: list[tuple[int, str, re.Match[str]]] = []
    for regex, kind in (
        (_COUNT_RE, "count"),
        (_MASS_RE, "mass"),
        (_VOLUME_RE, "volume"),
        (_OUNCE_RE, "ounce"),
        (_GALLON_RE, "gallon"),
    ):
        matches.extend((match.start(), kind, match) for match in regex.finditer(text))
    if not matches:
        return None
    _, kind, match = max(matches, key=lambda item: item[0])
    amount = _decimal(match.group("amount"))
    if amount is None:
        return None
    unit = match.group("unit").casefold()
    if kind == "count":
        return f"{int(amount)} unidades" if amount == amount.to_integral_value() else None
    if kind == "mass":
        if unit == "mg":
            return f"{_format_decimal(amount)} mg"
        if unit.startswith("kg") or unit.startswith("kilo"):
            return f"{_format_decimal(amount)} kg"
        if unit in {"lb", "lbs", "libra", "libras"}:
            return f"{_format_decimal(amount)} lb"
        return f"{_format_decimal(amount)} g"
    if kind == "volume":
        if unit in {"l", "lt", "lts", "litro", "litros"}:
            return f"{_format_decimal(amount)} L"
        return f"{_format_decimal(amount)} ml"
    if kind == "gallon":
        return f"{_format_decimal(amount)} gal"
    return f"{_format_decimal(amount)} oz"


def canonical_presentation(
    *,
    source_presentation: object,
    product_name: object,
    product_type: object,
    presentation_dimension: object,
    presentation_total_base: object,
    presentation_status: object,
) -> str | None:
    """Elige display comercial sin alterar la magnitud canónica de matching."""
    egg_count = _egg_count(product_name, source_presentation, product_type)
    if egg_count is not None:
        return f"{egg_count} unidades"

    # raw/display antes de canonical base: conserva 1.2 lb como 1.2 lb y evita
    # publicar 544.310844 g. La magnitud convertida sigue disponible para matching.
    source_display = _from_text(source_presentation)
    name_display = _from_text(product_name)
    if source_display is not None:
        return source_display
    if name_display is not None:
        return name_display

    if presentation_status in _VALID_PROFILE_PRESENTATION:
        normalized = _from_dimension(presentation_dimension, presentation_total_base)
        if normalized is not None:
            return normalized

    source = _clean(source_presentation)
    if source is not None and (_fold(source) or "") not in _GENERIC_PRESENTATIONS:
        return source
    return None