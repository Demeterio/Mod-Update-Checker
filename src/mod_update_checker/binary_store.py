# Demeterio: Mod Update Checker (script for The Sims 4)
# Do not copy, share or modify without my permission
# https://demeterio.tumblr.com
# https://discord.gg/mPyRPScgeS

"""Validated binary container for DMUC settings and cache data.

The payload is canonical JSON compressed with zlib. A fixed header, storage
kind, size fields, and SHA-256 digest reject corruption and casual edits.
This is deliberately not described as encryption: a determined reverse
engineer could still reproduce the format.
"""

import hashlib
import json
import os
import struct
import zlib
from typing import Any, Dict

from .constants import (
    MUC_STORAGE_FORMAT_VERSION,
    MUC_STORAGE_MAGIC,
    MUC_STORAGE_MAX_FILE_BYTES,
    MUC_STORAGE_MAX_UNCOMPRESSED_BYTES,
)
from .errors import PersistenceError
from .paths import MUCPaths

_HEADER = struct.Struct(">BBII32s")


def encode_dmuc_data(data: Dict[str, Any], storage_kind: int) -> bytes:
    """Serialize a dictionary into the validated binary DMUC container."""
    if not isinstance(data, dict):
        raise PersistenceError("DMUC storage root must be a dictionary")
    if isinstance(storage_kind, bool) or not isinstance(storage_kind, int):
        raise PersistenceError("DMUC storage kind must be an integer")
    if not 0 < storage_kind <= 255:
        raise PersistenceError("DMUC storage kind is outside the supported range")

    try:
        payload = json.dumps(
            data,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise PersistenceError("DMUC data contains unsupported values") from exc

    if len(payload) > MUC_STORAGE_MAX_UNCOMPRESSED_BYTES:
        raise PersistenceError("DMUC data exceeds the uncompressed size limit")

    compressed = zlib.compress(payload, 9)
    digest = hashlib.sha256(payload).digest()
    header = _HEADER.pack(
        MUC_STORAGE_FORMAT_VERSION,
        storage_kind,
        len(payload),
        len(compressed),
        digest,
    )
    result = MUC_STORAGE_MAGIC + header + compressed

    if len(result) > MUC_STORAGE_MAX_FILE_BYTES:
        raise PersistenceError("DMUC file exceeds the stored size limit")
    return result


def _decompress_limited(compressed: bytes) -> bytes:
    """Decompress one zlib stream without allowing unbounded output."""
    maximum = MUC_STORAGE_MAX_UNCOMPRESSED_BYTES
    try:
        decompressor = zlib.decompressobj()
        payload = decompressor.decompress(compressed, maximum + 1)
        if len(payload) > maximum or decompressor.unconsumed_tail:
            raise PersistenceError(
                "DMUC file exceeds the uncompressed size limit"
            )

        remaining_capacity = maximum + 1 - len(payload)
        payload += decompressor.flush(remaining_capacity)
    except zlib.error as exc:
        raise PersistenceError("DMUC file compressed data is invalid") from exc

    if len(payload) > maximum:
        raise PersistenceError("DMUC file exceeds the uncompressed size limit")
    if decompressor.eof is not True:
        raise PersistenceError("DMUC file compressed data is incomplete")
    if decompressor.unused_data:
        raise PersistenceError(
            "DMUC file contains trailing compressed data"
        )
    return payload


def decode_dmuc_data(blob: bytes, expected_storage_kind: int) -> Dict[str, Any]:
    """Validate and decode one binary DMUC settings or cache file."""
    if not isinstance(blob, bytes):
        raise PersistenceError("DMUC file content must be bytes")
    if not blob:
        raise PersistenceError("DMUC file is empty")
    if len(blob) > MUC_STORAGE_MAX_FILE_BYTES:
        raise PersistenceError("DMUC file exceeds the stored size limit")
    if not blob.startswith(MUC_STORAGE_MAGIC):
        raise PersistenceError("DMUC file signature is invalid")

    header_start = len(MUC_STORAGE_MAGIC)
    header_end = header_start + _HEADER.size
    if len(blob) < header_end:
        raise PersistenceError("DMUC file header is incomplete")

    version, storage_kind, raw_size, compressed_size, expected_digest = (
        _HEADER.unpack(blob[header_start:header_end])
    )

    if version != MUC_STORAGE_FORMAT_VERSION:
        raise PersistenceError("DMUC file format version is unsupported")
    if storage_kind != expected_storage_kind:
        raise PersistenceError("DMUC file kind does not match the requested data")
    if raw_size > MUC_STORAGE_MAX_UNCOMPRESSED_BYTES:
        raise PersistenceError(
            "DMUC file declares an excessive uncompressed size"
        )

    compressed = blob[header_end:]
    if len(compressed) != compressed_size:
        raise PersistenceError(
            "DMUC file compressed-size metadata is inconsistent"
        )

    payload = _decompress_limited(compressed)

    if len(payload) != raw_size:
        raise PersistenceError(
            "DMUC file uncompressed-size metadata is inconsistent"
        )
    if hashlib.sha256(payload).digest() != expected_digest:
        raise PersistenceError("DMUC file integrity verification failed")

    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, TypeError, ValueError) as exc:
        raise PersistenceError("DMUC file payload is invalid") from exc

    if not isinstance(value, dict):
        raise PersistenceError("DMUC file root must be an object")
    return value


def read_dmuc_file(path: str, expected_storage_kind: int) -> Dict[str, Any]:
    """Read and decode one DMUC file from disk."""
    try:
        with open(path, "rb") as stream:
            blob = stream.read(MUC_STORAGE_MAX_FILE_BYTES + 1)
    except OSError as exc:
        raise PersistenceError(
            "Unable to read DMUC file: {}".format(
                MUCPaths.privacy_safe_path(path)
            )
        ) from exc
    return decode_dmuc_data(blob, expected_storage_kind)


def write_dmuc_file(path: str, data: Dict[str, Any], storage_kind: int) -> None:
    """Atomically encode and replace one DMUC file."""
    blob = encode_dmuc_data(data, storage_kind)
    directory = os.path.dirname(path)
    temporary_path = path + ".tmp"

    try:
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(temporary_path, "wb") as stream:
            stream.write(blob)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    except OSError as exc:
        try:
            if os.path.exists(temporary_path):
                os.remove(temporary_path)
        except OSError:
            pass
        raise PersistenceError(
            "Unable to write DMUC file: {}".format(
                MUCPaths.privacy_safe_path(path)
            )
        ) from exc
