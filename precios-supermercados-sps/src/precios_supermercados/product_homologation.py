"""Homologación conservadora de productos entre supermercados.

La clasificación descriptiva vive separada del estado comercial: cambiar una
categoría, un tipo de producto o un candidato de matching nunca modifica por sí
solo un periodo de precio.

Confianza:
- GTIN válido idéntico = identidad fuerte, pero una contradicción descriptiva
  puede bloquear su uso automático en comparaciones de precio;
- sin GTIN, el motor sólo genera candidatos ``review_required``;
- dos GTIN válidos distintos nunca se proponen como el mismo producto;
- marcas placeholder no participan en matching;
- multipacks ambiguos no se reducen a una unidad;
- la presentación fuente de Paiz es evidencia auxiliar porque la auditoría real
  mostró contradicciones sistemáticas con el nombre comercial anunciado.
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


_GENERIC_BRANDS = frozenset(
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


def normalize_brand(value: str | None) -> str | None:
    """Devuelve una marca comparable o ``None`` para placeholders de fuente."""

    normalized = fold_text(value)
    if normalized is None or normalized in _GENERIC_BRANDS:
        return None
    return normalized


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
    """Presentación comparable; ``total_base`` representa el paquete completo."""

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
                profile.taxonomy.product_type is not None for profile in self.profiles
            ),
            "valid_gtin": sum(
                profile.canonical_gtin is not None for profile in self.profiles
            ),
            "exact_gtin_groups_cross_supermarket": len(self.exact_gtin_groups),
            "exact_gtin_groups_comparison_ready": sum(
                group.comparison_status == "ready"
                for group in self.exact_gtin_groups
            ),
            "exact_gtin_groups_review_required": sum(
                group.comparison_status == "review_required"
                for group in self.exact_gtin_groups
            ),
            "source_products_in_exact_gtin_groups": len(exact_members),
            "review_candidates": len(self.candidates),
            "presentation_conflicts": sum(
                profile.presentation_status == "conflict"
                for profile in self.profiles
            ),
            "presentation_ambiguous_multipacks": sum(
                profile.presentation_status == "ambiguous_multipack"
                for profile in self.profiles
            ),
            "paiz_source_presentation_overrides": sum(
                profile.presentation_status == "name_preferred_source_conflict"
                for profile in self.profiles
            ),
            "generic_brand_placeholders": sum(
                profile.record.source_brand is not None
                and profile.normalized_brand is None
                for profile in self.profiles
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


_TAXONOMY_RULES = (
    _TaxonomyRule("desodorante", "Cuidado personal", "Higiene", "Desodorante", any_terms=("desodorante",)),
    _TaxonomyRule("shampoo", "Cuidado personal", "Cabello", "Shampoo", any_terms=("shampoo", "champu")),
    _TaxonomyRule("acondicionador", "Cuidado personal", "Cabello", "Acondicionador", any_terms=("acondicionador",)),
    _TaxonomyRule("pasta_dental", "Cuidado personal", "Higiene oral", "Pasta dental", any_terms=("pasta dental", "crema dental")),
    _TaxonomyRule("cepillo_dental", "Cuidado personal", "Higiene oral", "Cepillo dental", ("cepillo",), ("dental", "dientes")),
    _TaxonomyRule("enjuague_bucal", "Cuidado personal", "Higiene oral", "Enjuague bucal", any_terms=("enjuague bucal", "enjuague oral")),
    _TaxonomyRule("agua_micelar", "Cuidado personal", "Cuidado facial", "Agua micelar", ("agua", "micelar")),
    _TaxonomyRule("tinte_cabello", "Cuidado personal", "Cabello", "Tinte para cabello", any_terms=("tinte",), forbidden_terms=("pintura",)),
    _TaxonomyRule("protector_diario", "Cuidado personal", "Higiene femenina", "Protector diario", ("protector",), ("diario", "diarios")),
    _TaxonomyRule("toalla_femenina", "Cuidado personal", "Higiene femenina", "Toalla femenina", ("toalla",), ("femenina", "femeninas", "sanitaria", "sanitarias")),
    _TaxonomyRule("panal", "Bebés", "Pañales", "Pañal", any_terms=("panal", "panales")),
    _TaxonomyRule("toallita_humeda", "Bebés", "Higiene", "Toallita húmeda", any_terms=("toallitas humedas", "toallas humedas")),
    _TaxonomyRule("jabon", "Cuidado personal", "Higiene", "Jabón", any_terms=("jabon",)),
    _TaxonomyRule("detergente", "Limpieza", "Lavandería", "Detergente", any_terms=("detergente",)),
    _TaxonomyRule("suavizante", "Limpieza", "Lavandería", "Suavizante", any_terms=("suavizante",)),
    _TaxonomyRule("lavaplatos", "Limpieza", "Cocina", "Lavaplatos", any_terms=("lavaplatos", "lavatrastes")),
    _TaxonomyRule("desinfectante", "Limpieza", "Superficies", "Desinfectante", any_terms=("desinfectante",)),
    _TaxonomyRule("cloro", "Limpieza", "Superficies", "Cloro", any_terms=("cloro", "lejia")),
    _TaxonomyRule("limpiador", "Limpieza", "Superficies", "Limpiador", any_terms=("limpiador",)),
    _TaxonomyRule("aromatizante", "Hogar", "Ambientadores", "Aromatizante", any_terms=("aromatizante", "ambientador")),
    _TaxonomyRule("papel_higienico", "Hogar", "Papel", "Papel higiénico", ("papel", "higienico")),
    _TaxonomyRule("papel_toalla", "Hogar", "Papel", "Papel toalla", any_terms=("papel toalla", "toalla de papel", "toallas de papel")),
    _TaxonomyRule("servilleta", "Hogar", "Papel", "Servilleta", any_terms=("servilleta", "servilletas")),
    _TaxonomyRule("alimento_perro", "Mascotas", "Alimento para mascotas", "Alimento para perro", any_terms=("alimento para perro", "comida para perro", "alimento canino")),
    _TaxonomyRule("alimento_gato", "Mascotas", "Alimento para mascotas", "Alimento para gato", any_terms=("alimento para gato", "comida para gato", "alimento felino")),
    _TaxonomyRule("atun", "Alimentos", "Conservas", "Atún", any_terms=("atun",)),
    _TaxonomyRule("sardina", "Alimentos", "Conservas", "Sardina", any_terms=("sardina", "sardinas")),
    _TaxonomyRule("yogurt", "Alimentos", "Lácteos", "Yogurt", any_terms=("yogurt", "yoghurt")),
    _TaxonomyRule("avena", "Alimentos", "Cereales", "Avena", any_terms=("avena", "mosh")),
    _TaxONOMY_RULES_PLACEHOLDER
)