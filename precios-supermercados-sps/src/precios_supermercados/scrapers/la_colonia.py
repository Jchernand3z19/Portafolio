"""Extractor controlado del catálogo público de Supermercados La Colonia."""

from __future__ import annotations

import base64
import json
import math
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import parse_qs, urlencode, urlsplit

from precios_supermercados.enums import AvailabilityStatus, LocationStatus
from precios_supermercados.identifiers import select_source_key
from precios_supermercados.models import RawProduct

from .base import (
    EmptyResponseError,
    ExtractionMetrics,
    ExtractionResult,
    SafeHttpClient,
    StructureChangedError,
)

SUPERMARKET_ID = "la_colonia"
LOCATION_ID = "la_colonia_online"
LOCATION_EVIDENCE = (
    "Catálogo público en línea sin selección obligatoria de ciudad o sucursal."
)
BASE_URL = "https://www.lacolonia.com"
CATALOG_URL = f"{BASE_URL}/supermercado"
GRAPHQL_URL = f"{BASE_URL}/_v/segment/graphql/v1"
ROBOTS_URL = f"{BASE_URL}/robots.txt"
EXTRACTOR_VERSION = "0.1.0"
SCHEMA_VERSION = "1.0.0"
PERSISTED_QUERY_HASH = (
    "c351315ecde7f473587b710ac8b97f147ac0ac0cd3060c27c695843a72fd3903"
)
USER_AGENT = (
    "PreciosSupermercadosSPS-LaColonia/0.1 "
    "(+https://github.com/Jchernand3z19/Portafolio)"
)
FORBIDDEN_PATH_PREFIXES = (
    "/img",
    "/account",
    "/login",
    "/checkout",
    "/busca",
    "/quick-view",
    "/espiar",
    "/buscapagina",
    "/site/track.aspx",
    "/api",
    "/register.js",
)

_PRESENTATION_PATTERN = re.compile(
    r"(?i)(?:\bx\s*)?(?:(\d+(?:[.,]\d+)?)\s*)?"
    r"(lb|lbs|libra|libras|kg|g|gr|gramos|ml|l|lt|litros|oz|"
    r"un|und|uds|unidad|unidades|ft)\s*$"
)


class LaColoniaExtractor:
    """Obtiene una única página pública y produce el contrato ``RawProduct``."""

    def __init__(
        self,
        client: SafeHttpClient | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
        persisted_query_hash: str = PERSISTED_QUERY_HASH,
    ) -> None:
        self.client = client or SafeHttpClient(
            allowed_hosts={"www.lacolonia.com"},
            forbidden_path_prefixes=FORBIDDEN_PATH_PREFIXES,
            user_agent=USER_AGENT,
        )
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        if not re.fullmatch(r"[0-9a-f]{64}", persisted_query_hash):
            raise ValueError("persisted_query_hash debe ser SHA-256 hexadecimal")
        self.persisted_query_hash = persisted_query_hash

    def build_page_url(
        self,
        *,
        page: int = 1,
        page_size: int = 5,
        query: str = "supermercado",
        category_map: str = "category-1",
    ) -> str:
        if page < 1:
            raise ValueError("page debe ser mayor o igual que 1")
        if not 1 <= page_size <= 5:
            raise ValueError("La prueba controlada admite entre 1 y 5 productos")
        if not query.strip() or not category_map.strip():
            raise ValueError("query y category_map no pueden estar vacíos")

        from_index = (page - 1) * page_size
        variables = {
            "hideUnavailableItems": False,
            "skusFilter": "ALL",
            "simulationBehavior": "default",
            "installmentCriteria": "MAX_WITHOUT_INTEREST",
            "productOriginVtex": False,
            "map": category_map,
            "query": query,
            "orderBy": "OrderByReleaseDateDESC",
            "from": from_index,
            "to": from_index + page_size - 1,
            "selectedFacets": [{"key": category_map, "value": query}],
            "fullText": "",
            "facetsBehavior": "Static",
            "categoryTreeBehavior": "default",
            "withFacets": False,
        }
        encoded_variables = base64.b64encode(
            json.dumps(variables, separators=(",", ":")).encode("utf-8")
        ).decode("ascii")
        extensions = {
            "persistedQuery": {
                "version": 1,
                "sha256Hash": self.persisted_query_hash,
                "sender": "vtex.store-resources@0.x",
                "provider": "vtex.search-graphql@0.x",
            },
            "variables": encoded_variables,
        }
        params = {
            "workspace": "master",
            "maxAge": "short",
            "appsEtag": "remove",
            "domain": "store",
            "locale": "es-HN",
            "operationName": "productSearchV3",
            "variables": "{}",
            "extensions": json.dumps(extensions, separators=(",", ":")),
        }
        return f"{GRAPHQL_URL}?{urlencode(params)}"

    def extract_page(
        self,
        *,
        scrape_run_id: str,
        page: int = 1,
        page_size: int = 5,
        query: str = "supermercado",
        category_map: str = "category-1",
    ) -> ExtractionResult:
        source_url = self.build_page_url(
            page=page,
            page_size=page_size,
            query=query,
            category_map=category_map,
        )
        payload = self.client.get_json(source_url)
        return self.parse_payload(
            payload,
            scrape_run_id=scrape_run_id,
            source_url=source_url,
            page_size=page_size,
        )

    def parse_payload(
        self,
        payload: Mapping[str, Any],
        *,
        scrape_run_id: str,
        source_url: str,
        page_size: int = 5,
    ) -> ExtractionResult:
        products_payload, total = _read_product_search(payload)
        if not products_payload:
            raise EmptyResponseError("La página controlada no devolvió productos")

        metrics = ExtractionMetrics(
            products_discovered=total,
            pages_discovered=max(math.ceil(total / page_size), 1),
            pages_processed=1,
        )
        metrics.page_coverage = metrics.pages_processed / metrics.pages_discovered
        events: list[str] = []
        observed_at = self.clock()
        if observed_at.tzinfo is None or observed_at.utcoffset() is None:
            raise ValueError("clock debe devolver una fecha con zona horaria")
        observed_at = observed_at.astimezone(timezone.utc)

        raw_products: list[RawProduct] = []
        seen_keys: set[tuple[str, str]] = set()

        for product in products_payload:
            if not isinstance(product, Mapping):
                metrics.errors += 1
                events.append("quality:product_not_mapping")
                continue
            items = product.get("items")
            if not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
                metrics.errors += 1
                metrics.structural_events += 1
                events.append("structure:missing_items")
                continue

            for item in items:
                if len(raw_products) >= page_size:
                    break
                if not isinstance(item, Mapping):
                    metrics.errors += 1
                    events.append("quality:item_not_mapping")
                    continue
                try:
                    raw = self._parse_item(
                        product,
                        item,
                        observed_at=observed_at,
                        scrape_run_id=scrape_run_id,
                        source_url=source_url,
                    )
                except (KeyError, ValueError) as exc:
                    metrics.errors += 1
                    events.append(f"quality:skipped_item:{type(exc).__name__}")
                    continue

                identity = (raw.source_key_type.value, raw.source_key)
                if identity in seen_keys:
                    metrics.duplicate_products += 1
                    events.append("quality:duplicate_source_key")
                    continue
                seen_keys.add(identity)
                raw_products.append(raw)

                values = raw.raw_values
                if values.get("current_price") is not None:
                    metrics.products_with_price += 1
                if any(
                    values.get(field_name) is None
                    for field_name in (
                        "current_price",
                        "brand",
                        "category",
                        "presentation",
                    )
                ):
                    metrics.products_pending_review += 1

            if len(raw_products) >= page_size:
                break

        metrics.products_extracted = len(raw_products)
        if not raw_products:
            raise StructureChangedError("No se pudo interpretar ningún SKU de la respuesta")

        if metrics.products_with_price == 0:
            events.append("quality:missing_all_prices")
        if metrics.products_extracted < min(page_size, len(products_payload)):
            events.append("quality:partial_page")
        accepted = (
            metrics.products_with_price > 0
            and metrics.structural_events == 0
            and metrics.products_extracted > 0
        )
        return ExtractionResult(
            products=tuple(raw_products),
            metrics=metrics,
            quality_events=tuple(dict.fromkeys(events)),
            accepted=accepted,
            source_url=source_url,
        )

    def _parse_item(
        self,
        product: Mapping[str, Any],
        item: Mapping[str, Any],
        *,
        observed_at: datetime,
        scrape_run_id: str,
        source_url: str,
    ) -> RawProduct:
        product_name = _text(product.get("productName")) or _text(item.get("nameComplete"))
        if product_name is None:
            raise ValueError("Producto sin nombre")

        link_text = _text(product.get("linkText"))
        product_url = _product_url(link_text)
        product_id = _text(product.get("productId"))
        item_id = _text(item.get("itemId"))
        source_sku = _reference_value(item.get("referenceId")) or _text(
            product.get("productReference")
        )
        barcode = _text(item.get("ean"))
        source_key_type, source_key = select_source_key(
            internal_id=item_id,
            sku=source_sku,
            barcode=barcode,
            api_id=product_id,
            stable_url=product_url,
        )

        sellers = _mapping_sequence(item.get("sellers"))
        selected_seller = _select_seller(sellers)
        offer = _commercial_offer(selected_seller)
        current_price = _positive_decimal(offer.get("Price"))
        list_price = _positive_decimal(offer.get("ListPrice"))
        quantities = [
            _non_negative_decimal(_commercial_offer(seller).get("AvailableQuantity"))
            for seller in sellers
        ]
        quantities = [value for value in quantities if value is not None]
        availability = _availability(current_price, sellers, quantities)
        promotion_evidence = _promotion_evidence(offer)
        is_promotion = bool(
            (current_price is not None and list_price is not None and list_price > current_price)
            or promotion_evidence
        )
        reported_regular_price = (
            list_price
            if current_price is not None
            and list_price is not None
            and list_price > current_price
            else None
        )

        category_tree = _mapping_sequence(product.get("categoryTree"))
        category_names = tuple(
            name
            for entry in category_tree
            if (name := _text(entry.get("name"))) is not None
        )
        source_category = " > ".join(category_names) or _first_category(
            product.get("categories")
        )
        subcategory = category_names[-1] if len(category_names) > 1 else None
        source_brand = _text(product.get("brand"))
        presentation_source = (
            _text(item.get("nameComplete"))
            or _text(item.get("name"))
            or product_name
        )
        source_presentation = _presentation(presentation_source)
        images = _mapping_sequence(item.get("images"))
        image_url = next(
            (
                value
                for image in images
                if (value := _text(image.get("imageUrl") or image.get("imageTag")))
                and value.startswith("https://")
            ),
            None,
        )
        measurement_unit = _text(item.get("measurementUnit"))
        unit_multiplier = _positive_decimal(item.get("unitMultiplier"))

        raw_values = {
            "product_id": product_id,
            "item_id": item_id,
            "reference": source_sku,
            "ean": barcode,
            "brand": source_brand,
            "category": source_category,
            "subcategory": subcategory,
            "presentation": source_presentation,
            "categories": list(product.get("categories") or []),
            "category_tree": [dict(entry) for entry in category_tree],
            "current_price": _decimal_text(current_price),
            "reported_regular_price": _decimal_text(reported_regular_price),
            "source_list_price": _decimal_text(list_price),
            "is_promotion": is_promotion,
            "promotion_evidence": promotion_evidence,
            "availability": availability.value,
            "available_quantity": _decimal_text(quantities[0]) if quantities else None,
            "seller_id": _text(selected_seller.get("sellerId")) if selected_seller else None,
            "measurement_unit": measurement_unit,
            "unit_multiplier": _decimal_text(unit_multiplier),
            "weighted_product": _is_weighted(product_name, measurement_unit),
        }

        return RawProduct(
            supermarket_id=SUPERMARKET_ID,
            location_id=LOCATION_ID,
            source_key_type=source_key_type,
            source_key=source_key,
            source_name=product_name,
            product_url=product_url,
            observed_at_utc=observed_at,
            scrape_run_id=scrape_run_id,
            extractor_version=EXTRACTOR_VERSION,
            schema_version=SCHEMA_VERSION,
            source_url=source_url,
            source_sku=source_sku,
            source_brand=source_brand,
            source_presentation=source_presentation,
            source_category=source_category,
            image_url=image_url,
            location_status=LocationStatus.UNKNOWN,
            location_evidence=LOCATION_EVIDENCE,
            location_confidence=None,
            raw_values=raw_values,
        )


def decode_search_variables(url: str) -> Mapping[str, Any]:
    """Decodifica variables de una URL creada por el extractor; útil en pruebas."""

    parsed = urlsplit(url)
    extensions_raw = parse_qs(parsed.query).get("extensions")
    if not extensions_raw:
        raise ValueError("La URL no contiene extensions")
    extensions = json.loads(extensions_raw[0])
    encoded = extensions["variables"]
    decoded = base64.b64decode(encoded).decode("utf-8")
    value = json.loads(decoded)
    if not isinstance(value, Mapping):
        raise ValueError("Las variables no son un objeto")
    return value


def _read_product_search(payload: Mapping[str, Any]) -> tuple[Sequence[Any], int]:
    data = payload.get("data")
    if not isinstance(data, Mapping):
        raise StructureChangedError("Falta data en la respuesta GraphQL")
    product_search = data.get("productSearch")
    if not isinstance(product_search, Mapping):
        errors = payload.get("errors")
        if errors:
            raise StructureChangedError(f"GraphQL devolvió errores: {errors}")
        raise StructureChangedError("Falta data.productSearch")
    products = product_search.get("products")
    if not isinstance(products, Sequence) or isinstance(products, (str, bytes)):
        raise StructureChangedError("Falta data.productSearch.products")
    total_value = product_search.get("recordsFiltered", len(products))
    try:
        total = max(int(total_value), len(products))
    except (TypeError, ValueError):
        total = len(products)
    return products, total


def _mapping_sequence(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [entry for entry in value if isinstance(entry, Mapping)]


def _text(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _positive_decimal(value: Any) -> Decimal | None:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return result if result.is_finite() and result > 0 else None


def _non_negative_decimal(value: Any) -> Decimal | None:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return result if result.is_finite() and result >= 0 else None


def _decimal_text(value: Decimal | None) -> str | None:
    if value is None:
        return None
    rendered = format(value.normalize(), "f")
    return "0" if rendered in {"", "-0"} else rendered


def _product_url(link_text: str | None) -> str:
    if link_text is None:
        raise ValueError("Producto sin linkText")
    cleaned = link_text.strip("/")
    if not cleaned:
        raise ValueError("linkText vacío")
    return f"{BASE_URL}/{cleaned}/p"


def _reference_value(value: Any) -> str | None:
    for entry in _mapping_sequence(value):
        candidate = _text(entry.get("Value") or entry.get("value"))
        if candidate:
            return candidate
    return None


def _select_seller(sellers: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
    if not sellers:
        return {}
    return next((seller for seller in sellers if seller.get("sellerDefault") is True), sellers[0])


def _commercial_offer(seller: Mapping[str, Any]) -> Mapping[str, Any]:
    offer = seller.get("commercialOffer") if seller else None
    return offer if isinstance(offer, Mapping) else {}


def _availability(
    current_price: Decimal | None,
    sellers: Sequence[Mapping[str, Any]],
    quantities: Sequence[Decimal],
) -> AvailabilityStatus:
    if current_price is not None and any(quantity > 0 for quantity in quantities):
        return AvailabilityStatus.IN_STOCK
    if sellers and quantities and all(quantity == 0 for quantity in quantities):
        return AvailabilityStatus.OUT_OF_STOCK
    return AvailabilityStatus.UNKNOWN


def _promotion_evidence(offer: Mapping[str, Any]) -> list[str]:
    evidence: list[str] = []
    for field_name in ("discountHighlights", "teasers"):
        entries = offer.get(field_name)
        for entry in _mapping_sequence(entries):
            text = _text(entry.get("name") or entry.get("Name") or entry.get("<Name>k__BackingField"))
            if text:
                evidence.append(text)
            elif entry:
                evidence.append(field_name)
    return list(dict.fromkeys(evidence))


def _first_category(value: Any) -> str | None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return None
    for item in value:
        text = _text(item)
        if text:
            parts = [part.strip() for part in text.split("/") if part.strip()]
            return " > ".join(parts) if parts else text
    return None


def _presentation(value: str | None) -> str | None:
    if value is None:
        return None
    match = _PRESENTATION_PATTERN.search(value)
    if not match:
        return None
    number, _unit = match.groups()
    matched = match.group(0).strip()
    if number is None and not matched.casefold().startswith("x"):
        return None
    return matched


def _is_weighted(name: str, measurement_unit: str | None) -> bool:
    normalized_unit = (measurement_unit or "").casefold()
    if normalized_unit in {"kg", "g", "lb", "lbs", "libra", "libras"}:
        return True
    return bool(re.search(r"(?i)\bx\s*(lb|kg|g)\b", name))
