"""Carga fail-closed de la raíz pública de autoridad comercial.

La política productiva no acepta un keyring pasado por el caller. El material
público confiable llega por configuración de despliegue y sólo contiene SPKI
públicos Ed25519; la clave privada nunca pertenece a este runtime.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping

from .commercial_authority import (
    CommercialAuthorityError,
    Ed25519CommercialAuthorityVerifier,
)

COMMERCIAL_AUTHORITY_KEYRING_ENV = "PRECIOS_SPS_COMMERCIAL_AUTHORITY_KEYRING_JSON"
COMMERCIAL_AUTHORITY_TRUST_SCHEMA_VERSION = "1"
COMMERCIAL_AUTHORITY_TRUST_PURPOSE = "precios-sps-commercial-authority"
_MAX_KEYRING_JSON_BYTES = 16 * 1024


class CommercialAuthorityTrustError(ValueError):
    """La configuración de confianza productiva falta o no es canónica."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def load_productive_commercial_authority_verifier() -> Ed25519CommercialAuthorityVerifier:
    """Carga exclusivamente la trust config del entorno productivo.

    No recibe mappings, paths ni overrides del caller. Tests pueden aislar el
    entorno del proceso, pero el API operacional no puede sustituir la raíz de
    confianza mediante un argumento de función.
    """

    raw = os.environ.get(COMMERCIAL_AUTHORITY_KEYRING_ENV)
    if raw is None or not raw.strip():
        raise CommercialAuthorityTrustError("commercial_authority_keyring_missing")
    if raw != raw.strip() or len(raw.encode("utf-8")) > _MAX_KEYRING_JSON_BYTES:
        raise CommercialAuthorityTrustError("commercial_authority_keyring_invalid")
    try:
        document = json.loads(raw)
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise CommercialAuthorityTrustError("commercial_authority_keyring_invalid") from exc
    if not isinstance(document, dict) or set(document) != {
        "schema_version",
        "purpose",
        "keys",
    }:
        raise CommercialAuthorityTrustError("commercial_authority_keyring_schema_invalid")
    if document["schema_version"] != COMMERCIAL_AUTHORITY_TRUST_SCHEMA_VERSION:
        raise CommercialAuthorityTrustError("commercial_authority_keyring_version_invalid")
    if document["purpose"] != COMMERCIAL_AUTHORITY_TRUST_PURPOSE:
        raise CommercialAuthorityTrustError("commercial_authority_keyring_purpose_invalid")
    keys = document["keys"]
    if not isinstance(keys, Mapping) or not keys:
        raise CommercialAuthorityTrustError("commercial_authority_keyring_keys_invalid")
    if len(keys) > 8:
        raise CommercialAuthorityTrustError("commercial_authority_keyring_too_many_keys")
    if any(not isinstance(key, str) or not isinstance(value, str) for key, value in keys.items()):
        raise CommercialAuthorityTrustError("commercial_authority_keyring_keys_invalid")
    try:
        return Ed25519CommercialAuthorityVerifier(keys)
    except CommercialAuthorityError as exc:
        raise CommercialAuthorityTrustError(
            f"commercial_authority_keyring_{exc.code}"
        ) from exc
