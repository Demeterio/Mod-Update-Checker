# Demeterio: Mod Update Checker (script for The Sims 4)
# Do not copy, share or modify without my permission
# https://demeterio.tumblr.com
# https://discord.gg/mPyRPScgeS

"""Tuning classes used by optional creator integration packages."""

from typing import ClassVar, Optional, TYPE_CHECKING


if TYPE_CHECKING:
    class ModUpdateCheckerDeclaration:
        """Static typing view of the runtime EA tuning class."""

        schema_version: ClassVar[int]
        mod_id: ClassVar[str]
        mod_name: ClassVar[str]
        installed_version: ClassVar[str]
        release_channel: ClassVar[str]
        download_page_provider: ClassVar[str]
        github_download_owner: ClassVar[Optional[str]]
        github_download_repository: ClassVar[Optional[str]]
        mod_the_sims_submission_id: ClassVar[int]
        sim_file_share_folder_id: ClassVar[int]

        @classmethod
        def _tuning_loaded_callback(cls) -> None:
            ...
else:
    import services
    from sims4.resources import Types
    from sims4.tuning.instances import HashedTunedInstanceMetaclass
    from sims4.tuning.tunable import Tunable


    class ModUpdateCheckerDeclaration(
        metaclass=HashedTunedInstanceMetaclass,
        manager=services.get_instance_manager(Types.SNIPPET),
    ):
        """One optional update-check declaration supplied by a mod creator."""

        INSTANCE_TUNABLES = {
            "schema_version": Tunable(
                tunable_type=int,
                default=1,
                description="Declaration schema. Version 1 is currently required.",
            ),
            "mod_id": Tunable(
                tunable_type=str,
                default=None,
                allow_empty=False,
                description=(
                    "Permanent identifier using creator.mod_name.FNV64. The first "
                    "two segments use lowercase letters, digits, underscores, or "
                    "hyphens. The final segment is exactly 16 uppercase hexadecimal "
                    "characters generated once with Sims 4 Studio."
                ),
            ),
            "mod_name": Tunable(
                tunable_type=str,
                default=None,
                allow_empty=False,
                description=(
                    "Player-facing mod name used in reports and notifications."
                ),
            ),
            "installed_version": Tunable(
                tunable_type=str,
                default=None,
                allow_empty=False,
                description="Installed SemVer version, for example 1.3.1.",
            ),
            "release_channel": Tunable(
                tunable_type=str,
                default="stable",
                allow_empty=False,
                description=(
                    "Central-registry channel to compare: stable or prerelease."
                ),
            ),
            "download_page_provider": Tunable(
                tunable_type=str,
                default="GITHUB_RELEASE",
                allow_empty=False,
                description=(
                    "Player-facing page provider: GITHUB_RELEASE, MOD_THE_SIMS, "
                    "or SIM_FILE_SHARE."
                ),
            ),
            "github_download_owner": Tunable(
                tunable_type=str,
                default=None,
                allow_empty=False,
                description=(
                    "Required only for GITHUB_RELEASE: account or organization "
                    "whose release page should be opened."
                ),
            ),
            "github_download_repository": Tunable(
                tunable_type=str,
                default=None,
                allow_empty=False,
                description=(
                    "Required only for GITHUB_RELEASE: repository whose release "
                    "page should be opened."
                ),
            ),
            "mod_the_sims_submission_id": Tunable(
                tunable_type=int,
                default=0,
                description=(
                    "Required only when download_page_provider is MOD_THE_SIMS."
                ),
            ),
            "sim_file_share_folder_id": Tunable(
                tunable_type=int,
                default=0,
                description=(
                    "Required only when download_page_provider is SIM_FILE_SHARE."
                ),
            ),
        }

        @classmethod
        def _tuning_loaded_callback(cls) -> None:
            """Register this declaration without allowing errors to reach EA."""

            try:
                from .runtime import get_runtime

                get_runtime().register_tuning(cls)
            except Exception:
                try:
                    from .logger import MUCLog

                    MUCLog.exception(
                        "Invalid Mod Update Checker tuning declaration skipped: {}".format(
                            getattr(cls, "__name__", "<unknown>")
                        )
                    )
                except Exception:
                    pass
