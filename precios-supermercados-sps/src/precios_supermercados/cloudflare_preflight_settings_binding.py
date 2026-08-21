"""Vincula Script Settings parseados con el preflight offline de Cloudflare.

El preflight histórico conserva flags declarados dentro del snapshot de
despliegue. Esta capa adicional exige que tracing/observability coincidan con
una respuesta de Script Settings parseada de forma independiente, evitando que
esos flags por sí solos satisfagan la preparación técnica.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import NoReturn

from precios_supermercados.cloudflare_live_preflight import (
    CloudflareDeploymentEvidence,
    CloudflareLivePreflightAssessment,
    assess_cloudflare_live_preflight,
)
from precios_supermercados.cloudflare_script_settings import CloudflareScriptSettingsEvidence
from precios_supermercados.edge_provenance import canonical_json_bytes
from precios_supermercados.edge_provenance_run import EdgeProvenanceRunManifest

SETTINGS_BOUND_PREFLIGHT_SCHEMA_VERSION = "1"
_DOMAIN = b"precios-sps/cloudflare-settings-bound-preflight/v1\0"
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_FULL_RATE_PPM = 1_000_000
_MANDATORY_BLOCKERS = (
    "human_live_authorization_required",
    "sps_context_unconfirmed",
    "production_authority_not_established",
)


class CloudflareSettingsBindingError(ValueError):
    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code


def _fail(code: str) -> NoReturn:
    raise CloudflareSettingsBindingError(code)


def _sha256(value: object, code: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        _fail(code)
    return value


@dataclass(frozen=True, slots=True)
class CloudflareSettingsBoundPreflightAssessment:
    """Assessment cuya configuración observable queda ligada a Script Settings."""

    base_preflight_digest: str
    settings_evidence_digest: str
    technical_prerequisites_satisfied: bool
    ready_for_human_live_authorization_request: bool
    blockers: tuple[str, ...]
    schema_version: str = SETTINGS_BOUND_PREFLIGHT_SCHEMA_VERSION
    production_authority: bool = False

    def __post_init__(self) -> None:
        if self.schema_version != SETTINGS_BOUND_PREFLIGHT_SCHEMA_VERSION:
            _fail("settings_bound_schema_version_invalid")
        object.__setattr__(
            self,
            "base_preflight_digest",
            _sha256(self.base_preflight_digest, "settings_bound_base_digest_invalid"),
        )
        object.__setattr__(
            self,
            "settings_evidence_digest",
            _sha256(self.settings_evidence_digest, "settings_bound_settings_digest_invalid"),
        )
        if not isinstance(self.technical_prerequisites_satisfied, bool):
            _fail("settings_bound_technical_invalid")
        if not isinstance(self.ready_for_human_live_authorization_request, bool):
            _fail("settings_bound_ready_invalid")
        if self.ready_for_human_live_authorization_request != self.technical_prerequisites_satisfied:
            _fail("settings_bound_readiness_inconsistent")
        if not isinstance(self.blockers, tuple) or any(
            not isinstance(item, str) or not item for item in self.blockers
        ):
            _fail("settings_bound_blockers_invalid")
        if len(set(self.blockers)) != len(self.blockers):
            _fail("settings_bound_blockers_duplicate")
        if not set(_MANDATORY_BLOCKERS).issubset(self.blockers):
            _fail("settings_bound_mandatory_blocker_missing")
        if self.production_authority is not False:
            _fail("settings_bound_production_authority_forbidden")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "base_preflight_digest": self.base_preflight_digest,
            "blockers": list(self.blockers),
            "production_authority": self.production_authority,
            "ready_for_human_live_authorization_request": self.ready_for_human_live_authorization_request,
            "schema_version": self.schema_version,
            "settings_evidence_digest": self.settings_evidence_digest,
            "technical_prerequisites_satisfied": self.technical_prerequisites_satisfied,
        }

    @property
    def digest(self) -> str:
        return hashlib.sha256(_DOMAIN + canonical_json_bytes(self.canonical_dict())).hexdigest()


def bind_script_settings_to_preflight(
    *,
    manifest: EdgeProvenanceRunManifest,
    deployment: CloudflareDeploymentEvidence,
    settings: CloudflareScriptSettingsEvidence,
) -> CloudflareSettingsBoundPreflightAssessment:
    """Exige que los flags del deployment estén demostrados por Script Settings."""

    if not isinstance(settings, CloudflareScriptSettingsEvidence):
        _fail("settings_evidence_invalid")
    if settings.production_authority is not False:
        _fail("settings_evidence_production_authority_invalid")

    base: CloudflareLivePreflightAssessment = assess_cloudflare_live_preflight(
        manifest,
        deployment,
    )

    settings_blockers: list[str] = []
    if settings.observability_enabled is not True:
        settings_blockers.append("settings_observability_disabled")
    if settings.traces_enabled is not True:
        settings_blockers.append("settings_tracing_disabled")
    if settings.traces_head_sampling_rate_ppm != _FULL_RATE_PPM:
        settings_blockers.append("settings_tracing_sampling_not_full")
    if deployment.observability_enabled != settings.observability_enabled:
        settings_blockers.append("deployment_settings_observability_mismatch")
    if deployment.tracing_enabled != settings.traces_enabled:
        settings_blockers.append("deployment_settings_tracing_mismatch")
    if deployment.tracing_sampling_rate_ppm != settings.traces_head_sampling_rate_ppm:
        settings_blockers.append("deployment_settings_sampling_mismatch")

    base_technical = [blocker for blocker in base.blockers if blocker not in _MANDATORY_BLOCKERS]
    technical_blockers = tuple(dict.fromkeys([*base_technical, *settings_blockers]))
    technical_ok = len(technical_blockers) == 0
    blockers = (*technical_blockers, *_MANDATORY_BLOCKERS)

    return CloudflareSettingsBoundPreflightAssessment(
        base_preflight_digest=base.digest,
        settings_evidence_digest=settings.digest,
        technical_prerequisites_satisfied=technical_ok,
        ready_for_human_live_authorization_request=technical_ok,
        blockers=blockers,
    )
