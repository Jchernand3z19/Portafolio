"""Contrato efímero de las señales débiles de sesión observadas al seleccionar SPS.

La radiografía canónica confirmó como cambios de ciudad ``vtexsegment`` y
``vtexsession`` además del ``request:regionid`` fuerte. Este módulo no convierte
esas cookies en identidad por sí mismas; exige que una futura ejecución que salga
del BrowserContext reproduzca **todas** las señales observadas, sin persistir sus
valores raw.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping, NoReturn

SPS_BINDING_EVIDENCE = (
    "location_binding_radiography:sha256:"
    "80f2e4d333043a38954603c9c72086d241ac9b5a1cc1f10b71a9fde772588d95"
)
SPS_SESSION_SIGNAL_FINGERPRINTS = MappingProxyType(
    {
        "vtexsegment": "475c2feb7ffafa1c3bdd668c5c864b94602e14d3aa26e710226c64dd4a4b65d3",
        "vtexsession": "a25a19b8bc35038143f7aa0dc6b711f4a86107e3db8e2df09e91b225d6089b1e",
    }
)


class SpsSessionContextError(ValueError):
    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code


def _fail(code: str, message: str | None = None) -> NoReturn:
    raise SpsSessionContextError(code, message)


def _fingerprint(value: str) -> str:
    rendered = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _cookie_value(value: object, code: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 8192
        or "\r" in value
        or "\n" in value
        or ";" in value
    ):
        _fail(code)
    return value


@dataclass(frozen=True, slots=True)
class VerifiedSpsSessionContext:
    binding_evidence: str
    signal_fingerprints: Mapping[str, str]
    _raw_values: Mapping[str, str] = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.binding_evidence != SPS_BINDING_EVIDENCE:
            _fail("sps_session_binding_evidence_mismatch")
        if dict(self.signal_fingerprints) != dict(SPS_SESSION_SIGNAL_FINGERPRINTS):
            _fail("sps_session_fingerprint_set_mismatch")
        raw = dict(self._raw_values)
        if set(raw) != set(SPS_SESSION_SIGNAL_FINGERPRINTS):
            _fail("sps_session_signal_set_incomplete")
        for key, expected in SPS_SESSION_SIGNAL_FINGERPRINTS.items():
            value = _cookie_value(raw.get(key), f"sps_session_{key}_invalid")
            if _fingerprint(value) != expected:
                _fail(f"sps_session_{key}_fingerprint_mismatch")
        object.__setattr__(self, "signal_fingerprints", SPS_SESSION_SIGNAL_FINGERPRINTS)
        object.__setattr__(self, "_raw_values", MappingProxyType(raw))

    def __repr__(self) -> str:
        return (
            "VerifiedSpsSessionContext("
            f"binding_evidence={self.binding_evidence!r}, "
            f"signal_fingerprints={dict(self.signal_fingerprints)!r}, "
            "raw_values='<redacted>')"
        )

    @property
    def complete(self) -> bool:
        return True

    def public_dict(self) -> dict[str, object]:
        return {
            "binding_evidence": self.binding_evidence,
            "signal_fingerprints": dict(self.signal_fingerprints),
            "session_context_complete": True,
            "raw_values_exposed": False,
        }

    def wire_signals(self) -> dict[str, dict[str, str]]:
        return {
            key: {
                "fingerprint": fingerprint,
                "rawValue": self._raw_values[key],
            }
            for key, fingerprint in self.signal_fingerprints.items()
        }

    def cookie_header(self) -> str:
        return "; ".join(f"{key}={self._raw_values[key]}" for key in sorted(self._raw_values))


def verify_sps_session_context(
    cookies: Mapping[str, object],
    *,
    binding_evidence: str = SPS_BINDING_EVIDENCE,
) -> VerifiedSpsSessionContext:
    """Verifica los valores post-ciudad en memoria contra la radiografía canónica."""

    if not isinstance(cookies, Mapping):
        _fail("sps_session_cookies_mapping_required")
    normalized = {str(key).casefold(): value for key, value in cookies.items()}
    raw: dict[str, str] = {}
    for key in SPS_SESSION_SIGNAL_FINGERPRINTS:
        if key not in normalized:
            _fail(f"sps_session_{key}_missing")
        raw[key] = _cookie_value(normalized[key], f"sps_session_{key}_invalid")
    return VerifiedSpsSessionContext(
        binding_evidence=binding_evidence,
        signal_fingerprints=SPS_SESSION_SIGNAL_FINGERPRINTS,
        _raw_values=raw,
    )
