# Demeterio: Mod Update Checker (script for The Sims 4)
# Do not copy, share or modify without my permission
# https://demeterio.tumblr.com
# https://discord.gg/mPyRPScgeS

"""Minimal method-injection helper used only for game lifecycle hooks."""

from functools import wraps


def inject(target, method_name: str):
    def _decorator(replacement):
        original = getattr(target, method_name)

        @wraps(original)
        def _wrapped(*args, **kwargs):
            return replacement(original, *args, **kwargs)

        setattr(target, method_name, _wrapped)
        return _wrapped

    return _decorator
