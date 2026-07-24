# Demeterio: Mod Update Checker (script for The Sims 4)
# Do not copy, share or modify without my permission
# https://demeterio.tumblr.com
# https://discord.gg/mPyRPScgeS

"""Small SemVer parser compatible with Python 3.7 and no dependencies."""

import re
from typing import NamedTuple, Tuple

from .errors import VersionValidationError

_SEMVER_PATTERN = re.compile(
    r"^(0|[1-9][0-9]*)\."
    r"(0|[1-9][0-9]*)\."
    r"(0|[1-9][0-9]*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)


class SemanticVersion(NamedTuple):
    major: int
    minor: int
    patch: int
    prerelease: Tuple[str, ...]


def parse_version(value: str) -> SemanticVersion:
    if not isinstance(value, str):
        raise VersionValidationError("version must be a string")
    if value != value.strip():
        raise VersionValidationError(
            "version must not contain leading or trailing whitespace"
        )

    match = _SEMVER_PATTERN.fullmatch(value)
    if match is None:
        raise VersionValidationError(
            "version must follow MAJOR.MINOR.PATCH SemVer syntax"
        )

    prerelease_text = match.group(4)
    prerelease = (
        tuple(prerelease_text.split("."))
        if prerelease_text
        else tuple()
    )
    for identifier in prerelease:
        if (
            identifier.isdigit()
            and len(identifier) > 1
            and identifier.startswith("0")
        ):
            raise VersionValidationError(
                "numeric prerelease identifiers must not contain leading zeroes"
            )

    return SemanticVersion(
        int(match.group(1)),
        int(match.group(2)),
        int(match.group(3)),
        prerelease,
    )


def _compare_prerelease(
    left: Tuple[str, ...],
    right: Tuple[str, ...],
) -> int:
    if not left and not right:
        return 0
    if not left:
        return 1
    if not right:
        return -1

    for left_part, right_part in zip(left, right):
        if left_part == right_part:
            continue

        left_numeric = left_part.isdigit()
        right_numeric = right_part.isdigit()
        if left_numeric and right_numeric:
            return 1 if int(left_part) > int(right_part) else -1
        if left_numeric != right_numeric:
            return -1 if left_numeric else 1
        return 1 if left_part > right_part else -1

    if len(left) == len(right):
        return 0
    return 1 if len(left) > len(right) else -1


def compare_versions(left: str, right: str) -> int:
    """Return -1, 0, or 1 when left is older, equal, or newer."""

    left_version = parse_version(left)
    right_version = parse_version(right)

    left_core = left_version[:3]
    right_core = right_version[:3]
    if left_core != right_core:
        return 1 if left_core > right_core else -1

    return _compare_prerelease(
        left_version.prerelease,
        right_version.prerelease,
    )


def update_is_available(
    installed: str,
    available: str,
) -> bool:
    return compare_versions(installed, available) < 0
