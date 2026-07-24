# Demeterio: Mod Update Checker (script for The Sims 4)
# Do not copy, share or modify without my permission
# https://demeterio.tumblr.com
# https://discord.gg/mPyRPScgeS

"""Marker tuning loaded from Demeterio_Mod_Update_Checker.package."""

from typing import ClassVar, TYPE_CHECKING

from .constants import MUC_UI_PACKAGE_TOKEN, MUC_UI_PACKAGE_VERSION
from .logger import MUCLog


if TYPE_CHECKING:
    class MUCUIResourceMarker:
        """Static typing view of the runtime EA tuning class."""

        package_version: ClassVar[int]
        package_token: ClassVar[str]
        _available: ClassVar[bool]

        @classmethod
        def _tuning_loaded_callback(cls) -> None:
            ...

        @classmethod
        def is_available(cls) -> bool:
            ...
else:
    try:
        import services
        from sims4.resources import Types
        from sims4.tuning.instances import HashedTunedInstanceMetaclass
        from sims4.tuning.tunable import Tunable
    except ImportError:
        class MUCUIResourceMarker:
            """Outside-game placeholder used by unit tests."""

            _available = False

            @classmethod
            def is_available(cls) -> bool:
                return cls._available is True
    else:
        class MUCUIResourceMarker(
            metaclass=HashedTunedInstanceMetaclass,
            manager=services.get_instance_manager(Types.SNIPPET),
        ):
            """Confirm that the matching package and STBL resources are installed."""

            INSTANCE_TUNABLES = {
                "package_version": Tunable(
                    tunable_type=int,
                    default=0,
                    description="Internal Mod Update Checker UI package format version.",
                ),
                "package_token": Tunable(
                    tunable_type=str,
                    default=None,
                    allow_empty=False,
                    description="Internal token tying this package to the script.",
                ),
            }

            _available = False

            @classmethod
            def _tuning_loaded_callback(cls) -> None:
                """Publish the concrete XML tuning result on the shared base class."""

                logger = MUCLog.logger()

                try:
                    package_version = getattr(cls, "package_version", None)
                    package_token = getattr(cls, "package_token", None)
                    available = (
                        package_version == MUC_UI_PACKAGE_VERSION
                        and package_token == MUC_UI_PACKAGE_TOKEN
                    )

                    # EA invokes this callback on the concrete tuning subclass
                    # generated from XML. Consent and notifications query the
                    # shared Python base class, so publish the result explicitly.
                    MUCUIResourceMarker._available = available

                    if available:
                        logger.info(
                            "Mod Update Checker UI package detected | version {} | token {}".format(
                                package_version,
                                package_token,
                            )
                        )
                    else:
                        logger.error(
                            "Mod Update Checker UI package marker is incompatible | version {} | token {}"
                            .format(
                                package_version,
                                package_token,
                            )
                        )
                except Exception:
                    MUCUIResourceMarker._available = False
                    logger.exception("Unable to validate the Mod Update Checker UI package marker")

            @classmethod
            def is_available(cls) -> bool:
                return MUCUIResourceMarker._available is True
