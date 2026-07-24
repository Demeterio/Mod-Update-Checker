# Demeterio: Mod Update Checker (script for The Sims 4)
# Do not copy, share or modify without my permission
# https://demeterio.tumblr.com
# https://discord.gg/mPyRPScgeS

"""Real-time scheduler for one central-registry request per check cycle."""

import traceback
from queue import Empty, Queue
from threading import Thread
from typing import NamedTuple, Optional

from .cache import utc_now, utc_text
from .constants import AUTO_CHECK_INITIAL_DELAY_SECONDS, AUTO_CHECK_POLL_SECONDS
from .logger import MUCLog
from .update_service import (
    CheckSummary,
    RegistryNetworkOutcome,
    UpdateService,
)


class SchedulerSnapshot(NamedTuple):
    running: bool
    pending: int
    checked: int
    updates: int
    errors: int
    notifications: int
    missing: int


class MUCProgressiveScheduler:
    """Keep network work off-thread and all game/UI changes on the game thread."""

    __slots__ = (
        "_runtime",
        "_service",
        "_alarm_handle",
        "_worker",
        "_worker_generation",
        "_results",
        "_running",
        "_generation",
        "_force",
        "_checked",
        "_updates",
        "_errors",
        "_notifications",
        "_missing",
        "__weakref__",
    )

    def __init__(self, runtime) -> None:
        self._runtime = runtime
        self._service = UpdateService(
            runtime.registry,
            runtime.settings,
            runtime.cache,
        )
        self._alarm_handle = None
        self._worker = None  # type: Optional[Thread]
        self._worker_generation = None  # type: Optional[int]
        self._results = Queue()
        self._running = False
        self._generation = 0
        self._force = False
        self._checked = 0
        self._updates = 0
        self._errors = 0
        self._notifications = 0
        self._missing = 0

    def _reset_counters(self) -> None:
        self._checked = 0
        self._updates = 0
        self._errors = 0
        self._notifications = 0
        self._missing = 0

    def _cancel_alarm(self) -> None:
        if self._alarm_handle is None:
            return
        try:
            import alarms

            alarms.cancel_alarm(self._alarm_handle)
        except Exception:
            MUCLog.logger().exception("Unable to cancel the Mod Update Checker registry alarm")
        self._alarm_handle = None

    def _schedule(self, seconds: int, callback) -> bool:
        try:
            import alarms
            from clock import interval_in_real_seconds

            self._cancel_alarm()
            span = interval_in_real_seconds(max(1, int(seconds)))
            self._alarm_handle = alarms.add_alarm_real_time(
                self,
                span,
                callback,
                repeating=False,
                use_sleep_time=True,
                cross_zone=False,
            )
            if self._alarm_handle is None:
                raise RuntimeError("add_alarm_real_time returned no alarm handle")
            return True
        except Exception:
            self._alarm_handle = None
            self._running = False
            MUCLog.logger().exception("Unable to schedule the Mod Update Checker registry alarm")
            return False

    def pending_count(self) -> int:
        if self._running:
            return 1
        return 1 if self._service.is_due(force=self._force) else 0

    def snapshot(self) -> SchedulerSnapshot:
        return SchedulerSnapshot(
            self._running,
            self.pending_count(),
            self._checked,
            self._updates,
            self._errors,
            self._notifications,
            self._missing,
        )

    def start(self, force: bool = False, restart: bool = False) -> bool:
        logger = MUCLog.logger()
        if self._runtime.settings.network_checks_enabled is not True:
            logger.info("Central registry check not started: network consent is disabled")
            return False

        if restart:
            self.stop()
        if self._running:
            logger.info("Central registry checker is already running")
            return True

        self._force = force
        if self._service.is_due(force=force) is not True:
            logger.info("Central registry check is not currently due")
            return False

        self._reset_counters()
        self._running = True
        self._generation += 1
        if self._schedule(AUTO_CHECK_INITIAL_DELAY_SECONDS, self._tick) is not True:
            return False
        logger.info("Central registry checker scheduled")
        return True

    def stop(self, clear_force: bool = True) -> None:
        self._generation += 1
        self._running = False
        self._cancel_alarm()
        if clear_force:
            self._force = False

    def _worker_run(self, generation: int, started_at) -> None:
        outcome = self._service.fetch_registry(started_at)
        self._results.put((generation, outcome))

    def _tick(self, _alarm_handle=None) -> None:
        self._alarm_handle = None
        if self._running is not True:
            return

        # A worker from a previous zone may still be alive, or may already have
        # queued its result. Consume that result before creating another worker.
        if self._worker is not None:
            self._schedule(AUTO_CHECK_POLL_SECONDS, self._poll)
            return

        started_at = utc_now()
        self._service.begin_check(started_at)
        generation = self._generation
        try:
            worker = Thread(
                target=self._worker_run,
                args=(generation, started_at),
                name="DemeterioMUCCentralRegistry",
                daemon=True,
            )
            self._worker = worker
            self._worker_generation = generation
            worker.start()
        except Exception as exc:
            self._worker = None
            self._worker_generation = None
            outcome = RegistryNetworkOutcome(
                None,
                exc,
                traceback.format_exc(),
                utc_text(started_at),
                utc_text(utc_now()),
            )
            summary = self._service.apply_outcome(outcome)
            self._checked = summary.checked
            self._updates = summary.updates
            self._errors = summary.errors
            self._notifications = summary.notifications
            self._missing = summary.missing
            self._running = False
            self._force = False
            MUCLog.logger().exception(
                "Unable to start the central registry network worker"
            )
            return
        self._schedule(AUTO_CHECK_POLL_SECONDS, self._poll)

    def _poll(self, _alarm_handle=None) -> None:
        self._alarm_handle = None
        if self._running is not True:
            return
        try:
            generation, outcome = self._results.get_nowait()
        except Empty:
            self._schedule(AUTO_CHECK_POLL_SECONDS, self._poll)
            return

        if generation != self._generation:
            if generation == self._worker_generation:
                self._worker = None
                self._worker_generation = None
            MUCLog.logger().info(
                "Discarded stale central registry result after a runtime restart"
            )
            if self._running:
                callback = self._tick if self._worker is None else self._poll
                self._schedule(AUTO_CHECK_POLL_SECONDS, callback)
            return

        self._worker = None
        self._worker_generation = None
        try:
            summary = self._service.apply_outcome(outcome)
        except Exception:
            summary = CheckSummary(0, 0, 1, 0, 0)
            MUCLog.logger().exception(
                "Unable to apply the central registry result"
            )
        self._checked = summary.checked
        self._updates = summary.updates
        self._errors = summary.errors
        self._notifications = summary.notifications
        self._missing = summary.missing
        self._running = False
        self._force = False
