# Demeterio: Mod Update Checker (script for The Sims 4)
# Do not copy, share or modify without my permission
# https://demeterio.tumblr.com
# https://discord.gg/mPyRPScgeS

"""Player choices for network checks and update-summary notifications."""

from typing import Callable, Optional

from .errors import NotificationError
from .localization import localized_factory
from .logger import MUCLog
from .package_strings import (
    NETWORK_CONSENT_ALLOW,
    NETWORK_CONSENT_LATER,
    NETWORK_CONSENT_TEXT,
    NETWORK_CONSENT_TITLE,
    NOTIFICATIONS_CONSENT_ENABLE,
    NOTIFICATIONS_CONSENT_MUTE,
    NOTIFICATIONS_CONSENT_TEXT,
    NOTIFICATIONS_CONSENT_TITLE,
)
from .ui_resources import MUCUIResourceMarker


class MUCConsentService:
    """Ask for explicit choices only after a playable zone has loaded."""

    __slots__ = (
        "_settings",
        "_dialog_open",
        "_on_complete",
        "_settings_mode",
    )

    def __init__(self, settings) -> None:
        self._settings = settings
        self._dialog_open = False
        self._on_complete = None  # type: Optional[Callable[[bool], None]]
        self._settings_mode = False

    @staticmethod
    def _active_sim():
        import services

        manager = services.client_manager()
        if manager is None:
            return None
        client = manager.get_first_client()
        if client is None:
            return None
        return getattr(client, "active_sim", None)

    @staticmethod
    def _accepted(dialog) -> bool:
        try:
            from ui.ui_dialog import ButtonType
        except ImportError:
            return False
        response = getattr(dialog, "response", None)
        return response == ButtonType.DIALOG_RESPONSE_OK

    def _finish(self) -> None:
        callback = self._on_complete
        self._on_complete = None
        self._dialog_open = False
        self._settings_mode = False
        if callback is None:
            return
        try:
            callback(self._settings.network_access_allowed())
        except Exception:
            MUCLog.logger().exception(
                "Unable to complete the Mod Update Checker consent callback"
            )

    def _show_dialog(
        self,
        title_id: int,
        text_id: int,
        ok_id: int,
        cancel_id: int,
        callback,
    ) -> None:
        if MUCUIResourceMarker.is_available() is not True:
            raise NotificationError(
                "Demeterio_Mod_Update_Checker.package UI resources are unavailable"
            )

        try:
            from ui.ui_dialog import UiDialogOkCancel
        except ImportError as exc:
            raise NotificationError(
                "The Sims 4 confirmation dialog is unavailable"
            ) from exc

        active_sim = self._active_sim()
        if active_sim is None:
            raise NotificationError(
                "No active Sim is available for the consent dialog"
            )

        dialog = UiDialogOkCancel.TunableFactory().default(
            active_sim,
            title=localized_factory(title_id),
            text=localized_factory(text_id),
            text_ok=localized_factory(ok_id),
            text_cancel=localized_factory(cancel_id),
        )
        dialog.show_dialog(on_response=callback)

    def _continue_after_network_choice(self) -> None:
        if self._settings_mode:
            self._show_notification_consent()
            return
        if (
            self._settings.network_access_allowed()
            and self._settings.has_notification_consent() is False
        ):
            self._show_notification_consent()
            return
        self._finish()

    def _show_notification_consent(self) -> None:
        logger = MUCLog.logger()

        def _response(dialog) -> None:
            try:
                if self._accepted(dialog):
                    self._settings.enable_notifications()
                    logger.info("Player enabled update summaries")
                else:
                    self._settings.mute_notifications()
                    logger.info("Player muted update summaries for seven days")
            except Exception:
                logger.exception("Unable to store notification preference")
            self._finish()

        self._show_dialog(
            NOTIFICATIONS_CONSENT_TITLE,
            NOTIFICATIONS_CONSENT_TEXT,
            NOTIFICATIONS_CONSENT_ENABLE,
            NOTIFICATIONS_CONSENT_MUTE,
            _response,
        )

    def _show_network_consent(self) -> None:
        logger = MUCLog.logger()

        def _response(dialog) -> None:
            try:
                if self._accepted(dialog):
                    self._settings.enable_network_checks()
                    logger.info("Player enabled central registry checks")
                else:
                    self._settings.snooze_network_prompt()
                    logger.info(
                        "Player postponed the network question for seven days"
                    )
                self._continue_after_network_choice()
            except Exception:
                logger.exception("Unable to store network preference")
                self._finish()

        self._show_dialog(
            NETWORK_CONSENT_TITLE,
            NETWORK_CONSENT_TEXT,
            NETWORK_CONSENT_ALLOW,
            NETWORK_CONSENT_LATER,
            _response,
        )

    def open_settings(
        self,
        on_complete: Optional[Callable[[bool], None]] = None,
    ) -> bool:
        """Open both preference flows; return False when another dialog is open."""

        logger = MUCLog.logger()
        if self._dialog_open:
            logger.info("A Mod Update Checker consent or settings dialog is already open")
            return False

        self._on_complete = on_complete
        self._settings_mode = True
        self._dialog_open = True
        try:
            self._show_network_consent()
            return True
        except Exception:
            logger.exception("Unable to display the Mod Update Checker settings dialog")
            self._finish()
            return False

    def request_if_needed(
        self,
        on_complete: Optional[Callable[[bool], None]] = None,
        force_network_prompt: bool = False,
    ) -> bool:
        """Show due dialogs; return False if a dialog was queued."""

        logger = MUCLog.logger()
        if self._dialog_open:
            logger.info("Consent dialog is already open")
            return False

        self._on_complete = on_complete
        self._settings_mode = False
        try:
            if force_network_prompt or self._settings.network_prompt_due():
                self._dialog_open = True
                self._show_network_consent()
                return False

            if self._settings.network_access_allowed() is not True:
                self._finish()
                return True

            if self._settings.has_notification_consent() is False:
                self._dialog_open = True
                self._show_notification_consent()
                return False

            self._finish()
            return True
        except Exception:
            self._dialog_open = False
            logger.exception("Unable to display the Mod Update Checker consent dialog")
            self._finish()
            return True
