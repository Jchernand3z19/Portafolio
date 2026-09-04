"""Homologación conservadora de productos entre supermercados.

La clasificación descriptiva vive separada del estado comercial: cambiar una
categoría, un tipo de producto o un candidato de matching nunca modifica por sí
solo un periodo de precio.

Confianza:
- GTIN válido idéntico = identidad fuerte, pero una contradicción descriptiva
  puede bloquear su uso automático en comparaciones de precio;
- sin GTIN, el motor sólo genera candidatos `review_required`;
- dos GTIN válidos distintos nunca se proponen como el mismo producto;
- multipacks y unidades ambiguas se conservan, no se reducen a una unidad.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from difflib import SequenceMatcher
from typing import Iterable

from .identifiers import canonicalize_gtin, generate_gtin_product_id


class ProductHomologationError(ValueError):
    """Un registro no cumple el contrato mínimo de homologación."""


def _required_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProductHomologationError(f"{field_name}_missing")
    return value.strip()


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def fold_text(value: str | None) -> str | None:
    """Normaliza texto para comparación sin destruir el texto fuente."""

    value = _optional_text(value)
    if value is None:
        return None
    decomposed = unicodedata.normalize("NFKD", value)
    without_marks = "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )
    normalized = re.sub(r"[^0-9a-zA-Z]+", " ", without_marks).casefold()
    collapsed = " ".join(normalized.split())
    return collapsed or None


@dataclass(frozen=True, slots=True)
class SourceProductRecord:
    source_record_id: str
    supermarket_id: str
    source_name: str
    source_brand: str | None = None
    source_presentation: str | None = None
    source_category: str | None = None
    barcode: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "source_record_id",
            _required_text(self.source_record_id, "source_record_id"),
        )
        object.__setattr__(
            self,
            "supermarket_id",
            _required_text(self.supermarket_id, "supermarket_id"),
        )
        object.__setattr__(
            self,
            "source_name",
            _required_text(self.source_name, "source_name"),
        )
        for field_name in (
            "source_brand",
            "source_presentation",
            "source_category",
            "barcode",
        ):
            object.__setattr__(
                self, field_name, _optional_text(getattr(self, field_name))
            )


@dataclass(frozen=True, slots=True)
class TaxonomyAssignment:
    category: str | None
    subcategory: str | None
    product_type: str | None
    rule_id: str | None


@dataclass(frozen=True, slots=True)
class PresentationSignature:
    """Presentación comparable; `total_base` representa el paquete completo."""

    dimension: str
    total_base: Decimal
    pack_count: int
    unit_amount_base: Decimal | None = None

    def __post_init__(self) -> None:
        if self.dimension not in {"mass_g", "volume_ml", "count", "ounce"}:
            raise ProductHomologationError("presentation_dimension_invalid")
        if self.total_base <= 0 or self.pack_count <= 0:
            raise ProductHomologationError("presentation_value_invalid")
        if self.unit_amount_base is not None and self.unit_amount_base <= 0:
            raise ProductHomologationError("presentation_unit_value_invalid")


@dataclass(frozen=True, slots=True)
class ProductProfile:
    record: SourceProductRecord
    normalized_name: str
    normalized_brand: str | None
    canonical_gtin: str | None
    canonical_product_id: str | None
    taxonomy: TaxonomyAssignment
    presentation: PresentationSignature | None
    presentation_status: str
    matching_tokens: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ExactGtinGroup:
    canonical_gtin: str
    canonical_product_id: str
    source_record_ids: tuple[str, ...]
    supermarket_ids: tuple[str, ...]
    comparison_status: str = "ready"
    conflict_reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MatchCandidate:
    left_source_record_id: str
    right_source_record_id: str
    left_supermarket_id: str
    right_supermarket_id: str
    product_type: str
    normalized_brand: str
    score: Decimal
    reason: str = "brand+product_type+presentation+name_similarity"
    status: str = "review_required"


@dataclass(frozen=True, slots=True)
class HomologationResult:
    profiles: tuple[ProductProfile, ...]
    exact_gtin_groups: tuple[ExactGtinGroup, ...]
    candidates: tuple[MatchCandidate, ...]

    @property
    def summary(self) -> dict[str, int]:
        exact_members = {
            source_id
            for group in self.exact_gtin_groups
            for source_id in group.source_record_ids
        }
        return {
            "source_products": len(self.profiles),
            "classified_product_type": sum(
                p.taxonomy.product_type is not None for p in self.profiles
            ),
            "valid_gtin": sum(p.canonical_gtin is not None for p in self.profiles),
            "exact_gtin_groups_cross_supermarket": len(self.exact_gtin_groups),
            "exact_gtin_groups_comparison_ready": sum(
                g.comparison_status == "ready" for g in self.exact_gtin_groups
            ),
            "exact_gtin_groups_review_required": sum(
                g.comparison_status == "review_required"
                for g in self.exact_gtin_groups
            ),
            "source_products_in_exact_gtin_groups": len(exact_members),
            "review_candidates": len(self.candidates),
            "presentation_conflicts": sum(
                p.presentation_status == "conflict" for p in self.profiles
            ),
        }


@dataclass(frozen=True, slots=True)
class _TaxonomyRule:
    rule_id: str
    category: str
    subcategory: str
    product_type: str
    all_terms: tuple[str, ...] = ()
    any_terms: tuple[str, ...] = ()
    forbidden_terms: tuple[str, ...] = ()

    def matches(self, text: str) -> bool:
        padded = f" {text} "

        def present(term: str) -> bool:
            return f" {term} " in padded if " " not in term else term in text

        return (
            all(present(term) for term in self.all_terms)
            and (not self.any_terms or any(present(term) for term in self.any_terms))
            and not any(present(term) for term in self.forbidden_terms)
        )


# Específico -> genérico. `product_type` se deriva del nombre anunciado, no del
# breadcrumb fuente: categorías como "Pastas y Salsas" no convierten una salsa
# en pasta.
_TAXONOMY_RULES = (
    _TaxonomyRule("harina_maiz", "Alimentos", "Harinas", "Harina de maíz", ("harina",), ("maiz",)),
    _TaxonomyRule("harina_trigo", "Alimentos", "Harinas", "Harina de trigo", ("harina",), ("trigo",)),
    _TaxonomyRule("leche_polvo", "Alimentos", "Lácteos", "Leche en polvo", ("leche", "polvo")),
    _TaxonomyRule("leche_condensada", "Alimentos", "Lácteos", "Leche condensada", ("leche", "condensada")),
    _TaxonomyRule("leche_evaporada", "Alimentos", "Lácteos", "Leche evaporada", ("leche", "evaporada")),
    _TaxonomyRule("leche", "Alimentos", "Lácteos", "Leche", ("leche",), forbidden_terms=("condensada", "evaporada", "polvo")),
    _TaxonomyRule("huevo", "Alimentos", "Huevos", "Huevo", any_terms=("huevo", "huevos")),
    _TaxonomyRule("arroz", "Alimentos", "Arroz y granos", "Arroz", any_terms=("arroz",)),
    _TaxonomyRule("frijol", "Alimentos", "Frijoles y legumbres", "Frijol", any_terms=("frijol", "frijoles")),
    _TaxonomyRule("pasta_dental", "Cuidado personal", "Higiene oral", "Pasta dental", ("pasta",), ("dental", "dientes")),
    _TaxonomyRule("pasta", "Alimentos", "Pastas", "Pasta", any_terms=("pasta", "espagueti", "spaghetti", "macarron", "macarrones")),
    _TaxonomyRule("cereal", "Alimentos", "Cereales", "Cereal", any_terms=("cereal", "corn flakes", "hojuelas")),
    _TaxonomyRule("avena", "Alimentos", "Cereales", "Avena", any_terms=("avena", "mosh")),
    _TaxonomyRule("mantequilla_mani", "Alimentos", "Untables", "Mantequilla de maní", ("mantequilla",), ("mani",)),
    _TaxonomyRule("mantequilla", "Alimentos", "Lácteos", "Mantequilla", ("mantequilla",), forbidden_terms=("mani",)),
    _TaxonomyRule("queso", "Alimentos", "Lácteos", "Queso", any_terms=("queso",)),
    _TaxonomyRule("yogurt", "Alimentos", "Lácteos", "Yogurt", any_terms=("yogurt", "yoghurt")),
    _TaxonomyRule("pan_molde", "Alimentos", "Panadería", "Pan de molde", ("pan",), ("molde", "sandwich")),
    _TaxonomyRule("aceite", "Alimentos", "Aceites y grasas", "Aceite comestible", any_terms=("aceite",), forbidden_terms=("motor", "cabello", "corporal", "esencial")),
    _TaxonomyRule("cafe", "Bebidas", "Café", "Café", any_terms=("cafe",)),
    _TaxonomyRule("agua_micelar", "Cuidado personal", "Cuidado facial", "Agua micelar", ("agua", "micelar")),
    _TaxonomyRule("agua", "Bebidas", "Agua", "Agua", any_terms=("agua",), forbidden_terms=("oxigenada", "micelar", "colonia")),
    _TaxonomyRule("jugo", "Bebidas", "Jugos", "Jugo", any_terms=("jugo", "nectar")),
    _TaxonomyRule("refresco", "Bebidas", "Refrescos", "Refresco", any_terms=("refresco", "gaseosa", "soda")),
    _TaxonomyRule("detergente", "Limpieza", "Lavandería", "Detergente", any_terms=("detergente",)),
    _TaxonomyRule("suavizante", "Limpieza", "Lavandería", "Suavizante", any_terms=("suavizante",)),
    _TaxonomyRule("papel_higienico", "Hogar", "Papel", "Papel higiénico", ("papel", "higienico")),
    _TaxonomyRule("shampoo", "Cuidado personal", "Cabello", "Shampoo", any_terms=("shampoo", "champu")),
    _TaxonomyRule("jabon", "Cuidado personal", "Higiene", "Jabón", any_terms=("jabon",)),
    _TaxonomyRule("desodorante", "Cuidado personal", "Higiene", "Desodorante", any_terms=("desodorante",)),
    _TaxonomyRule("panal", "Bebés", "Pañales", "Pañal", any_terms=("panal", "panales")),
    _TaxonomyRule("alimento_perro", "Mascotas", "Alimento para mascotas", "Alimento para perro", ("alimento",), ("perro", "canino")),
    _TaxonomyRule("alimento_gato", "Mascotas", "Alimento para mascotas", "Alimento para gato", ("alimento",), ("gato", "felino")),
)


# `oz` no se fuerza a gramos: sin "fl oz" la fuente puede estar usando onzas
# de peso o una abreviación comercial de onza fluida.
_UNIT_FACTORS: dict[str, tuple[str, Decimal]] = {
    "g": ("mass_g", Decimal("1")),
    "gr": ("mass_g", Decimal("1")),
    "gramo": ("mass_g", Decimal("1")),
    "gramos": ("mass_g", Decimal("1")),
    "kg": ("mass_g", Decimal("1000")),
    "lb": ("mass_g", Decimal("453.59237")),
    "lbs": ("mass_g", Decimal("453.59237")),
    "ml": ("volume_ml", Decimal("1")),
    "l": ("volume_ml", Decimal("1000")),
    "lt": ("volume_ml", Decimal("1000")),
    "litro": ("volume_ml", Decimal("1000")),
    "litros": ("volume_ml", Decimal("1000")),
    "oz": ("ounce", Decimal("1")),
    "onza": ("ounce", Decimal("1")),
    "onzas": ("ounce", Decimal("1")),
    "un": ("count", Decimal("1")),
    "und": ("count", Decimal("1")),
    "uds": ("count", Decimal("1")),
    "ud": ("count", Decimal("1")),
    "unidad": ("count", Decimal("1")),
    "unidades": ("count", Decimal("1")),
}
_UNIT_PATTERN = "|".join(sorted(_UNIT_FACTORS, key=len, reverse=True))
_EXPLICIT_MULTIPACK_RE = re.compile(
    rf"(?<!\w)(?P<count>\d+)\s*[x×]\s*(?P<amount>\d+(?:[.,]\d+)?)\s*(?P<unit>{_UNIT_PATTERN})(?!\w)",
    re.IGNORECASE,
)
_SLASH_MULTIPACK_RE = re.compile(
    rf"(?<!\w)(?P<count>\d+)\s*(?:unidades?|uds?|und|ud|pack|pk)\s*/\s*(?P<amount>\d+(?:[.,]\d+)?)\s*(?P<unit>{_UNIT_PATTERN})(?!\w)",
    re.IGNORECASE,
)
_SINGLE_RE = re.compile(
    rf"(?<!\w)(?P<amount>\d+(?:[.,]\d+)?)\s*(?P<unit>{_UNIT_PATTERN})(?!\w)",
    re.IGNORECASE,
)
_STOPWORDS = frozenset(
    {
        "de", "del", "la", "el", "los", "las", "y", "con", "para", "en", "por",
        "un", "und", "uds", "ud", "unidad", "unidades", "g", "gr", "kg", "lb", "lbs",
        "oz", "ml", "l", "lt", "x", "pack", "pk",
    }
)


def assign_taxonomy(record: SourceProductRecord) -> TaxonomyAssignment:
    text = fold_text(record.source_name) or ""
    for rule in _TAXONOMY_RULES:
        if rule.matches(text):
            return TaxonomyAssignment(
                category=rule.category,
                subcategory=rule.subcategory,
                product_type=rule.product_type,
                rule_id=rule.rule_id,
            )
    return TaxonomyAssignment(None, None, None, None)


def _decimal(value: str) -> Decimal | None:
    try:
        parsed = Decimal(value.replace(",", "."))
    except (InvalidOperation, ValueError):
        return None
    return parsed if parsed.is_finite() and parsed > 0 else None


def _signature(
    amount_text: str,
    unit_text: str,
    *,
    pack_count: int = 1,
) -> PresentationSignature | None:
    amount = _decimal(amount_text)
    unit_info = _UNIT_FACTORS.get(unit_text.casefold())
    if amount is None or unit_info is None or pack_count <= 0:
        return None
    dimension, factor = unit_info
    unit_amount = amount * factor
    if dimension == "count":
        if pack_count != 1 or amount != amount.to_integral_value():
            return None
        count = int(amount)
        return PresentationSignature(
            dimension="count",
            total_base=Decimal(count),
            pack_count=count,
            unit_amount_base=Decimal("1"),
        )
    return PresentationSignature(
        dimension=dimension,
        total_base=unit_amount * pack_count,
        pack_count=pack_count,
        unit_amount_base=unit_amount,
    )


def _parse_presentation_text(value: str | None) -> PresentationSignature | None:
    value = _optional_text(value)
    if value is None:
        return None
    slash = list(_SLASH_MULTIPACK_RE.finditer(value))
    if slash:
        match = slash[-1]
        return _signature(
            match.group("amount"),
            match.group("unit"),
            pack_count=int(match.group("count")),
        )
    explicit = list(_EXPLICIT_MULTIPACK_RE.finditer(value))
    if explicit:
        match = explicit[-1]
        return _signature(
            match.group("amount"),
            match.group("unit"),
            pack_count=int(match.group("count")),
        )
    singles = list(_SINGLE_RE.finditer(value))
    if not singles:
        return None
    match = singles[-1]
    return _signature(match.group("amount"), match.group("unit"))


def presentations_compatible(
    left: PresentationSignature,
    right: PresentationSignature,
) -> bool:
    if left.dimension != right.dimension or left.pack_count != right.pack_count:
        return False
    if left.dimension in {"count", "ounce"}:
        return left.total_base == right.total_base
    larger = max(left.total_base, right.total_base)
    difference = abs(left.total_base - right.total_base)
    return difference <= Decimal("1.5") or difference / larger <= Decimal("0.005")


def resolve_presentation(
    record: SourceProductRecord,
) -> tuple[PresentationSignature | None, str]:
    source = _parse_presentation_text(record.source_presentation)
    name = _parse_presentation_text(record.source_name)
    if source is not None and name is not None:
        if presentations_compatible(source, name):
            return source, "confirmed"
        return None, "conflict"
    if source is not None:
        return source, "source_only"
    if name is not None:
        return name, "name_only"
    return None, "missing"


def _matching_tokens(name: str, brand: str | None) -> tuple[str, ...]:
    tokens = (fold_text(name) or "").split()
    brand_tokens = set((fold_text(brand) or "").split())
    return tuple(
        token
        for token in tokens
        if token not in _STOPWORDS
        and token not in brand_tokens
        and not token.isdigit()
    )


def profile_product(record: SourceProductRecord) -> ProductProfile:
    normalized_name = fold_text(record.source_name)
    assert normalized_name is not None
    normalized_brand = fold_text(record.source_brand)
    canonical_gtin = canonicalize_gtin(record.barcode)
    presentation, presentation_status = resolve_presentation(record)
    return ProductProfile(
        record=record,
        normalized_name=normalized_name,
        normalized_brand=normalized_brand,
        canonical_gtin=canonical_gtin,
        canonical_product_id=(
            generate_gtin_product_id(canonical_gtin)
            if canonical_gtin is not None
            else None
        ),
        taxonomy=assign_taxonomy(record),
        presentation=presentation,
        presentation_status=presentation_status,
        matching_tokens=_matching_tokens(record.source_name, record.source_brand),
    )


def _name_similarity(left: ProductProfile, right: ProductProfile) -> Decimal:
    left_tokens = set(left.matching_tokens)
    right_tokens = set(right.matching_tokens)
    if not left_tokens or not right_tokens:
        return Decimal("0")
    jaccard = Decimal(len(left_tokens & right_tokens)) / Decimal(
        len(left_tokens | right_tokens)
    )
    sequence = Decimal(
        str(
            SequenceMatcher(
                None,
                " ".join(left.matching_tokens),
                " ".join(right.matching_tokens),
            ).ratio()
        )
    )
    return (
        jaccard * Decimal("0.6") + sequence * Decimal("0.4")
    ).quantize(Decimal("0.0001"))


def _presentation_bucket(value: PresentationSignature) -> tuple[str, int, int]:
    if value.dimension in {"count", "ounce"}:
        bucket = int(
            (value.total_base * Decimal("10")).to_integral_value(
                rounding=ROUND_HALF_UP
            )
        )
    else:
        bucket = int(
            (value.total_base / Decimal("5")).to_integral_value(
                rounding=ROUND_HALF_UP
            )
        )
    return value.dimension, value.pack_count, bucket


def _gtin_group_conflicts(members: list[ProductProfile]) -> tuple[str, ...]:
    reasons: set[str] = set()
    if any(member.presentation_status == "conflict" for member in members):
        reasons.add("source_presentation_conflict")

    comparable = [
        member
        for member in members
        if member.presentation is not None
        and member.presentation_status != "conflict"
    ]
    for index, left in enumerate(comparable):
        for right in comparable[index + 1 :]:
            if left.record.supermarket_id == right.record.supermarket_id:
                continue
            assert left.presentation is not None and right.presentation is not None
            if not presentations_compatible(left.presentation, right.presentation):
                reasons.add("cross_source_presentation_conflict")

    types = {
        member.taxonomy.product_type
        for member in members
        if member.taxonomy.product_type is not None
    }
    if len(types) > 1:
        reasons.add("product_type_conflict")
    return tuple(sorted(reasons))


def homologate_products(
    records: Iterable[SourceProductRecord],
    *,
    candidate_threshold: Decimal = Decimal("0.72"),
) -> HomologationResult:
    """Clasifica, agrupa GTIN exactos y genera candidatos revisables."""

    if candidate_threshold < 0 or candidate_threshold > 1:
        raise ProductHomologationError("candidate_threshold_invalid")
    profiles = tuple(
        sorted(
            (profile_product(record) for record in records),
            key=lambda profile: profile.record.source_record_id,
        )
    )
    if len({p.record.source_record_id for p in profiles}) != len(profiles):
        raise ProductHomologationError("source_record_id_duplicate")

    gtin_index: dict[str, list[ProductProfile]] = defaultdict(list)
    for profile in profiles:
        if profile.canonical_gtin is not None:
            gtin_index[profile.canonical_gtin].append(profile)

    exact_groups: list[ExactGtinGroup] = []
    for gtin, members in sorted(gtin_index.items()):
        supermarkets = sorted({m.record.supermarket_id for m in members})
        if len(supermarkets) < 2:
            continue
        conflicts = _gtin_group_conflicts(members)
        exact_groups.append(
            ExactGtinGroup(
                canonical_gtin=gtin,
                canonical_product_id=generate_gtin_product_id(gtin),
                source_record_ids=tuple(m.record.source_record_id for m in members),
                supermarket_ids=tuple(supermarkets),
                comparison_status=("review_required" if conflicts else "ready"),
                conflict_reasons=conflicts,
            )
        )

    blocks: dict[
        tuple[str, str, str, int, int], list[ProductProfile]
    ] = defaultdict(list)
    for profile in profiles:
        if (
            profile.taxonomy.product_type is None
            or profile.normalized_brand is None
            or profile.presentation is None
        ):
            continue
        dimension, pack_count, bucket = _presentation_bucket(profile.presentation)
        blocks[
            (
                profile.taxonomy.product_type,
                profile.normalized_brand,
                dimension,
                pack_count,
                bucket,
            )
        ].append(profile)

    candidates: list[MatchCandidate] = []
    seen_pairs: set[tuple[str, str]] = set()
    for members in blocks.values():
        for index, left in enumerate(members):
            for right in members[index + 1 :]:
                if left.record.supermarket_id == right.record.supermarket_id:
                    continue
                pair = tuple(
                    sorted(
                        (left.record.source_record_id, right.record.source_record_id)
                    )
                )
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                if left.canonical_gtin is not None and right.canonical_gtin is not None:
                    # Igual GTIN ya está en exact_groups; GTIN distinto contradice match.
                    continue
                assert left.presentation is not None and right.presentation is not None
                if not presentations_compatible(left.presentation, right.presentation):
                    continue
                score = _name_similarity(left, right)
                if score < candidate_threshold:
                    continue
                candidates.append(
                    MatchCandidate(
                        left_source_record_id=left.record.source_record_id,
                        right_source_record_id=right.record.source_record_id,
                        left_supermarket_id=left.record.supermarket_id,
                        right_supermarket_id=right.record.supermarket_id,
                        product_type=left.taxonomy.product_type,
                        normalized_brand=left.normalized_brand,
                        score=score,
                    )
                )

    candidates.sort(
        key=lambda candidate: (
            -candidate.score,
            candidate.left_source_record_id,
            candidate.right_source_record_id,
        )
    )
    return HomologationResult(profiles, tuple(exact_groups), tuple(candidates))
