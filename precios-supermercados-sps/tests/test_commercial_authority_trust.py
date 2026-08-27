from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from precios_supermercados.commercial_authority_trust import (
    COMMERCIAL_AUTHORITY_KEYRING_ENV,
    COMMERCIAL_AUTHORITY_TRUST_PURPOSE,
    CommercialAuthorityTrustError,
    load_productive_commercial_authority_verifier,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MONOREPO_ROOT = PROJECT_ROOT.parent
TRUST_LOADER = "load_productive_commercial_authority_verifier"


def _spki_b64url() -> str:
    private = Ed25519PrivateKey.generate()
    der = private.public_key().public_bytes(
        Encoding.DER,
        PublicFormat.SubjectPublicKeyInfo,
    )
    return base64.urlsafe_b64encode(der).decode("ascii").rstrip("=")


def _document(*, purpose: str = COMMERCIAL_AUTHORITY_TRUST_PURPOSE, keys=None) -> str:
    return json.dumps(
        {
            "schema_version": "1",
            "purpose": purpose,
            "keys": keys or {"authority-v1": _spki_b64url()},
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _load(raw: str):
    with patch.dict(os.environ, {COMMERCIAL_AUTHORITY_KEYRING_ENV: raw}, clear=True):
        return load_productive_commercial_authority_verifier()


def test_valid_productive_trust_config_loads_exact_keyring() -> None:
    verifier = _load(_document())
    assert verifier.key_ids == ("authority-v1",)


def test_trust_config_fails_closed_when_missing_or_wrong_purpose() -> None:
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(
            CommercialAuthorityTrustError,
            match="commercial_authority_keyring_missing",
        ):
            load_productive_commercial_authority_verifier()

    with pytest.raises(
        CommercialAuthorityTrustError,
        match="commercial_authority_keyring_purpose_invalid",
    ):
        _load(_document(purpose="collector-receipt"))


def test_trust_config_rejects_duplicate_top_level_json_key() -> None:
    spki = _spki_b64url()
    raw = (
        '{"schema_version":"1","purpose":"precios-sps-commercial-authority",'
        '"purpose":"precios-sps-commercial-authority","keys":{"authority-v1":"'
        + spki
        + '"}}'
    )
    with pytest.raises(
        CommercialAuthorityTrustError,
        match="commercial_authority_keyring_duplicate_key",
    ):
        _load(raw)


def test_trust_config_rejects_duplicate_signing_key_id() -> None:
    first = _spki_b64url()
    second = _spki_b64url()
    raw = (
        '{"schema_version":"1","purpose":"precios-sps-commercial-authority",'
        '"keys":{"authority-v1":"'
        + first
        + '","authority-v1":"'
        + second
        + '"}}'
    )
    with pytest.raises(
        CommercialAuthorityTrustError,
        match="commercial_authority_keyring_duplicate_key",
    ):
        _load(raw)


def test_trust_config_rejects_more_than_eight_keys() -> None:
    keys = {f"authority-{index}": _spki_b64url() for index in range(9)}
    with pytest.raises(
        CommercialAuthorityTrustError,
        match="commercial_authority_keyring_too_many_keys",
    ):
        _load(_document(keys=keys))


def test_productive_trust_loader_is_only_consumed_by_source_authority_policy() -> None:
    allowed = {
        PROJECT_ROOT / "src/precios_supermercados/commercial_authority_trust.py",
        PROJECT_ROOT
        / "src/precios_supermercados/scrapers/la_colonia_commercial_authority.py",
    }
    candidates = [
        *sorted((PROJECT_ROOT / "src").rglob("*.py")),
        *sorted((PROJECT_ROOT / "scripts").rglob("*.py")),
        *sorted((MONOREPO_ROOT / ".github/workflows").glob("*.yml")),
        *sorted((MONOREPO_ROOT / ".github/workflows").glob("*.yaml")),
    ]
    violations = []
    for path in candidates:
        if path in allowed:
            continue
        if TRUST_LOADER in path.read_text(encoding="utf-8"):
            violations.append(str(path.relative_to(MONOREPO_ROOT)))
    assert violations == []
