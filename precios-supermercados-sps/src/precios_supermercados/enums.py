"""Enumeraciones compartidas por todos los extractores del proyecto."""

from enum import StrEnum


class SourceKeyType(StrEnum):
    """Tipo de llave estable elegida para identificar un producto fuente."""

    INTERNAL_ID = "internal_id"
    SKU = "sku"
    BARCODE = "barcode"
    API_ID = "api_id"
    STABLE_URL = "stable_url"


class AvailabilityStatus(StrEnum):
    """Estado observable de disponibilidad de una oferta."""

    IN_STOCK = "in_stock"
    OUT_OF_STOCK = "out_of_stock"
    NOT_LISTED = "not_listed"
    UNKNOWN = "unknown"


class LocationStatus(StrEnum):
    """Nivel de certeza sobre la ubicación asociada a la observación."""

    CONFIRMED = "confirmed"
    INFERRED = "inferred"
    UNKNOWN = "unknown"
