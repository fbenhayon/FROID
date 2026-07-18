"""Authenticated encryption for OAuth tokens persisted by FROID."""

from __future__ import annotations

import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken, MultiFernet


TOKEN_FIELDS = ("access_token", "refresh_token")
ENCRYPTED_FIELD = "oauth_tokens_encrypted"


class TokenEncryptionError(RuntimeError):
    pass


class TokenCipher:
    def __init__(self, keys: list[str]):
        normalized = [str(key or "").strip() for key in keys if str(key or "").strip()]
        if not normalized:
            raise TokenEncryptionError("at least one OAuth encryption key is required")
        try:
            fernets = [Fernet(key.encode("ascii")) for key in normalized]
            self._primary = fernets[0]
            self._fernet = MultiFernet(fernets)
        except (ValueError, TypeError) as exc:
            raise TokenEncryptionError("invalid FROID_TOKEN_ENCRYPTION_KEYS") from exc

    @classmethod
    def from_csv(cls, value: str) -> "TokenCipher | None":
        keys = [part.strip() for part in str(value or "").split(",") if part.strip()]
        return cls(keys) if keys else None

    def protect(self, connection: dict[str, Any]) -> dict[str, Any]:
        protected = dict(connection or {})
        secrets = {
            field: str(protected.pop(field, "") or "") for field in TOKEN_FIELDS
        }
        if any(secrets.values()):
            raw = json.dumps(secrets, separators=(",", ":")).encode("utf-8")
            protected[ENCRYPTED_FIELD] = self._fernet.encrypt(raw).decode("ascii")
        return protected

    def reveal(self, connection: dict[str, Any]) -> dict[str, Any]:
        revealed = dict(connection or {})
        encrypted = str(revealed.pop(ENCRYPTED_FIELD, "") or "")
        if not encrypted:
            return revealed
        try:
            raw = self._fernet.decrypt(encrypted.encode("ascii"))
            secrets = json.loads(raw.decode("utf-8"))
        except (InvalidToken, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TokenEncryptionError("unable to decrypt OAuth tokens") from exc
        for field in TOKEN_FIELDS:
            revealed[field] = str(secrets.get(field) or "")
        return revealed

    def needs_rotation(self, connection: dict[str, Any]) -> bool:
        encrypted = str((connection or {}).get(ENCRYPTED_FIELD) or "")
        if not encrypted:
            return False
        try:
            self._primary.decrypt(encrypted.encode("ascii"))
            return False
        except InvalidToken:
            return True


class TextCipher:
    """Encrypt one clinical text field while leaving index metadata readable."""

    def __init__(self, keys: list[str]):
        normalized = [str(key or "").strip() for key in keys if str(key or "").strip()]
        if not normalized:
            raise TokenEncryptionError("at least one clinical encryption key is required")
        try:
            self._fernet = MultiFernet([Fernet(key.encode("ascii")) for key in normalized])
        except (ValueError, TypeError) as exc:
            raise TokenEncryptionError("invalid clinical encryption keys") from exc

    @classmethod
    def from_csv(cls, value: str) -> "TextCipher | None":
        keys = [part.strip() for part in str(value or "").split(",") if part.strip()]
        return cls(keys) if keys else None

    def protect(self, payload: dict[str, Any], field: str, encrypted_field: str) -> dict[str, Any]:
        protected = dict(payload or {})
        text = str(protected.pop(field, "") or "")
        if text:
            protected[encrypted_field] = self._fernet.encrypt(text.encode("utf-8")).decode("ascii")
        return protected

    def reveal(self, payload: dict[str, Any], field: str, encrypted_field: str) -> dict[str, Any]:
        revealed = dict(payload or {})
        encrypted = str(revealed.pop(encrypted_field, "") or "")
        if encrypted:
            try:
                revealed[field] = self._fernet.decrypt(encrypted.encode("ascii")).decode("utf-8")
            except (InvalidToken, UnicodeDecodeError) as exc:
                raise TokenEncryptionError("unable to decrypt clinical text") from exc
        return revealed
