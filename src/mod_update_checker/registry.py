# Demeterio: Mod Update Checker (script for The Sims 4)
# Do not copy, share or modify without my permission
# https://demeterio.tumblr.com
# https://discord.gg/mPyRPScgeS

"""In-memory registry of validated mods and their update status."""

from typing import Dict, Iterable, List, Optional

from .constants import (
    REGISTRY_PRESENCE_MISSING,
    STATUS_CHECK_ERROR,
    STATUS_CONFLICT,
    STATUS_NOT_CHECKED,
    STATUS_REGISTRY_MISSING,
    STATUS_UP_TO_DATE,
    STATUS_UPDATE_AVAILABLE,
)
from .errors import RegistryError
from .logger import MUCLog
from .models import ModDeclaration
from .tuning_adapter import build_mod_declaration_from_tuning
from .versioning import update_is_available


class RegisteredMod:
    """Mutable runtime state for one validated declaration."""

    __slots__ = (
        "declaration",
        "available_version",
        "release_tag",
        "checked_at",
        "registry_missing_since",
        "status",
        "error",
    )

    def __init__(self, declaration: ModDeclaration) -> None:
        self.declaration = declaration
        self.available_version = None  # type: Optional[str]
        self.release_tag = None  # type: Optional[str]
        self.checked_at = None  # type: Optional[str]
        self.registry_missing_since = None  # type: Optional[str]
        self.status = STATUS_NOT_CHECKED
        self.error = None  # type: Optional[str]

    @property
    def mod_id(self) -> str:
        return self.declaration.mod_id

    @property
    def mod_name(self) -> str:
        return self.declaration.mod_name

    @property
    def installed_version(self) -> str:
        return self.declaration.installed_version

    def apply_available(
        self,
        available_version: str,
        release_tag: str,
        checked_at: str,
    ) -> None:
        self.available_version = available_version
        self.release_tag = release_tag
        self.checked_at = checked_at
        self.registry_missing_since = None
        self.error = None
        if update_is_available(self.installed_version, available_version):
            self.status = STATUS_UPDATE_AVAILABLE
        else:
            self.status = STATUS_UP_TO_DATE

    def apply_registry_missing(
        self,
        missing_since: str,
        message: str,
    ) -> None:
        self.registry_missing_since = missing_since
        self.status = STATUS_REGISTRY_MISSING
        self.error = message

    def apply_error(self, message: str) -> None:
        self.status = STATUS_CHECK_ERROR
        self.error = message


class ModRegistry:
    """Register snippets safely and expose deterministic status snapshots."""

    __slots__ = ("_mods", "_conflicts")

    def __init__(self) -> None:
        self._mods = {}  # type: Dict[str, RegisteredMod]
        self._conflicts = set()  # type: set

    def register_tuning(self, tuning: object) -> RegisteredMod:
        declaration = build_mod_declaration_from_tuning(tuning)
        return self.register_declaration(declaration)

    def register_declaration(
        self,
        declaration: ModDeclaration,
    ) -> RegisteredMod:
        logger = MUCLog.logger()
        mod_id = declaration.mod_id

        if mod_id in self._conflicts:
            raise RegistryError(
                "mod_id is already blocked by a conflicting declaration: "
                "{}".format(mod_id)
            )

        existing = self._mods.get(mod_id)
        if existing is None:
            state = RegisteredMod(declaration)
            self._mods[mod_id] = state
            logger.info(
                "Registered Mod Update Checker mod: {} | {} | installed {}".format(
                    declaration.mod_name,
                    declaration.mod_id,
                    declaration.installed_version,
                )
            )
            return state

        if existing.declaration == declaration:
            logger.warning(
                "Ignored identical duplicate Mod Update Checker declaration: {}".format(mod_id)
            )
            return existing

        del self._mods[mod_id]
        self._conflicts.add(mod_id)
        logger.error(
            "Conflicting Mod Update Checker declarations rejected for mod_id: {}".format(mod_id)
        )
        raise RegistryError(
            "conflicting declarations use the same mod_id: {}".format(mod_id)
        )

    def get(self, mod_id: str) -> Optional[RegisteredMod]:
        return self._mods.get(mod_id)

    def contains(self, mod_id: str) -> bool:
        return mod_id in self._mods

    def values(self) -> List[RegisteredMod]:
        return sorted(
            self._mods.values(),
            key=lambda state: (state.mod_name.lower(), state.mod_id),
        )

    def mod_ids(self) -> Iterable[str]:
        return tuple(sorted(self._mods.keys()))

    def count(self) -> int:
        return len(self._mods)

    def conflict_ids(self) -> Iterable[str]:
        return tuple(sorted(self._conflicts))

    def apply_cache_entry(
        self,
        mod_id: str,
        entry: Optional[Dict[str, str]],
    ) -> None:
        if entry is None:
            return
        state = self._mods.get(mod_id)
        if state is None:
            return
        if entry.get("release_channel") != state.declaration.release_channel:
            MUCLog.logger().warning(
                "Ignored cached result for another release channel | {}".format(
                    mod_id
                )
            )
            return

        if (
            entry.get("available_version")
            and entry.get("release_tag")
            and entry.get("checked_at")
        ):
            state.apply_available(
                entry["available_version"],
                entry["release_tag"],
                entry["checked_at"],
            )

        if entry.get("registry_presence") == REGISTRY_PRESENCE_MISSING:
            state.apply_registry_missing(
                entry.get("missing_since", ""),
                "The mod was not listed in the last accepted central registry",
            )

    def detailed_log_text(self, settings) -> str:
        lines = ["REGISTERED MOD UPDATE CHECKER MODS", "==================="]
        states = self.values()
        if not states:
            lines.append("No valid mods are registered with Mod Update Checker")
        else:
            for state in states:
                lines.extend(
                    (
                        "",
                        "Name: {}".format(state.mod_name),
                        "Mod ID: {}".format(state.mod_id),
                        "Installed version: {}".format(state.installed_version),
                        "Release channel: {}".format(
                            state.declaration.release_channel
                        ),
                        "Available version: {}".format(
                            state.available_version
                            if state.available_version is not None
                            else "Not checked"
                        ),
                        "Release tag: {}".format(
                            state.release_tag
                            if state.release_tag is not None
                            else "Unknown"
                        ),
                        "Status: {}".format(state.status),
                        "Alerts: {}".format(
                            "ON"
                            if settings.alerts_enabled_for(state.mod_id)
                            else "OFF"
                        ),
                        "Last confirmed: {}".format(
                            state.checked_at
                            if state.checked_at is not None
                            else "Never"
                        ),
                    )
                )
                if state.registry_missing_since:
                    lines.append(
                        "Missing from registry since: {}".format(
                            state.registry_missing_since
                        )
                    )
                if state.error:
                    lines.append("Status detail: {}".format(state.error))

        if self._conflicts:
            lines.extend(("", "CONFLICTING MOD IDS"))
            for mod_id in sorted(self._conflicts):
                lines.append("- {} ({})".format(mod_id, STATUS_CONFLICT))

        return "\n".join(lines)
