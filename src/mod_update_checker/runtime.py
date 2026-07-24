# Demeterio: Mod Update Checker (script for The Sims 4)
# Do not copy, share or modify without my permission
# https://demeterio.tumblr.com
# https://discord.gg/mPyRPScgeS

"""Single runtime container shared by tuning callbacks and commands."""

from typing import NamedTuple, Optional

from .cache import MUCCache
from .consent import MUCConsentService
from .logger import MUCLog
from .progressive_scheduler import MUCProgressiveScheduler, SchedulerSnapshot
from .registry import ModRegistry, RegisteredMod
from .settings import MUCSettings
from .update_report import MUCUpdateReport


class ManualCheckRequest(NamedTuple):
    started: bool
    consent_prompted: bool
    pending: int


class MUCRuntime:
    """Own settings, cache, registry, consent, and progressive scheduling."""

    __slots__ = (
        "settings",
        "cache",
        "registry",
        "consent",
        "scheduler",
        "_initialized",
    )

    def __init__(self) -> None:
        self.settings = MUCSettings()
        self.cache = MUCCache()
        self.registry = ModRegistry()
        self.consent = MUCConsentService(self.settings)
        self.scheduler = MUCProgressiveScheduler(self)
        self._initialized = False

    def initialize(self) -> None:
        if self._initialized is True:
            return
        logger = MUCLog.logger()
        self.settings.load()
        self.cache.load()
        try:
            MUCUpdateReport.ensure_initial_report()
        except Exception:
            logger.exception(
                "Unable to create the initial Mod Update Checker update report"
            )
        self._initialized = True
        logger.info("Mod Update Checker runtime initialized")

    def register_tuning(self, tuning: object) -> RegisteredMod:
        self.initialize()
        state = self.registry.register_tuning(tuning)
        self.registry.apply_cache_entry(
            state.mod_id,
            self.cache.get(state.mod_id),
        )
        return state

    def on_zone_ready(self) -> None:
        """Ask due questions, then resume central-registry checks after loading."""

        self.initialize()
        self.scheduler.stop(clear_force=False)

        def _after_consent(network_enabled: bool) -> None:
            if network_enabled:
                self.scheduler.start(force=False, restart=True)
            else:
                MUCLog.logger().info(
                    "Automatic checks remain disabled or temporarily postponed"
                )

        self.consent.request_if_needed(on_complete=_after_consent)

    def request_manual_check(self) -> ManualCheckRequest:
        """Start a forced central-registry check after resolving network consent."""

        self.initialize()
        consent_needed = self.settings.network_access_allowed() is not True
        started = [False]

        def _after_consent(network_enabled: bool) -> None:
            if network_enabled:
                started[0] = self.scheduler.start(force=True)

        completed = self.consent.request_if_needed(
            on_complete=_after_consent,
            force_network_prompt=consent_needed,
        )
        prompted = consent_needed and completed is False
        return ManualCheckRequest(
            started[0],
            prompted,
            self.scheduler.pending_count(),
        )

    def open_settings(self) -> bool:
        """Open preferences and immediately apply the resulting network state."""

        self.initialize()
        logger = MUCLog.logger()

        def _after_settings(network_enabled: bool) -> None:
            if network_enabled:
                started = self.scheduler.start(force=False)
                if started:
                    logger.info(
                        "Automatic central registry checks resumed after settings update"
                    )
                else:
                    logger.info(
                        "Automatic central registry checks are enabled but not currently due"
                    )
                return

            self.scheduler.stop()
            logger.info(
                "Automatic central registry checks disabled or temporarily postponed"
            )

        return self.consent.open_settings(on_complete=_after_settings)

    def scheduler_snapshot(self) -> SchedulerSnapshot:
        return self.scheduler.snapshot()


_runtime = None  # type: Optional[MUCRuntime]


def get_runtime() -> MUCRuntime:
    global _runtime
    if _runtime is None:
        _runtime = MUCRuntime()
        _runtime.initialize()
    return _runtime