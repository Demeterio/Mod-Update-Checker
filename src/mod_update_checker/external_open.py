# Demeterio: Mod Update Checker (script for The Sims 4)
# Do not copy, share or modify without my permission
# https://demeterio.tumblr.com
# https://discord.gg/mPyRPScgeS

"""Open only fixed Mod Update Checker-owned report and log locations."""

import os
import subprocess
import sys
import webbrowser
from pathlib import Path

from .errors import ExternalOpenError
from .paths import MUCPaths


def _allowed_targets():
    return frozenset(
        (
            os.path.abspath(MUCPaths.data_directory()),
            os.path.abspath(MUCPaths.log_path()),
            os.path.abspath(MUCPaths.update_report_path()),
        )
    )


def _open_fixed_target(target: str, require_file: bool) -> None:
    normalized = os.path.abspath(target)
    if normalized not in _allowed_targets():
        raise ExternalOpenError("Refused to open a non Mod Update Checker path")
    if require_file and not os.path.isfile(normalized):
        raise ExternalOpenError(
            "The requested Mod Update Checker file does not exist yet: {}".format(
                MUCPaths.privacy_safe_path(normalized)
            )
        )
    if not require_file and not os.path.isdir(normalized):
        raise ExternalOpenError(
            "The Mod Update Checker log directory does not exist: {}".format(
                MUCPaths.privacy_safe_path(normalized)
            )
        )

    try:
        if sys.platform.startswith("win"):
            startfile = getattr(os, "startfile", None)
            if startfile is None:
                raise OSError("os.startfile is unavailable")
            startfile(normalized)
            return
        if sys.platform == "darwin":
            subprocess.Popen(
                ("/usr/bin/open", normalized),
                close_fds=True,
            )
            return
        opened = webbrowser.open(Path(normalized).as_uri(), new=0)
        if opened is not True:
            raise OSError("No desktop file handler accepted the path")
    except ExternalOpenError:
        raise
    except Exception as exc:
        raise ExternalOpenError(
            "Unable to open the requested Mod Update Checker location"
        ) from exc


def open_update_report() -> None:
    from .update_report import MUCUpdateReport

    MUCUpdateReport.ensure_initial_report()
    _open_fixed_target(MUCPaths.update_report_path(), require_file=True)


def open_log_file() -> None:
    _open_fixed_target(MUCPaths.log_path(), require_file=True)


def open_log_folder() -> None:
    _open_fixed_target(MUCPaths.ensure_data_directory(), require_file=False)
