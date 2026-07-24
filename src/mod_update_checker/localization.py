# Demeterio: Mod Update Checker (script for The Sims 4)
# Do not copy, share or modify without my permission
# https://demeterio.tumblr.com
# https://discord.gg/mPyRPScgeS

"""Small localization helpers backed by the MUC package STBL resources."""

from typing import Any


def localized_factory(string_id: int, *tokens: object) -> Any:
    """Return a dialog-compatible callable for one STBL string and its tokens."""

    from sims4.localization import _create_localized_string

    return lambda *_, **__: _create_localized_string(string_id, *tokens)
