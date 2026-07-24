# Demeterio: Mod Update Checker (script for The Sims 4)
# Do not copy, share or modify without my permission
# https://demeterio.tumblr.com
# https://discord.gg/mPyRPScgeS

"""Custom exceptions for expected checker failures."""


class ModUpdateCheckerError(Exception):
    """Base class for expected Mod Update Checker errors."""


class DeclarationValidationError(ModUpdateCheckerError):
    """Raised when package tuning contains invalid or forbidden values."""


class CentralRegistryValidationError(ModUpdateCheckerError):
    """Raised when the central registry document is malformed or inconsistent."""


class CentralRegistrySignatureError(CentralRegistryValidationError):
    """Raised when the central registry signature or envelope is invalid."""


class VersionValidationError(ModUpdateCheckerError, ValueError):
    """Raised when a version does not follow the supported SemVer format.

    It is both an expected MUC error and a value-validation error so callers
    that convert malformed configuration or cache values into their own typed
    validation errors can catch it consistently.
    """


class NetworkSecurityError(ModUpdateCheckerError):
    """Raised when a request violates the fixed network security policy."""


class NetworkRequestError(ModUpdateCheckerError):
    """Raised when an allowed central-registry request fails."""


class RegistryRateLimitError(NetworkRequestError):
    """Raised when the central registry host requires requests to pause."""

    def __init__(self, message: str, retry_at: str = "") -> None:
        super().__init__(message)
        self.retry_at = retry_at


class PersistenceError(ModUpdateCheckerError):
    """Raised when a DMUC settings or cache file is invalid or cannot be stored."""


class RegistryError(ModUpdateCheckerError):
    """Raised when a declaration cannot be registered safely."""


class NotificationError(ModUpdateCheckerError):
    """Raised when a requested in-game dialog cannot be created safely."""


class ExternalOpenError(ModUpdateCheckerError):
    """Raised when a fixed MUC report or log location cannot be opened."""
