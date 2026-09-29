"""Backend identity evidence for the controlled Psique Phase 2A workflow.

Loaders must read authenticated server records, never request JSON. Neither
email verification nor material ownership is asserted by a browser field.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime

CREDIT_MODELS = frozenset({"v1", "psique_v2"})
FUNDING_TYPES = frozenset({"TRIAL", "PAID"})
SOURCE_KINDS = frozenset({"file", "stream"})
ELIGIBILITY_ORIGINS = frozenset({"V1", "V2"})


class EvidenceError(ValueError):
    pass


def normalize_trial_email(email: str) -> str:
    normalized = email.strip().lower()
    if not normalized or "@" not in normalized:
        raise EvidenceError("TRIAL_EMAIL_REQUIRED")
    return normalized


@dataclass(frozen=True)
class TrialIdentity:
    email: str
    verified_at: datetime | None
    verification_ref: str
    legacy_benefit_ref: str | None = None
    legacy_history_checked: bool = False


@dataclass(frozen=True)
class AuthorizedMaterial:
    """Returned by the server's authorization/ingestion loader, not a client DTO.

    material_key is a stable server-generated UUID retained by that loader.
    A file loader supplies an iterator of ORIGINAL bytes, without retaining a
    second audio copy. A stream keeps its registered identity without inventing
    a hash; advanced chunk manifests are deliberately deferred.
    """

    material_key: str
    organization_id: str
    owner_user_id: str
    session_id: str
    source_kind: str
    original_chunks: Iterable[bytes] | None = None


def source_sha256(chunks: Iterable[bytes]) -> str:
    digest = hashlib.sha256()
    seen = False
    for chunk in chunks:
        if not isinstance(chunk, bytes):
            raise EvidenceError("ORIGINAL_BYTES_REQUIRED")
        if chunk:
            seen = True
            digest.update(chunk)
    if not seen:
        raise EvidenceError("EMPTY_SOURCE")
    return digest.hexdigest()


class TrialKeyring:
    def __init__(self, keys: Mapping[str, bytes], active_version: str):
        self._keys = dict(keys)
        self.active_version = active_version

    @classmethod
    def from_env(cls) -> TrialKeyring:
        try:
            raw = json.loads(os.environ.get("FROID_PSIQUE_TRIAL_HMAC_KEYS", "{}") or "{}")
            if not isinstance(raw, dict):
                raise TypeError
            keys = {str(version): base64.b64decode(value, validate=True)
                    for version, value in raw.items()}
        except (ValueError, TypeError) as exc:
            raise EvidenceError("TRIAL_HMAC_CONFIG_INVALID") from exc
        return cls(keys, os.environ.get("FROID_PSIQUE_TRIAL_HMAC_ACTIVE_VERSION", ""))

    def tokens(self, email: str, historical_versions: Iterable[str]) -> list[dict[str, str]]:
        if not self.active_version or self.active_version not in self._keys:
            raise EvidenceError("TRIAL_HMAC_KEY_REQUIRED")
        if any(not version or len(secret) < 32 for version, secret in self._keys.items()):
            raise EvidenceError("TRIAL_HMAC_CONFIG_INVALID")
        if set(historical_versions) - self._keys.keys():
            raise EvidenceError("TRIAL_HISTORICAL_KEY_REQUIRED")
        message = normalize_trial_email(email).encode("utf-8")
        return [{"version": version, "hmac": hmac.new(secret, message, hashlib.sha256).hexdigest()}
                for version, secret in sorted(self._keys.items())]
