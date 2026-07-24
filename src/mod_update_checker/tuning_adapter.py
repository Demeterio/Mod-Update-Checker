# Demeterio: Mod Update Checker (script for The Sims 4)
# Do not copy, share or modify without my permission
# https://demeterio.tumblr.com
# https://discord.gg/mPyRPScgeS

"""Convert flat Sims 4 tuning fields into validated core data models."""

from typing import Optional

from .errors import DeclarationValidationError
from .models import DownloadPage, ModDeclaration
from .validation import validate_mod_declaration


def _required_string_field(tuning: object, field_name: str) -> str:
    value = getattr(tuning, field_name, None)
    if not isinstance(value, str):
        raise DeclarationValidationError(
            "{} must be a string".format(field_name)
        )
    return value


def _optional_string_field(
    tuning: object,
    field_name: str,
) -> Optional[str]:
    value = getattr(tuning, field_name, None)
    if value is None:
        return None
    if not isinstance(value, str):
        raise DeclarationValidationError(
            "{} must be a string or null".format(field_name)
        )
    return value


def _required_integer_field(tuning: object, field_name: str) -> int:
    value = getattr(tuning, field_name, None)
    if isinstance(value, bool) or not isinstance(value, int):
        raise DeclarationValidationError(
            "{} must be an integer".format(field_name)
        )
    return value


def _optional_identifier_field(
    tuning: object,
    field_name: str,
) -> Optional[int]:
    """Convert the tuning default zero to None and reject non-integers."""

    value = getattr(tuning, field_name, 0)
    if isinstance(value, bool) or not isinstance(value, int):
        raise DeclarationValidationError(
            "{} must be an integer".format(field_name)
        )
    if value == 0:
        return None
    return value


def build_mod_declaration_from_tuning(
    tuning: object,
) -> ModDeclaration:
    """Build and validate one declaration from a tuned snippet class."""

    schema_version = _required_integer_field(tuning, "schema_version")
    mod_id = _required_string_field(tuning, "mod_id")
    mod_name = _required_string_field(tuning, "mod_name")
    installed_version = _required_string_field(tuning, "installed_version")
    release_channel = _required_string_field(tuning, "release_channel")
    provider = _required_string_field(tuning, "download_page_provider")
    github_owner = _optional_string_field(tuning, "github_download_owner")
    github_repository = _optional_string_field(
        tuning,
        "github_download_repository",
    )
    submission_id = _optional_identifier_field(
        tuning,
        "mod_the_sims_submission_id",
    )
    folder_id = _optional_identifier_field(
        tuning,
        "sim_file_share_folder_id",
    )

    # Keep every tuned field until validation. Provider-specific values must not
    # be discarded here, otherwise forbidden XML fields could be silently
    # accepted instead of producing a clear declaration error.
    page = DownloadPage(
        provider=provider,
        github_owner=github_owner,
        github_repository=github_repository,
        submission_id=submission_id,
        folder_id=folder_id,
    )

    declaration = ModDeclaration(
        schema_version=schema_version,
        mod_id=mod_id,
        mod_name=mod_name,
        installed_version=installed_version,
        download_page=page,
        release_channel=release_channel,
    )
    validate_mod_declaration(declaration)
    return declaration
