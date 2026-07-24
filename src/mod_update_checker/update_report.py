# Demeterio: Mod Update Checker (script for The Sims 4)
# Do not copy, share or modify without my permission
# https://demeterio.tumblr.com
# https://discord.gg/mPyRPScgeS

"""Create the player-facing update report, replacing it after every check."""

import os
from datetime import datetime, timezone
from typing import NamedTuple, Optional

from .central_registry import central_registry_url
from .constants import (
    STATUS_CHECK_ERROR,
    STATUS_REGISTRY_MISSING,
    STATUS_UP_TO_DATE,
    STATUS_UPDATE_AVAILABLE,
)
from .logger import MUCLog
from .paths import MUCPaths
from .provider_urls import build_download_page_url


class UpdateReportSummary(NamedTuple):
    registered: int
    updates: int
    up_to_date: int
    errors: int
    path: str
    missing: int = 0


def _display_time(value: Optional[str]) -> str:
    if not value:
        return "Unknown"
    try:
        text = value.strip()
        parsed = datetime.fromisoformat(
            text[:-1] + "+00:00" if text.endswith("Z") else text
        )
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    except (TypeError, ValueError):
        return str(value)


def _atomic_overwrite(lines) -> str:
    report_path = MUCPaths.update_report_path()
    temporary_path = report_path + ".tmp"
    text = "\n".join(lines).rstrip() + "\n"
    try:
        with open(temporary_path, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, report_path)
    except Exception:
        try:
            if os.path.exists(temporary_path):
                os.remove(temporary_path)
        except OSError:
            pass
        raise
    return report_path


class MUCUpdateReport:
    """Write a concise player report and always replace the previous report."""

    __slots__ = ()

    @staticmethod
    def ensure_initial_report() -> str:
        """Create a helpful first-run report without replacing an existing report."""

        report_path = MUCPaths.update_report_path()
        if os.path.isfile(report_path):
            return report_path

        path = _atomic_overwrite(
            (
                "Demeterio: Mod Update Checker",
                "================================",
                "",
                "No update report is available yet.",
                "",
                "An update report will be generated after the first registry check.",
                "Registry: {}".format(central_registry_url()),
            )
        )
        MUCLog.logger().info(
            "Initial Mod Update Checker update report created | {}".format(path)
        )
        return path

    @staticmethod
    def write_in_progress(registered_count: int, started_at: str) -> str:
        lines = [
            "Demeterio: Mod Update Checker",
            "================================",
            "",
            "A central registry check is currently in progress.",
            "Started: {}".format(_display_time(started_at)),
            "Registered mods: {}".format(registered_count),
            "Registry: {}".format(central_registry_url()),
            "",
            "This file is replaced when the check completes.",
        ]
        return _atomic_overwrite(lines)

    @staticmethod
    def write_final(
        registry,
        settings,
        checked_at: str,
        registry_generated_at: str = "",
        registry_error: str = "",
    ) -> UpdateReportSummary:
        states = registry.values()
        updates = [
            state for state in states if state.status == STATUS_UPDATE_AVAILABLE
        ]
        up_to_date = [
            state for state in states if state.status == STATUS_UP_TO_DATE
        ]
        missing = [
            state for state in states if state.status == STATUS_REGISTRY_MISSING
        ]
        errors = [
            state for state in states if state.status == STATUS_CHECK_ERROR
        ]

        lines = [
            "Demeterio: Mod Update Checker",
            "================================",
            "",
            "Check completed: {}".format(_display_time(checked_at)),
            "Registry generated: {}".format(
                _display_time(registry_generated_at)
            ),
            "Registry: {}".format(central_registry_url()),
            "",
            "Registered mods: {}".format(len(states)),
            "Updates available: {}".format(len(updates)),
            "Up to date: {}".format(len(up_to_date)),
            "Not listed in registry: {}".format(len(missing)),
            "Errors: {}".format(len(errors)),
        ]
        if registry_error:
            lines.extend(("", "REGISTRY ERROR", "--------------", registry_error))

        lines.extend(("", "UPDATES AVAILABLE", "-----------------"))
        if not updates:
            lines.append("No updates are currently available.")
        for state in updates:
            try:
                page_url = build_download_page_url(
                    state.declaration.download_page,
                    release_tag=state.release_tag,
                )
            except Exception as exc:
                page_url = "Unavailable ({})".format(exc)
            lines.extend(
                (
                    "",
                    state.mod_name,
                    "Mod ID: {}".format(state.mod_id),
                    "Installed version: {}".format(state.installed_version),
                    "Available version: {}".format(state.available_version),
                    "Release channel: {}".format(
                        state.declaration.release_channel
                    ),
                    "Release tag: {}".format(state.release_tag or "Unknown"),
                    "Official update page: {}".format(page_url),
                    "In-game alert: {}".format(
                        "enabled"
                        if settings.alerts_enabled_for(state.mod_id)
                        else "disabled"
                    ),
                )
            )

        lines.extend(("", "NOT LISTED IN REGISTRY", "----------------------"))
        if not missing:
            lines.append("All registered mods were found in the current registry.")
        for state in missing:
            lines.extend(
                (
                    "",
                    state.mod_name,
                    "Mod ID: {}".format(state.mod_id),
                    "Installed version: {}".format(state.installed_version),
                    "Release channel: {}".format(
                        state.declaration.release_channel
                    ),
                    "Registry status: Not currently listed",
                    "Last known available version: {}".format(
                        state.available_version or "Unknown"
                    ),
                    "Last known release tag: {}".format(
                        state.release_tag or "Unknown"
                    ),
                    "Last confirmed: {}".format(
                        _display_time(state.checked_at)
                    ),
                    "Missing since: {}".format(
                        _display_time(state.registry_missing_since)
                    ),
                    "Note: {}".format(
                        state.error
                        or "The entry may not have been added yet or may be temporarily unavailable."
                    ),
                )
            )

        lines.extend(("", "CHECK ERRORS", "------------"))
        if not errors:
            lines.append("No errors were reported.")
        for state in errors:
            lines.extend(
                (
                    "",
                    state.mod_name,
                    "Mod ID: {}".format(state.mod_id),
                    "Installed version: {}".format(state.installed_version),
                    "Release channel: {}".format(
                        state.declaration.release_channel
                    ),
                    "Error: {}".format(state.error or "Unknown error"),
                )
            )

        lines.extend(("", "UP TO DATE", "----------"))
        if not up_to_date:
            lines.append("No checked mods are currently marked up to date.")
        for state in up_to_date:
            lines.append(
                "{} — {}".format(state.mod_name, state.installed_version)
            )

        lines.extend(
            (
                "",
                "The report is overwritten after every completed check.",
                "Technical details remain available in the Mod Update Checker log file.",
            )
        )
        path = _atomic_overwrite(lines)
        MUCLog.logger().info(
            "Update report replaced | updates {} | missing {} | errors {} | {}".format(
                len(updates),
                len(missing),
                len(errors),
                path,
            )
        )
        return UpdateReportSummary(
            len(states),
            len(updates),
            len(up_to_date),
            len(errors),
            path,
            len(missing),
        )
