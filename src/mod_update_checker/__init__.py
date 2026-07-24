# Demeterio: Mod Update Checker (script for The Sims 4)
# Date: 2022-07 / 2026-07
# Python 3.7.9
# Do not copy, share or modify without my permission
# https://demeterio.tumblr.com
# https://discord.gg/mPyRPScgeS

"""Core package for Demeterio: Mod Update Checker."""

__version__ = "1.0.2"


try:
    import sims4  # noqa: F401
except ImportError:
    pass
else:
    try:
        from . import ui_resources as _ui_resources  # noqa: F401
        from . import commands as _commands  # noqa: F401
        from . import lifecycle as _lifecycle  # noqa: F401
        from . import startup as _startup  # noqa: F401
    except Exception:
        try:
            from .logger import MUCLog

            MUCLog.exception("Unable to import Mod Update Checker game runtime modules")
        except Exception:
            pass
