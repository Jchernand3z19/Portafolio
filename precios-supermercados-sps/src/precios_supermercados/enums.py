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


class ReviewStatus(StrEnum):
    """Estado de revisión de la interpretación normalizada."""

    READY = "ready"
    NEEDS_REVIEW = "needs_review"


class RunStatus(StrEnum):
    """Estado permitido para una ejecución de extracción."""

    RUNNING = "running"
    SUCCESS = "success"
    WARNING = "warning"
    REJECTED = "rejected"
    FAILED = "failed"
    ABANDONED = "abandoned"


class ChangeType(StrEnum):
    """Clasificación resumida del cambio que abre un periodo."""

    INITIAL = "initial"
    PRICE = "price"
    REGULAR_PRICE = "regular_price"
    PROMOTION = "promotion"
    AVAILABILITY = "availability"
    PRODUCT_ATTRIBUTE = "product_attribute"
    MULTIPLE = "multiple"


class QualityEventCategory(StrEnum):
    """Familia del evento registrado durante extracción o validación."""

    QUALITY = "quality"
    STRUCTURE = "structure"


class QualityEventSeverity(StrEnum):
    """Severidad operativa de un evento."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
