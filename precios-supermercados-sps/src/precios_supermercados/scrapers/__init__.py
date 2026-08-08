"""Extractores específicos de supermercados."""

from .base import ExtractionMetrics, ExtractionResult, SafeHttpClient, ScraperError
from .la_colonia import LaColoniaExtractor
from .la_colonia_runner import (
    AcceptanceProfile,
    AcceptanceThresholds,
    CatalogRunMetrics,
    CatalogRunResult,
    CrawlConfig,
    LaColoniaCatalogRunner,
    PageSummary,
)

__all__ = [
    "AcceptanceProfile",
    "AcceptanceThresholds",
    "CatalogRunMetrics",
    "CatalogRunResult",
    "CrawlConfig",
    "ExtractionMetrics",
    "ExtractionResult",
    "LaColoniaCatalogRunner",
    "LaColoniaExtractor",
    "PageSummary",
    "SafeHttpClient",
    "ScraperError",
]
