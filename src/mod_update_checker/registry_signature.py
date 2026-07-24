# Demeterio: Mod Update Checker (script for The Sims 4)
# Do not copy, share or modify without my permission
# https://demeterio.tumblr.com
# https://discord.gg/mPyRPScgeS

"""Authenticate the central registry with RSA PKCS#1 v1.5 and SHA-256."""

import base64
import binascii
import hashlib
import hmac
import json
from typing import Any, Dict, List, Tuple

from .constants import (
    MAX_CENTRAL_REGISTRY_BYTES,
    REGISTRY_PUBLIC_KEY_EXPONENT,
    REGISTRY_PUBLIC_KEY_ID,
    REGISTRY_PUBLIC_KEY_MODULUS_HEX,
    REGISTRY_SIGNATURE_ALGORITHM,
    REGISTRY_SIGNATURE_SCHEMA,
)
from .errors import CentralRegistrySignatureError


_SHA256_DIGEST_INFO_PREFIX = bytes.fromhex(
    "3031300d060960864801650304020105000420"
)
_SIGNED_ENVELOPE_FIELDS = frozenset(
    (
        "signature_schema",
        "key_id",
        "algorithm",
        "payload",
        "signature",
    )
)


def _reject_duplicate_envelope_keys(
    pairs: List[Tuple[str, Any]],
) -> Dict[str, Any]:
    result = {}  # type: Dict[str, Any]
    for key, value in pairs:
        if key in result:
            raise CentralRegistrySignatureError(
                "Signed central registry contains duplicate key: {}".format(key)
            )
        result[key] = value
    return result


def _decode_base64(
    value: object,
    field_name: str,
    maximum_decoded_bytes: int,
) -> bytes:
    if not isinstance(value, str):
        raise CentralRegistrySignatureError(
            "{} must be a Base64 string".format(field_name)
        )
    if not value:
        raise CentralRegistrySignatureError(
            "{} must not be empty".format(field_name)
        )

    maximum_encoded_length = 4 * ((maximum_decoded_bytes + 2) // 3)
    if len(value) > maximum_encoded_length:
        raise CentralRegistrySignatureError(
            "{} exceeds the allowed size".format(field_name)
        )

    try:
        encoded = value.encode("ascii")
        decoded = base64.b64decode(encoded, validate=True)
    except (UnicodeEncodeError, binascii.Error, ValueError) as exc:
        raise CentralRegistrySignatureError(
            "{} is not valid Base64".format(field_name)
        ) from exc

    if len(decoded) > maximum_decoded_bytes:
        raise CentralRegistrySignatureError(
            "{} exceeds the allowed size".format(field_name)
        )
    if base64.b64encode(decoded) != encoded:
        raise CentralRegistrySignatureError(
            "{} is not canonical Base64".format(field_name)
        )
    return decoded


def _public_key() -> Tuple[int, int, int]:
    try:
        if (
            not isinstance(REGISTRY_PUBLIC_KEY_MODULUS_HEX, str)
            or not REGISTRY_PUBLIC_KEY_MODULUS_HEX
            or len(REGISTRY_PUBLIC_KEY_MODULUS_HEX) % 2 != 0
        ):
            raise ValueError("RSA modulus is invalid")
        modulus = int(REGISTRY_PUBLIC_KEY_MODULUS_HEX, 16)
    except (TypeError, ValueError) as exc:
        raise CentralRegistrySignatureError(
            "Embedded registry public key is invalid"
        ) from exc

    exponent = REGISTRY_PUBLIC_KEY_EXPONENT
    if (
        isinstance(exponent, bool)
        or not isinstance(exponent, int)
        or exponent < 3
        or exponent % 2 == 0
    ):
        raise CentralRegistrySignatureError(
            "Embedded registry public key is invalid"
        )
    if modulus <= 0 or modulus % 2 == 0 or modulus.bit_length() < 2048:
        raise CentralRegistrySignatureError(
            "Embedded registry public key is invalid"
        )

    key_size = (modulus.bit_length() + 7) // 8
    return modulus, exponent, key_size


def _verify_rs256(
    payload: bytes,
    signature: bytes,
) -> None:
    modulus, exponent, key_size = _public_key()
    if len(signature) != key_size:
        raise CentralRegistrySignatureError(
            "Central registry signature has an invalid length"
        )

    signature_integer = int.from_bytes(signature, "big")
    if signature_integer <= 0 or signature_integer >= modulus:
        raise CentralRegistrySignatureError(
            "Central registry signature is invalid"
        )

    encoded_integer = pow(signature_integer, exponent, modulus)
    encoded_message = encoded_integer.to_bytes(key_size, "big")
    digest_info = _SHA256_DIGEST_INFO_PREFIX + hashlib.sha256(payload).digest()
    padding_length = key_size - len(digest_info) - 3
    if padding_length < 8:
        raise CentralRegistrySignatureError(
            "Embedded registry public key is invalid"
        )

    expected = (
        b"\x00\x01"
        + (b"\xff" * padding_length)
        + b"\x00"
        + digest_info
    )
    if not hmac.compare_digest(encoded_message, expected):
        raise CentralRegistrySignatureError(
            "Central registry signature is invalid"
        )


def extract_verified_registry_payload(signed_document: bytes) -> bytes:
    """Return the inner registry bytes only after authenticating the envelope."""

    try:
        data = json.loads(
            signed_document.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_envelope_keys,
        )
    except CentralRegistrySignatureError:
        raise
    except (UnicodeDecodeError, TypeError, ValueError) as exc:
        raise CentralRegistrySignatureError(
            "Signed central registry is not valid UTF-8 JSON"
        ) from exc

    try:
        if not isinstance(data, dict):
            raise TypeError("Signed central registry root must be an object")
        if frozenset(data.keys()) != _SIGNED_ENVELOPE_FIELDS:
            raise ValueError("Signed central registry fields are invalid")
        if (
            isinstance(data["signature_schema"], bool)
            or data["signature_schema"] != REGISTRY_SIGNATURE_SCHEMA
        ):
            raise ValueError(
                "signature_schema must be integer {}".format(
                    REGISTRY_SIGNATURE_SCHEMA
                )
            )
        if data["key_id"] != REGISTRY_PUBLIC_KEY_ID:
            raise ValueError("Signed central registry key_id is not trusted")
        if data["algorithm"] != REGISTRY_SIGNATURE_ALGORITHM:
            raise ValueError(
                "Signed central registry algorithm must be {}".format(
                    REGISTRY_SIGNATURE_ALGORITHM
                )
            )

        payload = _decode_base64(
            data["payload"],
            "payload",
            MAX_CENTRAL_REGISTRY_BYTES,
        )
        _modulus, _exponent, key_size = _public_key()
        signature = _decode_base64(
            data["signature"],
            "signature",
            key_size,
        )
        _verify_rs256(payload, signature)
        return payload
    except CentralRegistrySignatureError:
        raise
    except (TypeError, ValueError) as exc:
        raise CentralRegistrySignatureError(str(exc)) from exc
