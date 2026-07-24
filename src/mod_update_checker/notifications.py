# Demeterio: Mod Update Checker (script for The Sims 4)
# Do not copy, share or modify without my permission
# https://demeterio.tumblr.com
# https://discord.gg/mPyRPScgeS

"""One summary dialog for all update entries found in the central registry."""

import hashlib
from typing import NamedTuple

from .constants import STATUS_UPDATE_AVAILABLE
from .errors import NotificationError
from .external_open import open_log_folder, open_update_report
from .localization import localized_factory
from .logger import MUCLog
from .package_strings import (
    LOG_FOLDER_BUTTON,
    UPDATE_REPORT_BUTTON,
    UPDATE_TEXT,
    UPDATE_TITLE,
)
from .ui_resources import MUCUIResourceMarker


class NotificationSummary(NamedTuple):
    queued: int
    skipped: int
    errors: int


class Sims4NotificationPresenter:
    """Display a two-button summary dialog using package-backed strings."""

    __slots__ = ()

    @staticmethod
    def _active_sim():
        import services

        client_manager = services.client_manager()
        if client_manager is None:
            return None
        client = client_manager.get_first_client()
        if client is None:
            return None
        return getattr(client, "active_sim", None)

    def show_summary(self, update_count: int) -> None:
        if MUCUIResourceMarker.is_available() is not True:
            raise NotificationError(
                "Demeterio_Mod_Update_Checker.package UI resources are unavailable"
            )
        try:
            from ui.ui_dialog import ButtonType, UiDialogOkCancel
        except ImportError as exc:
            raise NotificationError(
                "The Sims 4 summary dialog is unavailable"
            ) from exc

        active_sim = self._active_sim()
        if active_sim is None:
            raise NotificationError(
                "No active Sim is available for the update summary"
            )

        def _response(dialog) -> None:
            try:
                response = getattr(dialog, "response", None)
                if response == ButtonType.DIALOG_RESPONSE_OK:
                    open_update_report()
                elif response == ButtonType.DIALOG_RESPONSE_CANCEL:
                    open_log_folder()
            except Exception:
                MUCLog.logger().exception(
                    "Unable to process the Mod Update Checker update-summary button"
                )

        try:
            dialog = UiDialogOkCancel.TunableFactory().default(
                active_sim,
                title=localized_factory(UPDATE_TITLE),
                text=localized_factory(UPDATE_TEXT, update_count),
                text_ok=localized_factory(UPDATE_REPORT_BUTTON),
                text_cancel=localized_factory(LOG_FOLDER_BUTTON),
            )
            dialog.show_dialog(on_response=_response)
        except Exception as exc:
            raise NotificationError(
                "The Sims 4 rejected the update summary dialog"
            ) from exc


class MUCNotificationService:
    """Show one deduplicated summary for alert-enabled available updates."""

    __slots__ = ("_registry", "_settings", "_cache", "_presenter")

    def __init__(
        self,
        registry,
        settings,
        cache,
        presenter=None,
    ) -> None:
        self._registry = registry
        self._settings = settings
        self._cache = cache
        self._presenter = presenter or Sims4NotificationPresenter()

    @staticmethod
    def _signature(states) -> str:
        values = [
            "{}={}".format(state.mod_id, state.available_version)
            for state in states
        ]
        payload = "\n".join(sorted(values)).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def show_summary(self) -> NotificationSummary:
        logger = MUCLog.logger()
        states = [
            state
            for state in self._registry.values()
            if state.status == STATUS_UPDATE_AVAILABLE
            and self._settings.alerts_enabled_for(state.mod_id) is True
        ]
        if not states:
            self._cache.clear_notification_signature()
            self._cache.save()
            logger.info("No alert-enabled updates require a summary dialog")
            return NotificationSummary(0, 1, 0)

        signature = self._signature(states)
        if self._cache.notification_signature() == signature:
            logger.info(
                "Update summary already displayed for the current version set"
            )
            return NotificationSummary(0, 1, 0)

        self._presenter.show_summary(len(states))
        self._cache.mark_notification_signature(signature)
        self._cache.save()
        logger.info(
            "Update summary queued | {} alert-enabled update(s)".format(
                len(states)
            )
        )
        return NotificationSummary(1, 0, 0)
