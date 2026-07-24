# Demeterio: Mod Update Checker (script for The Sims 4)
# Do not copy, share or modify without my permission
# https://demeterio.tumblr.com
# https://discord.gg/mPyRPScgeS

"""MUC file logger with an EA-log emergency fallback."""

import re
from logging import DEBUG, INFO, Formatter, getLogger
from logging.handlers import RotatingFileHandler
from typing import Any

from .constants import LOG_BACKUP_COUNT, LOG_MAX_BYTES
from .paths import MUCPaths

try:
    from sims4.log import Logger
except ImportError:
    Logger = None  # type: ignore


if Logger is not None:
    ea_log = Logger("ModUpdateChecker", default_owner="demeterio")
else:
    ea_log = None


_TRACEBACK_FILE_PATTERN = re.compile(
    r'(?P<prefix>\bFile\s+["\'])(?P<path>[^"\']+)(?P<suffix>["\'])'
)
_QUOTED_ABSOLUTE_PATH_PATTERN = re.compile(
    r'(?P<quote>["\'])'
    r'(?P<path>(?:[A-Za-z]:[\\/]|/(?:Users|home|Volumes|private|mnt)/|\\\\)[^"\']+)'
    r'(?P=quote)',
    re.IGNORECASE,
)


def _privacy_safe_log_text(value: object) -> str:
    """Remove user-specific parent directories from a log message or traceback."""
    text = str(value)

    try:
        physical_directory = MUCPaths.data_directory()
    except Exception:
        physical_directory = ""

    if physical_directory:
        safe_directory = MUCPaths.privacy_safe_path(physical_directory)
        variants = {
            physical_directory,
            physical_directory.replace("\\", "/"),
            physical_directory.replace("/", "\\"),
        }
        for raw_directory in sorted(variants, key=len, reverse=True):
            if raw_directory:
                text = text.replace(raw_directory, safe_directory)

    def replace_traceback_path(match) -> str:
        return "{}{}{}".format(
            match.group("prefix"),
            MUCPaths.privacy_safe_path(match.group("path")),
            match.group("suffix"),
        )

    text = _TRACEBACK_FILE_PATTERN.sub(replace_traceback_path, text)

    def replace_quoted_path(match) -> str:
        quote = match.group("quote")
        safe_path = MUCPaths.privacy_safe_path(match.group("path"))
        return "{}{}{}".format(quote, safe_path, quote)

    return _QUOTED_ABSOLUTE_PATH_PATTERN.sub(replace_quoted_path, text)


class _MUCFormatter(Formatter):
    """Keep intentional section spacing and sanitize local filesystem paths."""

    def format(self, record) -> str:
        rendered = _privacy_safe_log_text(super().format(record))
        try:
            message = record.getMessage()
        except Exception:
            return rendered

        if isinstance(message, str) and message.endswith(("\n", "\r")):
            return rendered.rstrip("\r\n") + "\n"
        return rendered


class MUCLog:
    """Create one rotating log and one session separator per game launch."""

    __slots__ = ()

    _initialized = False
    _logger = getLogger("demeterio_mod_update_checker")
    _FORMATTER = _MUCFormatter(
        fmt=(
            "%(asctime)s,%(msecs)03d %(levelname)-8s "
            "[%(filename)s:%(module)s:%(funcName)s:%(lineno)d] "
            "%(message)s"
        ),
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    _SESSION_SEPARATOR = (
        "------------------------------------------------------------------------"
    )

    @classmethod
    def _write_session_header(cls) -> None:
        cls._logger.info(cls._SESSION_SEPARATOR)
        cls._logger.info(
            "NEW GAME SESSION | Log mode: INFO | Standard log and cheat commands"
        )
        cls._logger.info("{}\n".format(cls._SESSION_SEPARATOR))

    @classmethod
    def logger(cls) -> Any:
        if cls._initialized is False:
            for handler in tuple(cls._logger.handlers):
                cls._logger.removeHandler(handler)
                handler.close()

            cls._logger.propagate = False
            cls._logger.setLevel(INFO)

            try:
                handler = RotatingFileHandler(
                    filename=MUCPaths.log_path(),
                    maxBytes=LOG_MAX_BYTES,
                    backupCount=LOG_BACKUP_COUNT,
                    encoding="utf-8",
                )
                handler.setFormatter(cls._FORMATTER)
                handler.setLevel(INFO)
                cls._logger.addHandler(handler)
                cls._write_session_header()
            except Exception as exc:
                cls.emergency(
                    "Unable to initialize the Mod Update Checker file log: {}".format(exc)
                )

            cls._initialized = True

        return cls._logger

    @classmethod
    def emergency(cls, message: str) -> None:
        """Write a privacy-sanitized message to EA logging as a fallback."""
        if ea_log is not None:
            try:
                ea_log.error(_privacy_safe_log_text(message))
            except Exception:
                pass

    @classmethod
    def exception(cls, message: str) -> None:
        try:
            cls.logger().exception(message)
        except Exception:
            cls.emergency(message)
