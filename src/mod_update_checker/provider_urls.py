# Demeterio: Mod Update Checker (script for The Sims 4)
# Do not copy, share or modify without my permission
# https://demeterio.tumblr.com
# https://discord.gg/mPyRPScgeS

"""Build canonical update-page URLs from restricted identifiers."""

from typing import Optional
from urllib.parse import quote

from .constants import (
    PROVIDER_GITHUB_RELEASE,
    PROVIDER_MOD_THE_SIMS,
    PROVIDER_SIM_FILE_SHARE,
)
from .errors import DeclarationValidationError
from .models import DownloadPage
from .validation import validate_download_page, validate_release_tag


def build_download_page_url(
    page: DownloadPage,
    release_tag: Optional[str] = None,
) -> str:
    """Return a canonical HTTPS page URL after strict validation."""

    validate_download_page(page)

    if page.provider == PROVIDER_GITHUB_RELEASE:
        if release_tag is not None:
            normalized_tag = validate_release_tag(release_tag)
            return "https://github.com/{}/{}/releases/tag/{}".format(
                page.github_owner,
                page.github_repository,
                quote(normalized_tag, safe=""),
            )
        return "https://github.com/{}/{}/releases/latest".format(
            page.github_owner,
            page.github_repository,
        )

    if page.provider == PROVIDER_MOD_THE_SIMS:
        return "https://modthesims.info/d/{}".format(
            page.submission_id
        )

    if page.provider == PROVIDER_SIM_FILE_SHARE:
        return "https://simfileshare.net/folder/{}/".format(
            page.folder_id
        )

    raise DeclarationValidationError(
        "unsupported download-page provider"
    )
