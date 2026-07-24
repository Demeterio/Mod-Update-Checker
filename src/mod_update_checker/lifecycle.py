# Demeterio: Mod Update Checker (script for The Sims 4)
# Do not copy, share or modify without my permission
# https://demeterio.tumblr.com
# https://discord.gg/mPyRPScgeS

"""Start consent and progressive checks after a playable zone is ready."""

from zone import Zone

from .injection import inject
from .logger import MUCLog
from .runtime import get_runtime


@inject(Zone, "on_loading_screen_animation_finished")
def _muc_after_loading_screen(original, self, *args, **kwargs) -> None:
    original(self, *args, **kwargs)
    logger = MUCLog.logger()
    logger.info("Zone loading screen finished; evaluating Mod Update Checker consent and due checks")
    try:
        get_runtime().on_zone_ready()
    except Exception:
        logger.exception("Unable to start Mod Update Checker after the loading screen")
