# Demeterio: Mod Update Checker (script for The Sims 4)
# Do not copy, share or modify without my permission
# https://demeterio.tumblr.com
# https://discord.gg/mPyRPScgeS

"""In-game cheat commands for Demeterio: Mod Update Checker."""

from sims4.commands import Command, CommandType, CheatOutput

from . import __version__
from .constants import MUC_GLOBAL_TARGET
from .external_open import open_log_file, open_log_folder, open_update_report
from .logger import MUCLog
from .runtime import get_runtime
from .validation import validate_mod_id


def _log_cheat_start(logger, cheatcode: str) -> None:
    logger.info("Cheatcode: {}".format(cheatcode))
    logger.info("Start...")


def _complete_cheat(logger, output, data: str, succeed: bool) -> None:
    logger.info("Succeed: {}".format(succeed))
    logger.info("...Completed\n\n")
    output(data)


@Command("demeterio.muc_version", command_type=CommandType.Live)
def _demeterio_muc_version(_connection=None) -> None:
    output = CheatOutput(_connection)
    logger = MUCLog.logger()
    _log_cheat_start(logger, "demeterio.muc_version")
    try:
        runtime = get_runtime()
        data = (
            "Mod Update Checker: Version {} and {} registered mod(s)"
        ).format(__version__, runtime.registry.count())
        logger.info(data.replace("\n", " | "))
        _complete_cheat(logger, output, data, True)
    except Exception:
        logger.exception(
            "Exception occurred on the cheatcode demeterio.muc_version"
        )
        _complete_cheat(
            logger,
            output,
            "Mod Update Checker: Unable to read the version. "
            "Please check the Mod Update Checker log file",
            False,
        )


@Command("demeterio.muc_getlist", command_type=CommandType.Live)
def _demeterio_muc_getlist(_connection=None) -> None:
    output = CheatOutput(_connection)
    logger = MUCLog.logger()
    _log_cheat_start(logger, "demeterio.muc_getlist")
    try:
        runtime = get_runtime()
        logger.info(
            "{}\n".format(
                runtime.registry.detailed_log_text(runtime.settings)
            )
        )
        snapshot = runtime.scheduler_snapshot()
        logger.info(
            "Central registry scheduler | running {} | pending {} | checked {} | "
            "updates {} | missing {} | errors {} | notifications {}".format(
                snapshot.running,
                snapshot.pending,
                snapshot.checked,
                snapshot.updates,
                snapshot.missing,
                snapshot.errors,
                snapshot.notifications,
            )
        )
        _complete_cheat(
            logger,
            output,
            (
                "Mod Update Checker: {} registered mod(s). The complete list "
                "was written to the Mod Update Checker log file"
            ).format(runtime.registry.count()),
            True,
        )
    except Exception:
        logger.exception(
            "Exception occurred on the cheatcode demeterio.muc_getlist"
        )
        _complete_cheat(
            logger,
            output,
            "Mod Update Checker: Unable to list registered mods. "
            "Please check the Mod Update Checker log file",
            False,
        )


@Command("demeterio.muc_check", command_type=CommandType.Live)
def _demeterio_muc_check(_connection=None) -> None:
    output = CheatOutput(_connection)
    logger = MUCLog.logger()
    _log_cheat_start(logger, "demeterio.muc_check")
    try:
        runtime = get_runtime()
        request = runtime.request_manual_check()
        if request.consent_prompted:
            _complete_cheat(
                logger,
                output,
                (
                    "Mod Update Checker: Please answer the in-game network "
                    "dialog. The central registry check will start only if "
                    "registry access is allowed"
                ),
                True,
            )
            return
        if request.started:
            logger.info("Manual central registry check requested")
            _complete_cheat(
                logger,
                output,
                (
                    "Mod Update Checker: Central registry check will start in 15 seconds. One "
                    "report will replace the previous update report when the "
                    "check completes"
                ),
                True,
            )
            return
        _complete_cheat(
            logger,
            output,
            (
                "Mod Update Checker: The central registry check was not started. "
                "Network permission is disabled, a retry delay is active, or "
                "a check is already running. Please check the Mod Update Checker log file"
            ),
            False,
        )
    except Exception:
        logger.exception(
            "Exception occurred on the cheatcode demeterio.muc_check"
        )
        _complete_cheat(
            logger,
            output,
            "Mod Update Checker: An error occurred while starting the central "
            "registry check. Please check the Mod Update Checker log file",
            False,
        )


@Command("demeterio.muc_settings", command_type=CommandType.Live)
def _demeterio_muc_settings(_connection=None) -> None:
    output = CheatOutput(_connection)
    logger = MUCLog.logger()
    _log_cheat_start(logger, "demeterio.muc_settings")
    try:
        runtime = get_runtime()
        opened = runtime.open_settings()
        if opened:
            _complete_cheat(
                logger,
                output,
                "Mod Update Checker: Settings dialogs opened",
                True,
            )
            return
        _complete_cheat(
            logger,
            output,
            "Mod Update Checker: A settings or consent dialog is already open",
            False,
        )
    except Exception:
        logger.exception(
            "Exception occurred on the cheatcode demeterio.muc_settings"
        )
        _complete_cheat(
            logger,
            output,
            "Mod Update Checker: Unable to open settings. "
            "Please check the Mod Update Checker log file",
            False,
        )


def _set_alert(target: str, enabled: bool, output, logger) -> None:
    runtime = get_runtime()
    requested = str(target).strip()
    if requested == MUC_GLOBAL_TARGET:
        runtime.settings.set_all_alerts(enabled)
        logger.info(
            "Notifications {} for all registered mods".format(
                "enabled" if enabled else "disabled"
            )
        )
        _complete_cheat(
            logger,
            output,
            "Mod Update Checker: Notifications {} for all mods".format(
                "enabled" if enabled else "disabled"
            ),
            True,
        )
        return
    try:
        mod_id = validate_mod_id(requested)
    except (TypeError, ValueError):
        logger.warning(
            "Invalid alert target: {}. Only an exact mod_id or * is accepted".format(
                requested
            )
        )
        _complete_cheat(
            logger,
            output,
            "Mod Update Checker: Use an exact mod_id or *",
            False,
        )
        return
    state = runtime.registry.get(mod_id)
    if state is None:
        logger.warning(
            "Alert target is not a registered mod_id: {}".format(mod_id)
        )
        _complete_cheat(
            logger,
            output,
            "Mod Update Checker: This mod_id is not registered. "
            "Use demeterio.muc_getlist and check the Mod Update Checker log file",
            False,
        )
        return
    runtime.settings.set_mod_alert(mod_id, enabled)
    logger.info(
        "Notifications {} | {} | {}".format(
            "enabled" if enabled else "disabled",
            state.mod_name,
            mod_id,
        )
    )
    _complete_cheat(
        logger,
        output,
        "Mod Update Checker: Notifications {} for {}".format(
            "enabled" if enabled else "disabled",
            state.mod_name,
        ),
        True,
    )


@Command("demeterio.muc_alerton", command_type=CommandType.Live)
def _demeterio_muc_alerton(target: str = "", _connection=None) -> None:
    output = CheatOutput(_connection)
    logger = MUCLog.logger()
    _log_cheat_start(logger, "demeterio.muc_alerton {}".format(target))
    try:
        _set_alert(target, True, output, logger)
    except Exception:
        logger.exception(
            "Exception occurred on the cheatcode demeterio.muc_alerton"
        )
        _complete_cheat(
            logger,
            output,
            "Mod Update Checker: Unable to enable notifications. "
            "Please check the Mod Update Checker log file",
            False,
        )


@Command("demeterio.muc_alertoff", command_type=CommandType.Live)
def _demeterio_muc_alertoff(target: str = "", _connection=None) -> None:
    output = CheatOutput(_connection)
    logger = MUCLog.logger()
    _log_cheat_start(logger, "demeterio.muc_alertoff {}".format(target))
    try:
        _set_alert(target, False, output, logger)
    except Exception:
        logger.exception(
            "Exception occurred on the cheatcode demeterio.muc_alertoff"
        )
        _complete_cheat(
            logger,
            output,
            "Mod Update Checker: Unable to disable notifications. "
            "Please check the Mod Update Checker log file",
            False,
        )


def _open_command(command_name: str, opener, success_text: str, _connection) -> None:
    output = CheatOutput(_connection)
    logger = MUCLog.logger()
    _log_cheat_start(logger, command_name)
    try:
        opener()
        _complete_cheat(logger, output, success_text, True)
    except Exception:
        logger.exception("Unable to execute {}".format(command_name))
        _complete_cheat(
            logger,
            output,
            "Mod Update Checker: Unable to open the requested location. "
            "Please check the Mod Update Checker log file",
            False,
        )


@Command("demeterio.muc_openreport", command_type=CommandType.Live)
def _demeterio_muc_openreport(_connection=None) -> None:
    _open_command(
        "demeterio.muc_openreport",
        open_update_report,
        "Mod Update Checker: Update report opened",
        _connection,
    )


@Command("demeterio.muc_openlogfolder", command_type=CommandType.Live)
def _demeterio_muc_openlogfolder(_connection=None) -> None:
    _open_command(
        "demeterio.muc_openlogfolder",
        open_log_folder,
        "Mod Update Checker: Log folder opened",
        _connection,
    )


@Command("demeterio.muc_openlog", command_type=CommandType.Live)
def _demeterio_muc_openlog(_connection=None) -> None:
    _open_command(
        "demeterio.muc_openlog",
        open_log_file,
        "Mod Update Checker: Technical log opened",
        _connection,
    )
