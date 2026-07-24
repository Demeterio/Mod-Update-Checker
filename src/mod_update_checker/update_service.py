# Demeterio: Mod Update Checker (script for The Sims 4)
# Do not copy, share or modify without my permission
# https://demeterio.tumblr.com
# https://discord.gg/mPyRPScgeS

"""Fetch one central registry and apply it to all installed declarations."""

import traceback
from datetime import datetime, timedelta
from typing import NamedTuple, Optional

from .cache import parse_utc_text, utc_now, utc_text
from .central_registry import CentralRegistryClient
from .constants import (
    REGISTRY_MAX_AGE_SECONDS,
    REGISTRY_MAX_FUTURE_SKEW_SECONDS,
    REGISTRY_RATE_RETRY_SECONDS,
    STATUS_UPDATE_AVAILABLE,
)
from .errors import (
    CentralRegistryValidationError,
    ModUpdateCheckerError,
    RegistryRateLimitError,
)
from .logger import MUCLog
from .models import CentralRegistryDocument
from .notifications import MUCNotificationService
from .update_report import MUCUpdateReport
from .versioning import compare_versions


class CheckSummary(NamedTuple):
    checked: int
    updates: int
    errors: int
    notifications: int = 0
    missing: int = 0


class RegistryNetworkOutcome(NamedTuple):
    document: Optional[CentralRegistryDocument]
    error: Optional[BaseException]
    traceback_text: str
    started_at: str
    completed_at: str


class UpdateService:
    """Coordinate one pure network fetch with main-thread state application."""

    __slots__ = (
        "_registry",
        "_settings",
        "_cache",
        "_client",
        "_notifications",
        "_report",
    )

    def __init__(
        self,
        registry,
        settings,
        cache,
        client=None,
        notifications=None,
        report=None,
    ) -> None:
        self._registry = registry
        self._settings = settings
        self._cache = cache
        self._client = client or CentralRegistryClient()
        self._notifications = notifications or MUCNotificationService(
            registry,
            settings,
            cache,
        )
        self._report = report or MUCUpdateReport()

    @property
    def client(self) -> CentralRegistryClient:
        return self._client

    def is_due(
        self,
        force: bool = False,
        now: Optional[datetime] = None,
    ) -> bool:
        return self._cache.is_due(now or utc_now(), force=force)

    def begin_check(self, started_at: Optional[datetime] = None) -> None:
        current = started_at or utc_now()
        try:
            self._report.write_in_progress(
                self._registry.count(),
                utc_text(current),
            )
        except Exception:
            MUCLog.logger().exception(
                "Unable to replace the Mod Update Checker update report at check start"
            )
        MUCLog.logger().info(
            "Central registry check started | {} registered mod(s)".format(
                self._registry.count()
            )
        )

    def fetch_registry(
        self,
        started_at: Optional[datetime] = None,
    ) -> RegistryNetworkOutcome:
        """Run only bounded network and JSON work in a background thread."""

        start = started_at or utc_now()
        try:
            document = self._client.fetch()
            return RegistryNetworkOutcome(
                document,
                None,
                "",
                utc_text(start),
                utc_text(utc_now()),
            )
        except Exception as exc:
            return RegistryNetworkOutcome(
                None,
                exc,
                traceback.format_exc(),
                utc_text(start),
                utc_text(utc_now()),
            )

    @staticmethod
    def _retry_time_for_error(
        error: BaseException,
        now: datetime,
    ) -> Optional[datetime]:
        if isinstance(error, RegistryRateLimitError):
            retry_at = getattr(error, "retry_at", "")
            if retry_at:
                try:
                    return parse_utc_text(retry_at, "retry_at")
                except ModUpdateCheckerError:
                    pass
            return now + timedelta(seconds=REGISTRY_RATE_RETRY_SECONDS)
        return None

    @staticmethod
    def _underlying_error_text(error: BaseException) -> str:
        """Return one concise technical cause for the private log only."""

        cause = getattr(error, "__cause__", None)
        if cause is None:
            return ""
        detail = str(cause).strip() or cause.__class__.__name__
        return "{}: {}".format(cause.__class__.__name__, detail)

    @staticmethod
    def _select_registry_entry(
        document: CentralRegistryDocument,
        mod_id: str,
        release_channel: str,
    ):
        """Resolve the best registry entry allowed by the installed channel."""

        stable_entry = document.entries.get((mod_id, "stable"))
        if release_channel != "prerelease":
            return stable_entry

        prerelease_entry = document.entries.get((mod_id, "prerelease"))
        if stable_entry is None:
            return prerelease_entry
        if prerelease_entry is None:
            return stable_entry
        if compare_versions(
            prerelease_entry.version,
            stable_entry.version,
        ) > 0:
            return prerelease_entry
        return stable_entry

    def _validate_document_freshness(
        self,
        document: CentralRegistryDocument,
        now: datetime,
    ) -> None:
        """Reject stale, future-dated, or rolled-back signed registries."""

        generated_at = parse_utc_text(document.generated_at, "generated_at")
        if generated_at > now + timedelta(
            seconds=REGISTRY_MAX_FUTURE_SKEW_SECONDS
        ):
            raise CentralRegistryValidationError(
                "Central registry generated_at is too far in the future"
            )
        if generated_at < now - timedelta(seconds=REGISTRY_MAX_AGE_SECONDS):
            raise CentralRegistryValidationError(
                "Central registry is older than the allowed freshness window"
            )

        previous_text = self._cache.registry_generated_at()
        if not previous_text:
            return
        previous = parse_utc_text(
            previous_text,
            "last_registry_generated_at",
        )
        if generated_at < previous:
            raise CentralRegistryValidationError(
                "Central registry is older than the last accepted registry"
            )

    def _write_final_report(
        self,
        checked_at: str,
        generated_at: str = "",
        registry_error: str = "",
    ) -> None:
        try:
            self._report.write_final(
                self._registry,
                self._settings,
                checked_at,
                registry_generated_at=generated_at,
                registry_error=registry_error,
            )
        except Exception:
            MUCLog.logger().exception(
                "Unable to replace the Mod Update Checker update report after a check"
            )

    def _apply_failure(
        self,
        error: BaseException,
        outcome: RegistryNetworkOutcome,
        now: datetime,
    ) -> CheckSummary:
        """Persist and report one typed worker or registry failure."""

        logger = MUCLog.logger()
        message = str(error) or error.__class__.__name__
        retry_at = self._retry_time_for_error(error, now)
        self._cache.mark_failure(message, now, retry_at=retry_at)
        self._cache.save()

        if isinstance(error, ModUpdateCheckerError):
            logger.warning(
                "Expected central registry failure | {}".format(message)
            )
            technical_cause = self._underlying_error_text(error)
            if technical_cause:
                logger.warning(
                    "Central registry failure cause | {}".format(technical_cause)
                )
        else:
            logger.error(
                "Unexpected central registry failure | {}\n{}".format(
                    message,
                    outcome.traceback_text.strip()
                    or "Worker traceback unavailable",
                )
            )

        self._write_final_report(
            outcome.completed_at,
            generated_at=self._cache.registry_generated_at(),
            registry_error=message,
        )
        return CheckSummary(0, 0, 1, 0, 0)

    def apply_outcome(self, outcome: RegistryNetworkOutcome) -> CheckSummary:
        """Apply the completed central document on the game/main thread."""

        logger = MUCLog.logger()
        now = utc_now()
        error = outcome.error
        if error is not None:
            return self._apply_failure(error, outcome, now)

        document = outcome.document
        if document is None:
            return self._apply_failure(
                RuntimeError(
                    "Central registry worker returned no document and no error"
                ),
                outcome,
                now,
            )

        try:
            self._validate_document_freshness(document, now)
        except ModUpdateCheckerError as exc:
            return self._apply_failure(exc, outcome, now)

        checked = 0
        updates = 0
        errors = 0
        missing = 0
        for state in self._registry.values():
            checked += 1
            channel = state.declaration.release_channel
            entry = self._select_registry_entry(
                document,
                state.mod_id,
                channel,
            )
            if entry is None:
                missing += 1
                expected_channels = (
                    "stable or prerelease"
                    if channel == "prerelease"
                    else "stable"
                )
                message = (
                    "No {} entry exists in the current central registry".format(
                        expected_channels
                    )
                )
                self._cache.mark_registry_missing(
                    state.mod_id,
                    channel,
                    now,
                )
                cached = self._cache.get(state.mod_id) or {}
                state.apply_registry_missing(
                    cached.get("missing_since", utc_text(now)),
                    message,
                )
                logger.warning(
                    "Central registry entry missing | {} | {} | "
                    "last known version retained".format(
                        state.mod_id,
                        expected_channels,
                    )
                )
                continue

            state.apply_available(
                entry.version,
                entry.release_tag,
                entry.checked_at,
            )
            self._cache.set_entry(
                state.mod_id,
                channel,
                entry.version,
                entry.release_tag,
                entry.checked_at,
            )
            if state.status == STATUS_UPDATE_AVAILABLE:
                updates += 1
            logger.info(
                "Central registry result | {} | installed {} | available {} | "
                "status {} | release {} | selected channel {}".format(
                    state.mod_id,
                    state.installed_version,
                    state.available_version,
                    state.status,
                    state.release_tag,
                    entry.release_channel,
                )
            )

        self._cache.remove_stale(self._registry.mod_ids())
        self._cache.mark_success(now, document.generated_at)
        self._cache.save()
        self._write_final_report(
            outcome.completed_at,
            generated_at=document.generated_at,
        )

        notifications = 0
        notification_errors = 0
        try:
            notification_summary = self._notifications.show_summary()
            notifications = notification_summary.queued
            notification_errors = notification_summary.errors
        except ModUpdateCheckerError as exc:
            notification_errors = 1
            logger.warning("Update summary failure | {}".format(exc))
        except Exception:
            notification_errors = 1
            logger.exception("Unexpected update summary failure")

        logger.info(
            "Central registry check completed | checked {} | updates {} | "
            "missing {} | errors {} | notifications {}".format(
                checked,
                updates,
                missing,
                errors + notification_errors,
                notifications,
            )
        )
        return CheckSummary(
            checked,
            updates,
            errors + notification_errors,
            notifications,
            missing,
        )

    def check_registry(self) -> CheckSummary:
        """Synchronous helper retained for unit tests and controlled debugging."""

        started = utc_now()
        self.begin_check(started)
        return self.apply_outcome(self.fetch_registry(started))
