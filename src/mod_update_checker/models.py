# Demeterio: Mod Update Checker (script for The Sims 4)
# Do not copy, share or modify without my permission
# https://demeterio.tumblr.com
# https://discord.gg/mPyRPScgeS

"""Immutable data models used after tuning and registry validation."""

from typing import Dict, NamedTuple, Optional, Tuple


class DownloadPage(NamedTuple):
    """Canonical update page reconstructed from validated flat tuning fields."""

    provider: str
    github_owner: Optional[str] = None
    github_repository: Optional[str] = None
    submission_id: Optional[int] = None
    folder_id: Optional[int] = None


class ModDeclaration(NamedTuple):
    """Validated values read from an optional creator integration snippet."""

    schema_version: int
    mod_id: str
    mod_name: str
    installed_version: str
    download_page: DownloadPage
    release_channel: str = "stable"


class CentralRegistryEntry(NamedTuple):
    """One validated available-version entry from the central registry."""

    mod_id: str
    release_channel: str
    version: str
    release_tag: str
    checked_at: str


class CentralRegistryDocument(NamedTuple):
    """Validated central registry document keyed by mod ID and release channel."""

    schema: int
    generated_at: str
    entries: Dict[Tuple[str, str], CentralRegistryEntry]
