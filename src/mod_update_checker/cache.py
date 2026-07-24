# Demeterio: Mod Update Checker (script for The Sims 4)
# Do not copy, share or modify without my permission
# https://demeterio.tumblr.com
# https://discord.gg/mPyRPScgeS

"""Central-registry and notification state stored in Cache.dmuc."""

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, Optional

from .binary_store import read_dmuc_file, write_dmuc_file
from .constants import (
    MUC_CACHE_SCHEMA,
    MUC_STORAGE_KIND_CACHE,
    REGISTRY_CHECK_INTERVAL_SECONDS,
    REGISTRY_GENERIC_RETRY_SECONDS,
    REGISTRY_PRESENCE_MISSING,
    REGISTRY_PRESENCE_PRESENT,
    REGISTRY_PRESENCE_VALUES,
)
from .errors import PersistenceError
from .logger import MUCLog
from .paths import MUCPaths
from .validation import (
    require_non_empty_string,
    validate_mod_id,
    validate_release_channel,
    validate_release_tag,
)
from .versioning import parse_version


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_text(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def parse_utc_text(value: str, field_name: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise PersistenceError(
            "{} must be a non-empty timestamp".format(field_name)
        )
    if value != value.strip():
        raise PersistenceError(
            "{} must not contain leading or trailing whitespace".format(
                field_name
            )
        )
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise PersistenceError(
            "{} must not contain control characters".format(field_name)
        )
    try:
        result = datetime.fromisoformat(
            value[:-1] + "+00:00" if value.endswith("Z") else value
        )
    except (TypeError, ValueError) as exc:
        raise PersistenceError(
            "{} is not a valid ISO timestamp".format(field_name)
        ) from exc
    if result.tzinfo is None:
        raise PersistenceError("{} must include a timezone".format(field_name))
    return result.astimezone(timezone.utc)


class MUCCache:
    """Cache the last central document result and summary notification state."""

    __slots__ = (
        "_mods",
        "_last_registry_check_at",
        "_last_registry_generated_at",
        "_retry_after",
        "_last_error",
        "_last_notification_signature",
    )

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._mods = {}  # type: Dict[str, Dict[str, str]]
        self._last_registry_check_at = ""
        self._last_registry_generated_at = ""
        self._retry_after = ""
        self._last_error = ""
        self._last_notification_signature = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema": MUC_CACHE_SCHEMA,
            "last_registry_check_at": self._last_registry_check_at,
            "last_registry_generated_at": self._last_registry_generated_at,
            "retry_after": self._retry_after,
            "last_error": self._last_error,
            "last_notification_signature": self._last_notification_signature,
            "mods": {
                mod_id: dict(sorted(entry.items()))
                for mod_id, entry in sorted(self._mods.items())
            },
        }

    @staticmethod
    def _optional_text(value: object, field_name: str, maximum: int) -> str:
        if not isinstance(value, str):
            raise PersistenceError("{} must be a string".format(field_name))
        if value != value.strip():
            raise PersistenceError(
                "{} must not contain leading or trailing whitespace".format(
                    field_name
                )
            )
        if len(value) > maximum:
            raise PersistenceError("{} is too long".format(field_name))
        if any(ord(character) < 32 or ord(character) == 127 for character in value):
            raise PersistenceError(
                "{} must not contain control characters".format(field_name)
            )
        return value

    def _validated_entry(
        self,
        raw_mod_id: object,
        raw_entry: object,
        source_schema: int,
    ) -> Dict[str, str]:
        try:
            validate_mod_id(raw_mod_id)
            if not isinstance(raw_entry, dict):
                raise TypeError("Every cached mod entry must be an object")

            legacy_fields = frozenset(
                (
                    "release_channel",
                    "available_version",
                    "release_tag",
                    "checked_at",
                )
            )
            current_fields = frozenset(
                tuple(legacy_fields)
                + (
                    "registry_presence",
                    "missing_since",
                )
            )
            expected = legacy_fields if source_schema == 1 else current_fields
            if frozenset(raw_entry.keys()) != expected:
                raise ValueError("Cached mod entry fields are invalid")

            channel = validate_release_channel(raw_entry["release_channel"])
            version = self._optional_text(
                raw_entry["available_version"],
                "available_version",
                128,
            )
            release_tag = self._optional_text(
                raw_entry["release_tag"],
                "release_tag",
                128,
            )
            checked_at = self._optional_text(
                raw_entry["checked_at"],
                "checked_at",
                64,
            )

            if source_schema == 1:
                presence = REGISTRY_PRESENCE_PRESENT
                missing_since = ""
            else:
                presence = self._optional_text(
                    raw_entry["registry_presence"],
                    "registry_presence",
                    16,
                )
                missing_since = self._optional_text(
                    raw_entry["missing_since"],
                    "missing_since",
                    64,
                )
                if presence not in REGISTRY_PRESENCE_VALUES:
                    raise ValueError("registry_presence is invalid")

            history_values = (version, release_tag, checked_at)
            has_history = any(history_values)
            if has_history and not all(history_values):
                raise ValueError(
                    "Cached last-known registry fields must be all present or all empty"
                )
            if presence == REGISTRY_PRESENCE_PRESENT and not has_history:
                raise ValueError(
                    "A present registry entry requires version, tag, and checked_at"
                )
            if presence == REGISTRY_PRESENCE_PRESENT and missing_since:
                raise ValueError(
                    "A present registry entry must not define missing_since"
                )
            if presence == REGISTRY_PRESENCE_MISSING and not missing_since:
                raise ValueError(
                    "A missing registry entry requires missing_since"
                )

            if has_history:
                require_non_empty_string(version, "available_version", 128)
                parse_version(version)
                validate_release_tag(release_tag)
                checked_at = utc_text(
                    parse_utc_text(checked_at, "checked_at")
                )
            if missing_since:
                missing_since = utc_text(
                    parse_utc_text(missing_since, "missing_since")
                )

            return {
                "release_channel": channel,
                "available_version": version,
                "release_tag": release_tag,
                "checked_at": checked_at,
                "registry_presence": presence,
                "missing_since": missing_since,
            }
        except PersistenceError:
            raise
        except (TypeError, ValueError) as exc:
            raise PersistenceError(str(exc)) from exc

    def _apply_dict(self, data: Dict[str, Any]) -> int:
        if not isinstance(data, dict):
            raise PersistenceError("Cache.dmuc root must be an object")
        expected = frozenset(
            (
                "schema",
                "last_registry_check_at",
                "last_registry_generated_at",
                "retry_after",
                "last_error",
                "last_notification_signature",
                "mods",
            )
        )
        if frozenset(data.keys()) != expected:
            raise PersistenceError("Cache.dmuc fields are invalid")

        source_schema = data["schema"]
        if (
            isinstance(source_schema, bool)
            or source_schema not in (1, MUC_CACHE_SCHEMA)
        ):
            raise PersistenceError("Cache.dmuc schema is unsupported")
        if not isinstance(data["mods"], dict):
            raise PersistenceError("Cache.dmuc mods must be an object")

        self.reset()
        for raw_mod_id, raw_entry in data["mods"].items():
            mod_id = validate_mod_id(raw_mod_id)
            self._mods[mod_id] = self._validated_entry(
                raw_mod_id,
                raw_entry,
                source_schema,
            )

        self._last_registry_check_at = self._optional_text(
            data["last_registry_check_at"],
            "last_registry_check_at",
            64,
        )
        self._last_registry_generated_at = self._optional_text(
            data["last_registry_generated_at"],
            "last_registry_generated_at",
            64,
        )
        self._retry_after = self._optional_text(
            data["retry_after"],
            "retry_after",
            64,
        )
        self._last_error = self._optional_text(
            data["last_error"],
            "last_error",
            512,
        )
        self._last_notification_signature = self._optional_text(
            data["last_notification_signature"],
            "last_notification_signature",
            128,
        )
        for value, field_name in (
            (self._last_registry_check_at, "last_registry_check_at"),
            (self._last_registry_generated_at, "last_registry_generated_at"),
            (self._retry_after, "retry_after"),
        ):
            if value:
                parse_utc_text(value, field_name)
        return source_schema

    def load(self) -> None:
        logger = MUCLog.logger()
        cache_path = MUCPaths.cache_path()
        if not os.path.exists(cache_path):
            self.reset()
            self.save()
            logger.info("Created empty Cache.dmuc")
            return
        try:
            source_schema = self._apply_dict(
                read_dmuc_file(cache_path, MUC_STORAGE_KIND_CACHE)
            )
            if source_schema != MUC_CACHE_SCHEMA:
                self.save()
                logger.info(
                    "Migrated Cache.dmuc from schema {} to schema {}".format(
                        source_schema,
                        MUC_CACHE_SCHEMA,
                    )
                )
            logger.info(
                "Loaded Cache.dmuc with {} entry(ies)".format(len(self._mods))
            )
        except (PersistenceError, TypeError, ValueError):
            logger.exception(
                "Cache.dmuc is invalid; an empty cache will replace it"
            )
            self.reset()
            self.save()

    def save(self) -> None:
        write_dmuc_file(
            MUCPaths.cache_path(),
            self.to_dict(),
            MUC_STORAGE_KIND_CACHE,
        )

    def get(self, mod_id: str) -> Optional[Dict[str, str]]:
        entry = self._mods.get(mod_id)
        return dict(entry) if entry is not None else None

    def set_entry(
        self,
        mod_id: str,
        release_channel: str,
        available_version: str,
        release_tag: str,
        checked_at: str,
    ) -> None:
        validate_mod_id(mod_id)
        channel = validate_release_channel(release_channel)
        version = require_non_empty_string(
            available_version,
            "available_version",
            128,
        )
        parse_version(version)
        tag = validate_release_tag(release_tag)
        normalized_checked_at = utc_text(
            parse_utc_text(checked_at, "checked_at")
        )
        self._mods[mod_id] = {
            "release_channel": channel,
            "available_version": version,
            "release_tag": tag,
            "checked_at": normalized_checked_at,
            "registry_presence": REGISTRY_PRESENCE_PRESENT,
            "missing_since": "",
        }

    def mark_registry_missing(
        self,
        mod_id: str,
        release_channel: str,
        missing_at: datetime,
    ) -> None:
        validate_mod_id(mod_id)
        channel = validate_release_channel(release_channel)
        existing = self._mods.get(mod_id)
        missing_since = utc_text(missing_at)

        if existing is None or existing.get("release_channel") != channel:
            self._mods[mod_id] = {
                "release_channel": channel,
                "available_version": "",
                "release_tag": "",
                "checked_at": "",
                "registry_presence": REGISTRY_PRESENCE_MISSING,
                "missing_since": missing_since,
            }
            return

        if existing.get("registry_presence") == REGISTRY_PRESENCE_MISSING:
            missing_since = existing.get("missing_since") or missing_since
        existing["registry_presence"] = REGISTRY_PRESENCE_MISSING
        existing["missing_since"] = missing_since

    def mark_success(
        self,
        checked_at: datetime,
        generated_at: str,
    ) -> None:
        self._last_registry_check_at = utc_text(checked_at)
        self._last_registry_generated_at = utc_text(
            parse_utc_text(generated_at, "generated_at")
        )
        self._retry_after = ""
        self._last_error = ""

    def mark_failure(
        self,
        message: str,
        now: datetime,
        retry_at: Optional[datetime] = None,
    ) -> None:
        self._last_registry_check_at = utc_text(now)
        self._last_error = str(message)[:512]
        retry = retry_at or (
            now + timedelta(seconds=REGISTRY_GENERIC_RETRY_SECONDS)
        )
        self._retry_after = utc_text(retry)

    def last_error(self) -> str:
        return self._last_error

    def registry_generated_at(self) -> str:
        return self._last_registry_generated_at

    def retry_at(self, now: datetime) -> Optional[datetime]:
        if not self._retry_after:
            return None
        retry = parse_utc_text(self._retry_after, "retry_after")
        if retry <= now:
            self._retry_after = ""
            return None
        return retry

    def is_due(self, now: datetime, force: bool = False) -> bool:
        if self.retry_at(now) is not None:
            return False
        if force:
            return True
        if not self._last_registry_check_at:
            return True
        checked_at = parse_utc_text(
            self._last_registry_check_at,
            "last_registry_check_at",
        )
        return (
            checked_at + timedelta(seconds=REGISTRY_CHECK_INTERVAL_SECONDS)
            <= now
        )

    def notification_signature(self) -> str:
        return self._last_notification_signature

    def mark_notification_signature(self, signature: str) -> None:
        if not isinstance(signature, str) or len(signature) > 128:
            raise PersistenceError("Notification signature is invalid")
        self._last_notification_signature = signature

    def clear_notification_signature(self) -> None:
        self._last_notification_signature = ""

    def remove_stale(self, active_mod_ids: Iterable[str]) -> None:
        active = frozenset(active_mod_ids)
        stale = tuple(mod_id for mod_id in self._mods if mod_id not in active)
        for mod_id in stale:
            del self._mods[mod_id]
