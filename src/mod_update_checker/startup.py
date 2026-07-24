# Demeterio: Mod Update Checker (script for The Sims 4)
# Do not copy, share or modify without my permission
# https://demeterio.tumblr.com
# https://discord.gg/mPyRPScgeS

"""Initialize local MUC services without performing network requests."""

from . import __version__
from .central_registry import central_registry_url
from .constants import REGISTRY_CHECK_INTERVAL_SECONDS
from .logger import MUCLog
from .runtime import get_runtime


def initialize() -> None:
    logger = MUCLog.logger()
    try:
        runtime = get_runtime()
        logger.info(
            "Demeterio: Mod Update Checker version {}".format(__version__)
        )
        logger.info(
            "Registered declarations at script startup: {}".format(
                runtime.registry.count()
            )
        )
        logger.info(
            "Central registry: {} | automatic interval {} hour(s)".format(
                central_registry_url(),
                REGISTRY_CHECK_INTERVAL_SECONDS // (60 * 60),
            )
        )
        logger.info("No network request is made during script import")
    except Exception:
        logger.exception("Unable to initialize the Mod Update Checker runtime")


initialize()
