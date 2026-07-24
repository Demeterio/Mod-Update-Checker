# Demeterio: Mod Update Checker (script for The Sims 4)
# Do not copy, share or modify without my permission
# https://demeterio.tumblr.com
# https://discord.gg/mPyRPScgeS

"""Validation helpers for untrusted package and central-registry data."""

import re
from typing import Optional

from .constants import (
    PROVIDER_GITHUB_RELEASE,
    PROVIDER_MOD_THE_SIMS,
    PROVIDER_SIM_FILE_SHARE,
    SUPPORTED_PROVIDERS,
)
from .errors import DeclarationValidationError
from .models import DownloadPage, ModDeclaration
from .versioning import parse_version

_GITHUB_NAME_PATTERN = re.compile(
    r"^[A-Za-z0-9](?:[A-Za-z0-9_.-]{0,98}[A-Za-z0-9])?$"
)
_MOD_ID_PATTERN = re.compile(
    r"^[a-z0-9_-]+\.[a-z0-9_-]+\.[0-9A-F]{16}$"
)
_TAG_PATTERN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._/+\-]{0,127}$"
)
_RELEASE_CHANNELS = frozenset(("stable", "prerelease"))


def require_non_empty_string(
    value: object,
    field_name: str,
    maximum: int,
) -> str:
    """Validate one exact configuration string without normalizing it."""

    if not isinstance(value, str):
        raise TypeError("{} must be a string".format(field_name))
    if value != value.strip():
        raise ValueError(
            "{} must not contain leading or trailing whitespace".format(
                field_name
            )
        )
    if not value:
        raise ValueError("{} must not be empty".format(field_name))
    if len(value) > maximum:
        raise ValueError("{} is too long".format(field_name))
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError(
            "{} must not contain control characters".format(field_name)
        )
    return value


def _validate_positive_identifier(
    value: Optional[int],
    field_name: str,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("{} must be an integer".format(field_name))
    if value <= 0:
        raise ValueError("{} must be greater than zero".format(field_name))
    return value


def validate_github_name(
    value: object,
    field_name: str,
) -> str:
    exact = require_non_empty_string(value, field_name, 100)
    if not _GITHUB_NAME_PATTERN.fullmatch(exact):
        raise ValueError(
            "{} contains unsupported characters".format(field_name)
        )
    if ".." in exact:
        raise ValueError(
            "{} must not contain consecutive dots".format(field_name)
        )
    return exact


def validate_mod_id(value: object) -> str:
    mod_id = require_non_empty_string(value, "mod_id", 128)
    if not _MOD_ID_PATTERN.fullmatch(mod_id):
        raise ValueError(
            "mod_id must use creator.mod_name.FNV64, where creator and "
            "mod_name contain only lowercase letters, digits, underscores, "
            "or hyphens, and FNV64 is exactly 16 uppercase hexadecimal "
            "characters"
        )
    return mod_id


def validate_release_channel(value: object) -> str:
    channel = require_non_empty_string(value, "release_channel", 32)
    if channel not in _RELEASE_CHANNELS:
        raise ValueError(
            "release_channel must be exactly stable or prerelease"
        )
    return channel


def validate_release_tag(value: object) -> str:
    release_tag = require_non_empty_string(value, "release_tag", 128)
    if not _TAG_PATTERN.fullmatch(release_tag):
        raise ValueError("release_tag contains unsupported characters")
    return release_tag


def validate_download_page(page: DownloadPage) -> None:
    try:
        if page.provider not in SUPPORTED_PROVIDERS:
            raise ValueError("unsupported download-page provider")

        if page.provider == PROVIDER_GITHUB_RELEASE:
            validate_github_name(
                page.github_owner,
                "download_page.github_owner",
            )
            validate_github_name(
                page.github_repository,
                "download_page.github_repository",
            )
            if page.submission_id is not None or page.folder_id is not None:
                raise ValueError(
                    "GitHub provider forbids submission_id and folder_id"
                )
            return

        if page.provider == PROVIDER_MOD_THE_SIMS:
            _validate_positive_identifier(
                page.submission_id,
                "mod_the_sims_submission_id",
            )
            if (
                page.github_owner is not None
                or page.github_repository is not None
                or page.folder_id is not None
            ):
                raise ValueError(
                    "Mod The Sims provider accepts only submission_id"
                )
            return

        if page.provider == PROVIDER_SIM_FILE_SHARE:
            _validate_positive_identifier(
                page.folder_id,
                "sim_file_share_folder_id",
            )
            if (
                page.github_owner is not None
                or page.github_repository is not None
                or page.submission_id is not None
            ):
                raise ValueError(
                    "Sim File Share provider accepts only folder_id"
                )
            return
    except (TypeError, ValueError) as exc:
        raise DeclarationValidationError(str(exc)) from exc


def validate_mod_declaration(declaration: ModDeclaration) -> None:
    try:
        if (
            isinstance(declaration.schema_version, bool)
            or declaration.schema_version != 1
        ):
            raise ValueError("schema_version must be integer 1")

        validate_mod_id(declaration.mod_id)
        require_non_empty_string(declaration.mod_name, "mod_name", 128)
        require_non_empty_string(
            declaration.installed_version,
            "installed_version",
            128,
        )
        parse_version(declaration.installed_version)
        validate_release_channel(declaration.release_channel)
        validate_download_page(declaration.download_page)
    except DeclarationValidationError:
        raise
    except (TypeError, ValueError) as exc:
        raise DeclarationValidationError(str(exc)) from exc
