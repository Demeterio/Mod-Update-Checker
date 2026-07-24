# Demeterio: Mod Update Checker (script for The Sims 4)
# Do not copy, share or modify without my permission
# https://demeterio.tumblr.com
# https://discord.gg/mPyRPScgeS

"""Resolve all writable MUC paths from one location."""

import os
from os import path
from typing import Optional

from .constants import (
    MUC_CACHE_FILE_NAME,
    MUC_LOG_FILE_NAME,
    MUC_SETTINGS_FILE_NAME,
    MUC_UPDATE_REPORT_FILE_NAME,
)


class MUCPaths:
    """Resolve writable files beside the installed .ts4script."""

    __slots__ = ()

    _game_root_override = None  # type: Optional[str]

    @classmethod
    def set_game_root_override(cls, value: Optional[str]) -> None:
        """Override the writable directory for tests; pass None to restore discovery."""
        cls._game_root_override = value

    @classmethod
    def mod_directory(cls) -> str:
        """Return the physical directory containing the installed .ts4script."""
        if cls._game_root_override:
            return path.abspath(cls._game_root_override)

        environment_override = os.environ.get("DEMETERIO_MUC_GAME_ROOT")
        if environment_override:
            return path.abspath(environment_override)

        module_file = path.abspath(path.realpath(__file__))
        normalized = module_file.replace("\\", "/")
        lowered = normalized.lower()
        marker = ".ts4script"
        marker_index = lowered.find(marker)

        if marker_index >= 0:
            archive_end = marker_index + len(marker)
            archive_path = normalized[:archive_end]
            return path.normpath(path.dirname(archive_path))

        package_directory = path.dirname(module_file)
        return path.normpath(
            path.join(package_directory, path.pardir, path.pardir)
        )

    @classmethod
    def game_root(cls) -> str:
        return cls.mod_directory()

    @classmethod
    def data_directory(cls) -> str:
        return cls.mod_directory()

    @classmethod
    def ensure_data_directory(cls) -> str:
        directory = cls.data_directory()
        os.makedirs(directory, exist_ok=True)
        return directory

    @staticmethod
    def privacy_safe_path(value: str) -> str:
        """Return a useful path without exposing user-specific parent folders."""
        text = str(value or "").strip()
        if not text:
            return "<unknown path>"

        normalized = text.replace("\\", "/")
        parts = [part for part in normalized.split("/") if part]

        for index, part in enumerate(parts):
            if part.casefold() == "the sims 4":
                return "/".join(parts[index:])

        is_absolute = (
            normalized.startswith("/")
            or normalized.startswith("//")
            or (
                len(normalized) >= 3
                and normalized[1] == ":"
                and normalized[2] == "/"
            )
        )
        if not is_absolute:
            return normalized

        final_name = parts[-1] if parts else "<unknown>"
        return "<private path>/{}".format(final_name)

    @classmethod
    def log_path(cls) -> str:
        return path.join(cls.ensure_data_directory(), MUC_LOG_FILE_NAME)

    @classmethod
    def update_report_path(cls) -> str:
        return path.join(
            cls.ensure_data_directory(),
            MUC_UPDATE_REPORT_FILE_NAME,
        )

    @classmethod
    def settings_path(cls) -> str:
        return path.join(cls.ensure_data_directory(), MUC_SETTINGS_FILE_NAME)

    @classmethod
    def cache_path(cls) -> str:
        return path.join(cls.ensure_data_directory(), MUC_CACHE_FILE_NAME)
