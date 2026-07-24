# Demeterio: Mod Update Checker (script for The Sims 4)
# Do not copy, share or modify without my permission
# https://demeterio.tumblr.com
# https://discord.gg/mPyRPScgeS

"""Fetch and strictly validate the single central update registry."""

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse

from .constants import (
    ALLOWED_NETWORK_HOSTS,
    CENTRAL_REGISTRY_HOST,
    CENTRAL_REGISTRY_PATH,
    CENTRAL_REGISTRY_PORT,
    CENTRAL_REGISTRY_SCHEMA,
    CENTRAL_REGISTRY_USER_AGENT,
    DEFAULT_REQUEST_TIMEOUT_SECONDS,
    MAX_CENTRAL_REGISTRY_BYTES,
    MAX_CENTRAL_REGISTRY_ENTRIES,
    MAX_SIGNED_CENTRAL_REGISTRY_BYTES,
)
from .errors import (
    CentralRegistryValidationError,
    NetworkRequestError,
    NetworkSecurityError,
    RegistryRateLimitError,
)
from .models import CentralRegistryDocument, CentralRegistryEntry
from .registry_signature import extract_verified_registry_payload
from .secure_http import http_get
from .validation import (
    require_non_empty_string,
    validate_mod_id,
    validate_release_channel,
    validate_release_tag,
)
from .versioning import parse_version


def _validate_allowed_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme.lower() != "http":
        raise NetworkSecurityError("Only HTTP registry requests are allowed")
    host = (parsed.hostname or "").lower()
    if host not in ALLOWED_NETWORK_HOSTS:
        raise NetworkSecurityError(
            "Central registry host is not allowed: {}".format(
                host or "<missing>"
            )
        )
    try:
        port = parsed.port or 80
    except ValueError as exc:
        raise NetworkSecurityError(
            "Central registry URL port is invalid"
        ) from exc
    if port != CENTRAL_REGISTRY_PORT:
        raise NetworkSecurityError("Only the configured HTTP port is allowed")
    if parsed.username is not None or parsed.password is not None:
        raise NetworkSecurityError(
            "Credentials in registry URLs are forbidden"
        )
    if parsed.params or parsed.query:
        raise NetworkSecurityError(
            "Parameters and queries in registry URLs are forbidden"
        )
    if parsed.fragment:
        raise NetworkSecurityError("Fragments in registry URLs are forbidden")
    if parsed.path != CENTRAL_REGISTRY_PATH:
        raise NetworkSecurityError("Central registry path is not allowed")


def central_registry_url() -> str:
    """Build the immutable HTTP registry URL from project-owned constants."""

    host = require_non_empty_string(
        CENTRAL_REGISTRY_HOST,
        "registry host",
        253,
    ).lower()
    if host not in ALLOWED_NETWORK_HOSTS:
        raise NetworkSecurityError(
            "Central registry host is not allowed: {}".format(host)
        )
    try:
        host.encode("ascii")
    except UnicodeEncodeError as exc:
        raise NetworkSecurityError("Central registry host is invalid") from exc

    if CENTRAL_REGISTRY_PORT != 80:
        raise NetworkSecurityError("Only the standard HTTP port is allowed")

    path = require_non_empty_string(
        CENTRAL_REGISTRY_PATH,
        "registry path",
        512,
    )
    if not path.startswith("/") or "\\" in path:
        raise NetworkSecurityError("Central registry path is invalid")
    parts = [part for part in path.split("/") if part]
    if not parts or any(part in (".", "..") for part in parts):
        raise NetworkSecurityError("Central registry path is invalid")
    if any(
        ord(character) < 32 or ord(character) == 127
        for character in path
    ):
        raise NetworkSecurityError("Central registry path is invalid")
    try:
        path.encode("ascii")
    except UnicodeEncodeError as exc:
        raise NetworkSecurityError("Central registry path is invalid") from exc

    url = "http://{}{}".format(host, path)
    _validate_allowed_url(url)
    return url


def _parse_timestamp(value: object, field_name: str) -> str:
    text = require_non_empty_string(value, field_name, 64)
    try:
        parsed = datetime.fromisoformat(
            text[:-1] + "+00:00" if text.endswith("Z") else text
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "{} must be an ISO timestamp".format(field_name)
        ) from exc
    if parsed.tzinfo is None:
        raise ValueError("{} must include a timezone".format(field_name))
    return parsed.astimezone(timezone.utc).isoformat()


def _reject_duplicate_keys(
    pairs: List[Tuple[str, Any]],
) -> Dict[str, Any]:
    result = {}  # type: Dict[str, Any]
    for key, value in pairs:
        if key in result:
            raise CentralRegistryValidationError(
                "Central registry JSON contains duplicate key: {}".format(key)
            )
        result[key] = value
    return result


def parse_central_registry(payload: bytes) -> CentralRegistryDocument:
    """Parse the restricted generated registry JSON document."""

    if len(payload) > MAX_CENTRAL_REGISTRY_BYTES:
        raise CentralRegistryValidationError(
            "Central registry payload exceeds the allowed size"
        )

    try:
        data = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except CentralRegistryValidationError:
        raise
    except (UnicodeDecodeError, TypeError, ValueError) as exc:
        raise CentralRegistryValidationError(
            "Central registry is not valid UTF-8 JSON"
        ) from exc

    try:
        if not isinstance(data, dict):
            raise TypeError("Central registry root must be an object")
        expected_root = frozenset(("schema", "generated_at", "entries"))
        if frozenset(data.keys()) != expected_root:
            raise ValueError("Central registry root fields are invalid")
        if (
            isinstance(data["schema"], bool)
            or data["schema"] != CENTRAL_REGISTRY_SCHEMA
        ):
            raise ValueError(
                "Central registry schema must be integer {}".format(
                    CENTRAL_REGISTRY_SCHEMA
                )
            )
        generated_at = _parse_timestamp(data["generated_at"], "generated_at")
        raw_entries = data["entries"]
        if not isinstance(raw_entries, list):
            raise TypeError("Central registry entries must be an array")
        if len(raw_entries) > MAX_CENTRAL_REGISTRY_ENTRIES:
            raise ValueError("Central registry contains too many entries")

        entries = {}  # type: Dict[Tuple[str, str], CentralRegistryEntry]
        expected_entry = frozenset(
            (
                "mod_id",
                "release_channel",
                "version",
                "release_tag",
                "checked_at",
            )
        )
        for index, raw_entry in enumerate(raw_entries):
            if not isinstance(raw_entry, dict):
                raise TypeError(
                    "Central registry entry {} must be an object".format(index)
                )
            if frozenset(raw_entry.keys()) != expected_entry:
                raise ValueError(
                    "Central registry entry {} fields are invalid".format(index)
                )
            mod_id = validate_mod_id(raw_entry["mod_id"])
            channel = validate_release_channel(
                raw_entry["release_channel"]
            )
            version = require_non_empty_string(
                raw_entry["version"],
                "version",
                128,
            )
            parse_version(version)
            release_tag = validate_release_tag(raw_entry["release_tag"])
            checked_at = _parse_timestamp(
                raw_entry["checked_at"],
                "checked_at",
            )
            key = (mod_id, channel)
            if key in entries:
                raise ValueError(
                    "Central registry contains duplicate mod/channel entry: "
                    "{} {}".format(mod_id, channel)
                )
            entries[key] = CentralRegistryEntry(
                mod_id,
                channel,
                version,
                release_tag,
                checked_at,
            )

        return CentralRegistryDocument(
            CENTRAL_REGISTRY_SCHEMA,
            generated_at,
            entries,
        )
    except CentralRegistryValidationError:
        raise
    except (TypeError, ValueError) as exc:
        raise CentralRegistryValidationError(str(exc)) from exc


def parse_signed_central_registry(
    signed_document: bytes,
) -> CentralRegistryDocument:
    """Authenticate one signed envelope, then parse its inner registry."""

    if len(signed_document) > MAX_SIGNED_CENTRAL_REGISTRY_BYTES:
        raise CentralRegistryValidationError(
            "Signed central registry exceeds the allowed size"
        )
    payload = extract_verified_registry_payload(signed_document)
    return parse_central_registry(payload)


class CentralRegistryClient:
    """Download exactly one bounded signed JSON registry document."""

    __slots__ = ("_timeout",)

    def __init__(
        self,
        timeout: float = DEFAULT_REQUEST_TIMEOUT_SECONDS,
    ) -> None:
        self._timeout = timeout

    @staticmethod
    def _retry_at(headers) -> str:
        value = headers.get("retry-after") if headers is not None else None
        try:
            seconds = max(60, int(str(value).strip()))
        except (TypeError, ValueError):
            seconds = 60 * 60
        return (
            datetime.now(timezone.utc) + timedelta(seconds=seconds)
        ).isoformat()

    def fetch(self) -> CentralRegistryDocument:
        url = central_registry_url()
        _validate_allowed_url(url)
        response = http_get(
            url,
            CENTRAL_REGISTRY_USER_AGENT,
            self._timeout,
            MAX_SIGNED_CENTRAL_REGISTRY_BYTES,
        )
        if response.status in (403, 429):
            raise RegistryRateLimitError(
                "Central registry host requires requests to pause",
                retry_at=self._retry_at(response.headers),
            )
        if response.status != 200:
            raise NetworkRequestError(
                "Central registry returned HTTP {}".format(response.status)
            )
        content_type = (
            response.headers.get("content-type", "")
            .split(";", 1)[0]
            .strip()
            .lower()
        )
        if content_type != "application/json":
            raise NetworkRequestError(
                "Central registry response is not application/json"
            )
        if len(response.body) > MAX_SIGNED_CENTRAL_REGISTRY_BYTES:
            raise NetworkRequestError(
                "Central registry exceeds the allowed size"
            )
        return parse_signed_central_registry(response.body)
