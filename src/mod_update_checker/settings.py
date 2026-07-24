# Demeterio: Mod Update Checker (script for The Sims 4)
# Do not copy, share or modify without my permission
# https://demeterio.tumblr.com
# https://discord.gg/mPyRPScgeS

"""Strict user preferences stored in the binary Settings.dmuc file."""

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from .binary_store import read_dmuc_file, write_dmuc_file
from .constants import (
    CONSENT_SNOOZE_SECONDS,
    MUC_SETTINGS_SCHEMA,
    MUC_STORAGE_KIND_SETTINGS,
)
from .errors import PersistenceError
from .logger import MUCLog
from .paths import MUCPaths
from .validation import validate_mod_id


class MUCSettings:
    """Mutable settings with explicit consent and atomic persistence."""

    __slots__ = (
        "network_checks_enabled",
        "network_prompt_after",
        "notifications_enabled",
        "notifications_muted_until",
        "mod_alert_overrides",
    )

    def __init__(self) -> None:
        self.network_checks_enabled = None  # type: Optional[bool]
        self.network_prompt_after = None  # type: Optional[str]
        self.notifications_enabled = None  # type: Optional[bool]
        self.notifications_muted_until = None  # type: Optional[str]
        self.mod_alert_overrides = {}  # type: Dict[str, bool]

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _utc_text(value: datetime) -> str:
        return value.astimezone(timezone.utc).isoformat()

    @staticmethod
    def _parse_utc_text(value: object, field_name: str) -> datetime:
        if not isinstance(value, str):
            raise PersistenceError("{} must be an ISO timestamp".format(field_name))
        text = value.strip()
        if not text:
            raise PersistenceError("{} must not be empty".format(field_name))
        try:
            parsed = datetime.fromisoformat(
                text[:-1] + "+00:00" if text.endswith("Z") else text
            )
        except ValueError as exc:
            raise PersistenceError(
                "{} must be a valid ISO timestamp".format(field_name)
            ) from exc
        if parsed.tzinfo is None:
            raise PersistenceError("{} must include a timezone".format(field_name))
        return parsed.astimezone(timezone.utc)

    @classmethod
    def _validate_optional_timestamp(
        cls,
        value: object,
        field_name: str,
    ) -> Optional[str]:
        if value is None:
            return None
        parsed = cls._parse_utc_text(value, field_name)
        return cls._utc_text(parsed)

    @staticmethod
    def _validate_optional_bool(value: object, field_name: str) -> Optional[bool]:
        if value is None:
            return None
        if type(value) is not bool:
            raise PersistenceError("{} must be True, False, or null".format(field_name))
        return value

    @staticmethod
    def _expected_fields() -> frozenset:
        return frozenset(
            (
                "schema",
                "network_checks_enabled",
                "network_prompt_after",
                "notifications_enabled",
                "notifications_muted_until",
                "mod_alert_overrides",
            )
        )

    def reset_defaults(self) -> None:
        # No network access or notification is allowed until the player answers.
        self.network_checks_enabled = None
        self.network_prompt_after = None
        self.notifications_enabled = None
        self.notifications_muted_until = None
        self.mod_alert_overrides = {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema": MUC_SETTINGS_SCHEMA,
            "network_checks_enabled": self.network_checks_enabled,
            "network_prompt_after": self.network_prompt_after,
            "notifications_enabled": self.notifications_enabled,
            "notifications_muted_until": self.notifications_muted_until,
            "mod_alert_overrides": dict(sorted(self.mod_alert_overrides.items())),
        }

    def _validate_overrides(self, raw_overrides: object) -> Dict[str, bool]:
        if not isinstance(raw_overrides, dict):
            raise PersistenceError("mod_alert_overrides must be an object")

        overrides = {}  # type: Dict[str, bool]
        for raw_mod_id, raw_enabled in raw_overrides.items():
            try:
                mod_id = validate_mod_id(raw_mod_id)
            except (TypeError, ValueError) as exc:
                raise PersistenceError(
                    "Settings.dmuc contains an invalid mod_id"
                ) from exc
            if type(raw_enabled) is not bool:
                raise PersistenceError(
                    "Every per-mod alert override must be True or False"
                )
            overrides[mod_id] = raw_enabled
        return overrides

    def _validate_network_state(self) -> None:
        if self.network_checks_enabled is True:
            if self.network_prompt_after is not None:
                raise PersistenceError(
                    "network_prompt_after is forbidden while network checks are enabled"
                )
            return
        if self.network_checks_enabled is False:
            if self.network_prompt_after is None:
                raise PersistenceError(
                    "paused network checks require a prompt timestamp"
                )
            return
        if self.network_prompt_after is not None:
            raise PersistenceError(
                "network_prompt_after requires network_checks_enabled=False"
            )

    def _validate_notification_state(self) -> None:
        if (
            self.notifications_enabled is not True
            and self.notifications_muted_until is not None
        ):
            raise PersistenceError(
                "notifications_muted_until requires notifications_enabled=True"
            )

    def _apply_dict(self, data: Dict[str, Any]) -> None:
        if not isinstance(data, dict):
            raise PersistenceError("Settings.dmuc root must be an object")
        if frozenset(data.keys()) != self._expected_fields():
            raise PersistenceError("Settings.dmuc fields are invalid")
        if isinstance(data["schema"], bool) or data["schema"] != MUC_SETTINGS_SCHEMA:
            raise PersistenceError("Settings.dmuc schema is unsupported")

        self.network_checks_enabled = self._validate_optional_bool(
            data["network_checks_enabled"],
            "network_checks_enabled",
        )
        self.network_prompt_after = self._validate_optional_timestamp(
            data["network_prompt_after"],
            "network_prompt_after",
        )
        self.notifications_enabled = self._validate_optional_bool(
            data["notifications_enabled"],
            "notifications_enabled",
        )
        self.notifications_muted_until = self._validate_optional_timestamp(
            data["notifications_muted_until"],
            "notifications_muted_until",
        )
        self.mod_alert_overrides = self._validate_overrides(
            data["mod_alert_overrides"]
        )
        self._validate_network_state()
        self._validate_notification_state()

    def load(self) -> None:
        logger = MUCLog.logger()
        settings_path = MUCPaths.settings_path()

        if not os.path.exists(settings_path):
            self.reset_defaults()
            self.save()
            logger.info("Created Settings.dmuc awaiting player consent")
            return

        try:
            self._apply_dict(
                read_dmuc_file(settings_path, MUC_STORAGE_KIND_SETTINGS)
            )
            logger.info("Loaded Settings.dmuc")
        except PersistenceError:
            logger.exception(
                "Settings.dmuc is invalid; safe consent defaults will replace it"
            )
            self.reset_defaults()
            self.save()

    def save(self) -> None:
        self._validate_network_state()
        self._validate_notification_state()
        write_dmuc_file(
            MUCPaths.settings_path(),
            self.to_dict(),
            MUC_STORAGE_KIND_SETTINGS,
        )

    def has_notification_consent(self) -> bool:
        return self.notifications_enabled is not None

    def network_access_allowed(self) -> bool:
        return self.network_checks_enabled is True

    def network_prompt_due(self, now: Optional[datetime] = None) -> bool:
        if self.network_checks_enabled is True:
            return False
        if self.network_checks_enabled is None or self.network_prompt_after is None:
            return True
        current = now or self._utc_now()
        return current >= self._parse_utc_text(
            self.network_prompt_after,
            "network_prompt_after",
        )

    def notifications_temporarily_muted(
        self,
        now: Optional[datetime] = None,
    ) -> bool:
        if self.notifications_muted_until is None:
            return False
        current = now or self._utc_now()
        return current < self._parse_utc_text(
            self.notifications_muted_until,
            "notifications_muted_until",
        )

    def enable_network_checks(self) -> None:
        self.network_checks_enabled = True
        self.network_prompt_after = None
        self.save()

    def snooze_network_prompt(
        self,
        now: Optional[datetime] = None,
    ) -> None:
        current = now or self._utc_now()
        self.network_checks_enabled = False
        self.network_prompt_after = self._utc_text(
            current + timedelta(seconds=CONSENT_SNOOZE_SECONDS)
        )
        self.save()

    def enable_notifications(self) -> None:
        self.notifications_enabled = True
        self.notifications_muted_until = None
        self.save()

    def mute_notifications(
        self,
        now: Optional[datetime] = None,
    ) -> None:
        current = now or self._utc_now()
        self.notifications_enabled = True
        self.notifications_muted_until = self._utc_text(
            current + timedelta(seconds=CONSENT_SNOOZE_SECONDS)
        )
        self.save()

    def alerts_enabled_for(
        self,
        mod_id: str,
        now: Optional[datetime] = None,
    ) -> bool:
        if self.notifications_temporarily_muted(now):
            return False
        override = self.mod_alert_overrides.get(mod_id)
        if override is not None:
            return override
        return self.notifications_enabled is True

    def set_all_alerts(self, enabled: bool) -> None:
        if type(enabled) is not bool:
            raise TypeError("enabled must be True or False")
        self.notifications_enabled = enabled
        self.notifications_muted_until = None
        self.mod_alert_overrides.clear()
        self.save()

    def set_mod_alert(self, mod_id: str, enabled: bool) -> None:
        validate_mod_id(mod_id)
        if type(enabled) is not bool:
            raise TypeError("enabled must be True or False")
        self.mod_alert_overrides[mod_id] = enabled
        self.save()
