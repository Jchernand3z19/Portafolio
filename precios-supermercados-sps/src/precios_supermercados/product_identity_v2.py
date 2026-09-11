"""Identidad de producto v2: normalización semántica y candidatos conservadores.

Esta capa separa cuatro pasos que no deben confundirse:

1. normalización de texto/unidades;
2. extracción de atributos semánticos;
3. generación de candidatos;
4. decisión de identidad.

Los candidatos sin identificador global siguen siendo ``review_required``. El
ranking numérico sólo ordena la cola privada; nunca confirma identidad ni puede
compensar un conflicto material.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, replace
from decimal import Decimal, ROUND_HALF_UP
from difflib import SequenceMatcher
from typing import Iterable

from .identifiers import generate_gtin_product_id
from .product_homologation import (
    ExactGtinGroup,
    HomologationResult,
    MatchCandidate,
    PresentationSignature,
    ProductHomologationError,
    ProductProfile,
    SourceProductRecord,
    TaxonomyAssignment,
    assign_taxonomy,
    fold_text,
    normalize_brand,
    presentations_compatible,
    profile_product,
    resolve_presentation,
)

IDENTITY_NORMALIZATION_VERSION = "product-homologation-v2"

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

# Alias demostrados en los catálogos actuales. Sólo se usan cuando la marca
# fuente es genérica/ausente o para detectar una contradicción explícita.
_BRAND_ALIASES = {
    "bonovo": "bonovo",
    "don cristobal": "don cristobal",
    "el ranchero": "el ranchero",
    "gallina feliz": "gallina feliz",
    "great value": "great value",
    "marca marketside": "marketside",
    "marketside": "marketside",
    "mister huevo": "mister huevo",
    "norteno": "norteno",
    "nutri yema": "nutri yema",
    "nutriyema": "nutri yema",
    "rica yema": "rica yema",
    "suli": "suli",
}

_COUNT_ALIASES = r"u|uni|un|und|unds|unid|unids|ud|uds|unidad|unidades"
_COUNT_RE = re.compile(
    rf"(?<!\w)(?P<count>\d{{1,4}})\s*(?P<unit>{_COUNT_ALIASES})(?!\w)",
    re.IGNORECASE,
)
_EGG_COUNT_RE = re.compile(
    rf"(?<!\w)(?P<count>\d{{1,3}})\s*(?P<size>xl|g|m|p)?\s*(?P<unit>{_COUNT_ALIASES})(?!\w)",
    re.IGNORECASE,
)
_MG_RE = re.compile(r"(?<!\w)(?P<amount>\d+(?:[.,]\d+)?)\s*mg(?!\w)", re.IGNORECASE)
_LIBRA_RE = re.compile(r"(?<!\w)(?P<amount>\d+(?:[.,]\d+)?)\s*libras?(?!\w)", re.IGNORECASE)
_GRAMOS_RE = re.compile(r"(?<!\w)(?P<amount>\d+(?:[.,]\d+)?)\s*grs?(?:\.)?(?!\w)", re.IGNORECASE)
_LITROS_RE = re.compile(r"(?<!\w)(?P<amount>\d+(?:[.,]\d+)?)\s*lts?(?:\.)?(?!\w)", re.IGNORECASE)

_EGG_FALSE_CONTEXT = frozenset(
    {"tallarin", "tallarines", "fideo", "fideos", "mayonesa", "kinder", "toro"}
)

_VARIANT_GROUPS = (
    frozenset({"original", "regular"}),
    frozenset({"zero", "sin azucar"}),
    frozenset({"light", "diet", "bajo en azucar"}),
    frozenset({"entera", "entero"}),
    frozenset({"descremada", "descremado"}),
    frozenset({"semidescremada", "semidescremado"}),
)
_FLAVORS = frozenset(
    {
        "vainilla",
        "chocolate",
        "fresa",
        "limon",
        "naranja",
        "manzana",
        "uva",
        "pina",
        "coco",
        "mango",
    }
)

_MATCH_STOPWORDS = frozenset(
    {
        "de",
        "del",
        "la",
        "el",
        "los",
        "las",
        "y",
        "con",
        "para",
        "en",
        "por",
        "doy",
        "pack",
        "packs",
        "paquete",
        "paquetes",
        "caja",
        "carton",
        "botella",
        "bolsa",
        "u",
        "uni",
        "un",
        "und",
        "unds",
        "unid",
        "unids",
        "ud",
        "uds",
        "unidad",
        "unidades",
        "mg",
        "g",
        "gr",
        "grs",
        "gramo",
        "gramos",
        "kg",
        "lb",
        "lbs",
        "libra",
        "libras",
        "oz",
        "ml",
        "l",
        "lt",
        "litro",
        "litros",
        "x",
    }
)


@dataclass(frozen=True, slots=True)
class BrandResolution:
    canonical_brand: str | None
    source: str
    source_brand: str | None
    name_brand: str | None
    conflict: bool = False


@dataclass(frozen=True, slots=True)
class CandidateEvidence:
    left_source_record_id: str
    right_source_record_id: str
    decision_state: str
    ranking_score: Decimal
    matching_signals: tuple[str, ...]
    conflict_signals: tuple[str, ...]


def _phrase_present(text: str, phrase: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text) is not None


def build_brand_lexicon(records: Iterable[SourceProductRecord]) -> frozenset[str]:
    """Crea un vocabulario de marcas ya observadas como marcas fuente reales."""
    values = {
        brand
        for record in records
        if (brand := normalize_brand(record.source_brand)) is not None
    }
    values.update(_BRAND_ALIASES.values())
    return frozenset(values)


def resolve_brand(
    record: SourceProductRecord,
    *,
    brand_lexicon: frozenset[str],
) -> BrandResolution:
    source_brand = normalize_brand(record.source_brand)
    name = fold_text(record.source_name) or ""
    matches: set[str] = set()

    for alias, canonical in _BRAND_ALIASES.items():
        if _phrase_present(name, alias):
            matches.add(canonical)
    for canonical in brand_lexicon:
        if _phrase_present(name, canonical):
            matches.add(canonical)

    # Preferimos el match de frase más larga cuando todos los matches son
    # anidados (p. ej. una marca de dos palabras que contiene otra corta).
    if len(matches) > 1:
        longest = max(matches, key=len)
        if all(candidate == longest or _phrase_present(longest, candidate) for candidate in matches):
            matches = {longest}

    name_brand = next(iter(matches)) if len(matches) == 1 else None
    if source_brand is not None:
        if name_brand is not None and name_brand != source_brand:
            return BrandResolution(
                canonical_brand=source_brand,
                source="source_conflict",
                source_brand=source_brand,
                name_brand=name_brand,
                conflict=True,
            )
        return BrandResolution(source_brand, "source", source_brand, name_brand)
    if name_brand is not None:
        return BrandResolution(name_brand, "name_known_brand", None, name_brand)
    return BrandResolution(None, "missing", None, None)


def _egg_false_context(text: str) -> bool:
    tokens = set(text.split())
    return bool(tokens & _EGG_FALSE_CONTEXT)


def is_shell_egg(record: SourceProductRecord, taxonomy: TaxonomyAssignment | None = None) -> bool:
    text = fold_text(record.source_name) or ""
    taxonomy = taxonomy or assign_taxonomy(record)
    if taxonomy.product_type != "Huevo" or _egg_false_context(text):
        return False
    if "claras" in text.split() or "clara" in text.split():
        return False
    return bool(re.search(r"\bhuevos?\b", text))


def canonical_egg_size(record: SourceProductRecord, taxonomy: TaxonomyAssignment | None = None) -> str | None:
    if not is_shell_egg(record, taxonomy):
        return None
    text = fold_text(record.source_name) or ""
    if re.search(r"\b(?:extra grande|extra grandes|xl)\b", text) or re.search(
        rf"\d+\s*xl\s*(?:{_COUNT_ALIASES})\b", text
    ):
        return "Extra grande"
    if re.search(r"\bjumbo\b", text):
        return "Jumbo"
    if re.search(r"\b(?:pequeno|pequenos|pequena|pequenas)\b", text) or re.search(r"\bcarton\s+p\b", text):
        return "Pequeño"
    if re.search(r"\b(?:mediano|medianos|mediana|medianas)\b", text) or re.search(r"\bcarton\s+m\b", text) or re.search(r"\bhuevos?\s+(?:liso\s+)?m\b", text):
        return "Mediano"
    if re.search(r"\b(?:grande|grandes)\b", text) or re.search(r"\bcarton\s+g\b", text) or re.search(r"\bhuevos?\s+g\b", text) or re.search(
        rf"\d+\s*g\s*(?:{_COUNT_ALIASES})\b", text
    ):
        return "Grande"
    return None


def assign_taxonomy_v2(record: SourceProductRecord) -> TaxonomyAssignment:
    """Corrige falsos positivos demostrados antes de aplicar la taxonomía v1."""
    text = fold_text(record.source_name) or ""
    tokens = set(text.split())
    if {"tallarin", "tallarines", "fideo", "fideos"} & tokens and "huevo" in tokens:
        return TaxonomyAssignment("Alimentos", "Pastas", "Pasta", "v2_egg_noodle")
    if "mayonesa" in tokens:
        return TaxonomyAssignment("Alimentos", "Salsas y aderezos", "Mayonesa", "v2_mayonesa")
    if "kinder" in tokens and "huevo" in tokens:
        return TaxonomyAssignment("Alimentos", "Dulces y chocolates", "Chocolate", "v2_kinder_huevo")
    if "toro" in tokens and ("huevo" in tokens or "huevos" in tokens):
        return TaxonomyAssignment(None, None, None, "v2_huevos_toro_unresolved")
    return assign_taxonomy(record)


def _replace_mg(match: re.Match[str]) -> str:
    amount = Decimal(match.group("amount").replace(",", ".")) / Decimal("1000")
    return f"{format(amount.normalize(), 'f')} g"


def _normalize_parser_text(
    value: str | None,
    *,
    shell_egg: bool,
) -> str | None:
    if value is None:
        return None
    text = " ".join(value.split())
    if shell_egg:
        text = _EGG_COUNT_RE.sub(lambda match: f"{match.group('count')} unidades", text)
    else:
        text = _COUNT_RE.sub(lambda match: f"{match.group('count')} unidades", text)
    text = _MG_RE.sub(_replace_mg, text)
    text = _LIBRA_RE.sub(lambda match: f"{match.group('amount')} lb", text)
    text = _GRAMOS_RE.sub(lambda match: f"{match.group('amount')} g", text)
    text = _LITROS_RE.sub(lambda match: f"{match.group('amount')} l", text)
    return text


def resolve_presentation_v2(
    record: SourceProductRecord,
    taxonomy: TaxonomyAssignment | None = None,
) -> tuple[PresentationSignature | None, str]:
    taxonomy = taxonomy or assign_taxonomy_v2(record)
    shell_egg = is_shell_egg(record, taxonomy)
    normalized = SourceProductRecord(
        source_record_id=record.source_record_id,
        supermarket_id=record.supermarket_id,
        source_name=_normalize_parser_text(record.source_name, shell_egg=shell_egg) or record.source_name,
        source_brand=record.source_brand,
        source_presentation=_normalize_parser_text(record.source_presentation, shell_egg=shell_egg),
        source_category=record.source_category,
        barcode=record.barcode,
    )
    return resolve_presentation(normalized)


def candidate_presentations_compatible(left: PresentationSignature, right: PresentationSignature) -> bool:
    """Compatibilidad para GENERAR candidatos; nunca confirma identidad."""
    if presentations_compatible(left, right):
        return True
    if left.dimension != right.dimension or left.pack_count != right.pack_count:
        return False
    if left.dimension in {"count", "ounce"}:
        return False
    larger = max(left.total_base, right.total_base)
    difference = abs(left.total_base - right.total_base)
    relative = difference / larger
    if left.dimension == "mass_g":
        absolute_limit = Decimal("15") if larger < Decimal("1000") else Decimal("30")
        relative_limit = Decimal("0.02") if larger < Decimal("1000") else Decimal("0.015")
        return difference <= absolute_limit and relative <= relative_limit
    if left.dimension == "volume_ml":
        absolute_limit = Decimal("20") if larger < Decimal("1000") else Decimal("30")
        relative_limit = Decimal("0.02") if larger < Decimal("1000") else Decimal("0.015")
        return difference <= absolute_limit and relative <= relative_limit
    return False


def _matching_tokens(profile: ProductProfile) -> tuple[str, ...]:
    tokens = (fold_text(profile.record.source_name) or "").split()
    brand_tokens = set((profile.normalized_brand or "").split())
    type_tokens = set((fold_text(profile.taxonomy.product_type) or "").split())
    result: list[str] = []
    for token in tokens:
        if token in _MATCH_STOPWORDS or token in brand_tokens or token in type_tokens or token.isdigit():
            continue
        if re.fullmatch(r"\d+(?:[.,]\d+)?", token):
            continue
        result.append(token)
    return tuple(result)


def _name_similarity(left: ProductProfile, right: ProductProfile) -> Decimal:
    left_tokens = set(left.matching_tokens)
    right_tokens = set(right.matching_tokens)
    if not left_tokens or not right_tokens:
        return Decimal("0")
    jaccard = Decimal(len(left_tokens & right_tokens)) / Decimal(len(left_tokens | right_tokens))
    sequence = Decimal(
        str(SequenceMatcher(None, " ".join(left.matching_tokens), " ".join(right.matching_tokens)).ratio())
    )
    return (jaccard * Decimal("0.6") + sequence * Decimal("0.4")).quantize(Decimal("0.0001"))


def _variant_labels(profile: ProductProfile) -> frozenset[str]:
    text = fold_text(profile.record.source_name) or ""
    labels: set[str] = set()
    for group in _VARIANT_GROUPS:
        for label in group:
            if _phrase_present(text, label):
                labels.add(label)
    for flavor in _FLAVORS:
        if _phrase_present(text, flavor):
            labels.add(f"flavor:{flavor}")
    egg_size = canonical_egg_size(profile.record, profile.taxonomy)
    if egg_size is not None:
        labels.add(f"egg_size:{fold_text(egg_size)}")
    return frozenset(labels)


def _hard_conflicts(left: ProductProfile, right: ProductProfile) -> tuple[str, ...]:
    conflicts: set[str] = set()
    if left.canonical_gtin is not None and right.canonical_gtin is not None and left.canonical_gtin != right.canonical_gtin:
        conflicts.add("different_valid_gtin")
    if left.taxonomy.product_type != right.taxonomy.product_type:
        conflicts.add("product_type_conflict")
    if left.normalized_brand and right.normalized_brand and left.normalized_brand != right.normalized_brand:
        conflicts.add("brand_conflict")
    if left.presentation is None or right.presentation is None:
        conflicts.add("presentation_missing")
    elif not candidate_presentations_compatible(left.presentation, right.presentation):
        conflicts.add("presentation_conflict")

    left_labels = _variant_labels(left)
    right_labels = _variant_labels(right)
    left_sizes = {item for item in left_labels if item.startswith("egg_size:")}
    right_sizes = {item for item in right_labels if item.startswith("egg_size:")}
    if left_sizes and right_sizes and left_sizes != right_sizes:
        conflicts.add("egg_size_conflict")
    left_flavors = {item for item in left_labels if item.startswith("flavor:")}
    right_flavors = {item for item in right_labels if item.startswith("flavor:")}
    if left_flavors and right_flavors and left_flavors != right_flavors:
        conflicts.add("flavor_conflict")

    # Grupos de formulación: sólo contradicen si ambos productos declaran de
    # forma explícita grupos diferentes.
    def formulation_group(labels: frozenset[str]) -> int | None:
        for index, group in enumerate(_VARIANT_GROUPS):
            if any(label in labels for label in group):
                return index
        return None

    left_group = formulation_group(left_labels)
    right_group = formulation_group(right_labels)
    if left_group is not None and right_group is not None and left_group != right_group:
        conflicts.add("variant_conflict")
    return tuple(sorted(conflicts))


def _candidate_score(left: ProductProfile, right: ProductProfile) -> tuple[Decimal, tuple[str, ...]]:
    """Score sólo para ordenar review candidates; no representa probabilidad."""
    signals: list[str] = ["same_product_type", "presentation_candidate_compatible"]
    score = Decimal("0.45")
    if left.normalized_brand and right.normalized_brand and left.normalized_brand == right.normalized_brand:
        signals.append("same_canonical_brand")
        score += Decimal("0.20")
    elif bool(left.normalized_brand) != bool(right.normalized_brand):
        signals.append("one_brand_missing")
        score += Decimal("0.05")
    similarity = _name_similarity(left, right)
    if similarity > 0:
        signals.append(f"name_similarity:{format(similarity, 'f')}")
    score += similarity * Decimal("0.55")
    return min(score, Decimal("1")).quantize(Decimal("0.0001")), tuple(signals)


def _presentation_bucket(value: PresentationSignature) -> tuple[str, int, int]:
    if value.dimension in {"count", "ounce"}:
        bucket = int(value.total_base.to_integral_value(rounding=ROUND_HALF_UP))
    else:
        bucket = int((value.total_base / Decimal("25")).to_integral_value(rounding=ROUND_HALF_UP))
    return value.dimension, value.pack_count, bucket


def profile_product_v2(
    record: SourceProductRecord,
    *,
    brand_lexicon: frozenset[str],
) -> ProductProfile:
    base = profile_product(record)
    taxonomy = assign_taxonomy_v2(record)
    brand = resolve_brand(record, brand_lexicon=brand_lexicon)
    presentation, presentation_status = resolve_presentation_v2(record, taxonomy)
    provisional = replace(
        base,
        normalized_brand=brand.canonical_brand,
        taxonomy=taxonomy,
        presentation=presentation,
        presentation_status=presentation_status,
    )
    return replace(provisional, matching_tokens=_matching_tokens(provisional))


def _exact_groups(profiles: tuple[ProductProfile, ...]) -> tuple[ExactGtinGroup, ...]:
    index: dict[str, list[ProductProfile]] = defaultdict(list)
    for profile in profiles:
        if profile.canonical_gtin is not None:
            index[profile.canonical_gtin].append(profile)
    groups: list[ExactGtinGroup] = []
    for gtin, members in sorted(index.items()):
        supermarkets = sorted({member.record.supermarket_id for member in members})
        if len(supermarkets) < 2:
            continue
        conflicts: set[str] = set()
        if any(member.presentation_status == "conflict" for member in members):
            conflicts.add("source_presentation_conflict")
        if any(member.presentation_status == "ambiguous_multipack" for member in members):
            conflicts.add("ambiguous_multipack_presentation")
        types = {member.taxonomy.product_type for member in members if member.taxonomy.product_type is not None}
        if len(types) > 1:
            conflicts.add("product_type_conflict")
        for idx, left in enumerate(members):
            for right in members[idx + 1 :]:
                if left.record.supermarket_id == right.record.supermarket_id:
                    continue
                pair_conflicts = _hard_conflicts(left, right)
                for reason in pair_conflicts:
                    if reason == "presentation_conflict":
                        conflicts.add("cross_source_presentation_conflict")
                    elif reason not in {"different_valid_gtin", "presentation_missing"}:
                        conflicts.add(reason)
        groups.append(
            ExactGtinGroup(
                canonical_gtin=gtin,
                canonical_product_id=generate_gtin_product_id(gtin),
                source_record_ids=tuple(member.record.source_record_id for member in members),
                supermarket_ids=tuple(supermarkets),
                comparison_status="review_required" if conflicts else "ready",
                conflict_reasons=tuple(sorted(conflicts)),
            )
        )
    return tuple(groups)


def homologate_products_v2(
    records: Iterable[SourceProductRecord],
    *,
    candidate_threshold: Decimal = Decimal("0.72"),
) -> HomologationResult:
    if candidate_threshold < 0 or candidate_threshold > 1:
        raise ProductHomologationError("candidate_threshold_invalid")
    records = tuple(records)
    if len({record.source_record_id for record in records}) != len(records):
        raise ProductHomologationError("source_record_id_duplicate")
    brand_lexicon = build_brand_lexicon(records)
    profiles = tuple(
        sorted(
            (profile_product_v2(record, brand_lexicon=brand_lexicon) for record in records),
            key=lambda profile: profile.record.source_record_id,
        )
    )
    exact_groups = _exact_groups(profiles)

    blocks: dict[tuple[str, str, int, int], list[ProductProfile]] = defaultdict(list)
    for profile in profiles:
        if (
            profile.taxonomy.product_type is None
            or profile.presentation is None
            or profile.presentation_status in {"conflict", "ambiguous_multipack"}
        ):
            continue
        dimension, pack_count, bucket = _presentation_bucket(profile.presentation)
        blocks[(profile.taxonomy.product_type, dimension, pack_count, bucket)].append(profile)

    candidates: list[MatchCandidate] = []
    seen: set[tuple[str, str]] = set()
    for members in blocks.values():
        for index, left in enumerate(members):
            for right in members[index + 1 :]:
                if left.record.supermarket_id == right.record.supermarket_id:
                    continue
                pair = tuple(sorted((left.record.source_record_id, right.record.source_record_id)))
                if pair in seen:
                    continue
                seen.add(pair)
                conflicts = _hard_conflicts(left, right)
                if conflicts:
                    continue
                if left.canonical_gtin is not None and right.canonical_gtin is not None:
                    continue
                score, signals = _candidate_score(left, right)
                if score < candidate_threshold:
                    continue
                candidate_brand = left.normalized_brand or right.normalized_brand or "unknown"
                candidates.append(
                    MatchCandidate(
                        left_source_record_id=left.record.source_record_id,
                        right_source_record_id=right.record.source_record_id,
                        left_supermarket_id=left.record.supermarket_id,
                        right_supermarket_id=right.record.supermarket_id,
                        product_type=left.taxonomy.product_type or "unknown",
                        normalized_brand=candidate_brand,
                        score=score,
                        reason="candidate_only:" + "+".join(signals),
                        status="review_required",
                    )
                )
    candidates.sort(key=lambda candidate: (-candidate.score, candidate.left_source_record_id, candidate.right_source_record_id))
    return HomologationResult(profiles=profiles, exact_gtin_groups=exact_groups, candidates=tuple(candidates))


def explain_candidate(
    left: ProductProfile,
    right: ProductProfile,
) -> CandidateEvidence:
    conflicts = _hard_conflicts(left, right)
    if conflicts:
        return CandidateEvidence(
            left.record.source_record_id,
            right.record.source_record_id,
            "conflict",
            Decimal("0"),
            (),
            conflicts,
        )
    score, signals = _candidate_score(left, right)
    return CandidateEvidence(
        left.record.source_record_id,
        right.record.source_record_id,
        "review_candidate",
        score,
        signals,
        (),
    )


def audit_identity_quality(result: HomologationResult) -> dict[str, object]:
    """Métricas derivadas sin mutar catálogo ni histórico comercial."""
    profiles = result.profiles
    exact_multi = [group for group in result.exact_gtin_groups if len(group.supermarket_ids) >= 2]
    cluster_sizes: dict[str, int] = defaultdict(int)
    for group in exact_multi:
        cluster_sizes[str(len(group.source_record_ids))] += 1
    retailer_collisions = 0
    for group in exact_multi:
        members = [profile for profile in profiles if profile.record.source_record_id in group.source_record_ids]
        supermarkets = [profile.record.supermarket_id for profile in members]
        if len(supermarkets) != len(set(supermarkets)):
            retailer_collisions += 1
    return {
        "source_products": len(profiles),
        "normalized_brand": sum(profile.normalized_brand is not None for profile in profiles),
        "missing_brand": sum(profile.normalized_brand is None for profile in profiles),
        "normalized_presentation": sum(profile.presentation is not None for profile in profiles),
        "missing_or_conflicting_presentation": sum(
            profile.presentation is None for profile in profiles
        ),
        "exact_identity_groups": len(result.exact_gtin_groups),
        "exact_comparable_groups": sum(group.comparison_status == "ready" for group in result.exact_gtin_groups),
        "exact_review_groups": sum(group.comparison_status == "review_required" for group in result.exact_gtin_groups),
        "review_candidates": len(result.candidates),
        "multi_retailer_clusters": len(exact_multi),
        "cluster_size_distribution": dict(sorted(cluster_sizes.items(), key=lambda item: int(item[0]))),
        "retailer_collision_clusters": retailer_collisions,
        "individual_without_global_identity": sum(profile.canonical_gtin is None for profile in profiles),
    }
