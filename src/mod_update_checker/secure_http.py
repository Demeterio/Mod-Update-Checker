# Demeterio: Mod Update Checker (script for The Sims 4)
# Do not copy, share or modify without my permission
# https://demeterio.tumblr.com
# https://discord.gg/mPyRPScgeS

"""Perform one bounded HTTP GET to the fixed central registry host."""

import socket
from typing import Dict, NamedTuple, Optional, Tuple
from urllib.parse import urlparse

from .constants import ALLOWED_NETWORK_HOSTS
from .errors import NetworkRequestError, NetworkSecurityError


_MAX_STATUS_LINE_BYTES = 4096
_MAX_HEADER_LINE_BYTES = 8192
_MAX_HEADER_BYTES = 65536
_MAX_HEADER_LINES = 100
_MAX_CHUNK_LINE_BYTES = 128


class SecureHTTPResponse(NamedTuple):
    status: int
    reason: str
    headers: Dict[str, str]
    body: bytes


def _readline(stream, limit: int, description: str) -> bytes:
    line = stream.readline(limit + 1)
    if len(line) > limit:
        raise NetworkRequestError(
            "Central registry {} is too long".format(description)
        )
    if not line:
        raise NetworkRequestError(
            "Central registry response ended before {}".format(description)
        )
    return line


def _read_exact(stream, size: int, description: str) -> bytes:
    remaining = size
    chunks = []
    while remaining > 0:
        block = stream.read(remaining)
        if not block:
            raise NetworkRequestError(
                "Central registry response ended during {}".format(description)
            )
        chunks.append(block)
        remaining -= len(block)
    return b"".join(chunks)


def _parse_status_line(line: bytes) -> Tuple[int, str]:
    try:
        text = line.decode("iso-8859-1").rstrip("\r\n")
    except UnicodeDecodeError as exc:
        raise NetworkRequestError(
            "Central registry HTTP status is invalid"
        ) from exc
    parts = text.split(" ", 2)
    if len(parts) < 2 or parts[0] not in ("HTTP/1.0", "HTTP/1.1"):
        raise NetworkRequestError("Central registry HTTP status is invalid")
    try:
        status = int(parts[1])
    except ValueError as exc:
        raise NetworkRequestError(
            "Central registry HTTP status is invalid"
        ) from exc
    if status < 100 or status > 599:
        raise NetworkRequestError("Central registry HTTP status is invalid")
    reason = parts[2].strip() if len(parts) == 3 else ""
    return status, reason


def _read_headers(stream) -> Dict[str, str]:
    headers = {}  # type: Dict[str, str]
    total_bytes = 0
    line_count = 0
    while True:
        line = _readline(stream, _MAX_HEADER_LINE_BYTES, "header line")
        total_bytes += len(line)
        if total_bytes > _MAX_HEADER_BYTES:
            raise NetworkRequestError(
                "Central registry HTTP headers are too large"
            )
        if line in (b"\r\n", b"\n"):
            return headers
        line_count += 1
        if line_count > _MAX_HEADER_LINES:
            raise NetworkRequestError(
                "Central registry has too many HTTP headers"
            )
        if line[:1] in (b" ", b"\t"):
            raise NetworkRequestError(
                "Folded central registry HTTP headers are forbidden"
            )
        try:
            text = line.decode("iso-8859-1").rstrip("\r\n")
        except UnicodeDecodeError as exc:
            raise NetworkRequestError(
                "Central registry HTTP header is invalid"
            ) from exc
        name, separator, value = text.partition(":")
        if not separator:
            raise NetworkRequestError(
                "Central registry HTTP header is invalid"
            )
        name = name.strip().lower()
        if not name or any(character.isspace() for character in name):
            raise NetworkRequestError(
                "Central registry HTTP header name is invalid"
            )
        try:
            name.encode("ascii")
        except UnicodeEncodeError as exc:
            raise NetworkRequestError(
                "Central registry HTTP header name is invalid"
            ) from exc
        value = value.strip()
        if name in headers:
            headers[name] = "{},{}".format(headers[name], value)
        else:
            headers[name] = value


def _read_chunked_body(stream, max_bytes: int) -> bytes:
    chunks = []
    total = 0
    while True:
        line = _readline(stream, _MAX_CHUNK_LINE_BYTES, "chunk size")
        size_text = line.strip().split(b";", 1)[0]
        if not size_text:
            raise NetworkRequestError("Central registry chunk size is invalid")
        try:
            chunk_size = int(size_text, 16)
        except ValueError as exc:
            raise NetworkRequestError(
                "Central registry chunk size is invalid"
            ) from exc
        if chunk_size < 0:
            raise NetworkRequestError("Central registry chunk size is invalid")
        if chunk_size == 0:
            _read_headers(stream)
            return b"".join(chunks)
        if total + chunk_size > max_bytes:
            raise NetworkRequestError(
                "Central registry exceeds the allowed size"
            )
        chunks.append(_read_exact(stream, chunk_size, "chunk body"))
        if _read_exact(stream, 2, "chunk terminator") != b"\r\n":
            raise NetworkRequestError(
                "Central registry chunk terminator is invalid"
            )
        total += chunk_size


def _read_response_body(
    stream,
    status: int,
    headers: Dict[str, str],
    max_bytes: int,
) -> bytes:
    if status in (204, 304) or 100 <= status < 200:
        return b""
    content_encoding = headers.get("content-encoding", "").strip().lower()
    if content_encoding not in ("", "identity"):
        raise NetworkRequestError(
            "Compressed central registry responses are forbidden"
        )
    transfer_encoding = headers.get("transfer-encoding", "").strip().lower()
    if transfer_encoding:
        if transfer_encoding != "chunked":
            raise NetworkRequestError(
                "Unsupported central registry transfer encoding"
            )
        return _read_chunked_body(stream, max_bytes)
    content_length = headers.get("content-length")
    if content_length is not None:
        try:
            expected = int(content_length.strip())
        except ValueError as exc:
            raise NetworkRequestError(
                "Central registry content length is invalid"
            ) from exc
        if expected < 0:
            raise NetworkRequestError(
                "Central registry content length is invalid"
            )
        if expected > max_bytes:
            raise NetworkRequestError(
                "Central registry exceeds the allowed size"
            )
        return _read_exact(stream, expected, "response body")
    body = stream.read(max_bytes + 1)
    if len(body) > max_bytes:
        raise NetworkRequestError("Central registry exceeds the allowed size")
    return body


def _connect_tcp(host: str, port: int, timeout: float):
    last_error = None  # type: Optional[BaseException]
    try:
        addresses = socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)
    except OSError as exc:
        raise NetworkRequestError(
            "Unable to resolve the central registry host"
        ) from exc

    for family, socket_type, protocol, _canonical_name, address in addresses:
        raw_socket = None
        try:
            raw_socket = socket.socket(family, socket_type, protocol)
            raw_socket.settimeout(timeout)
            raw_socket.connect(address)
            return raw_socket
        except (OSError, ValueError) as exc:
            last_error = exc
            if raw_socket is not None:
                try:
                    raw_socket.close()
                except OSError:
                    pass

    if last_error is None:
        raise NetworkRequestError(
            "No address is available for the central registry host"
        )
    raise NetworkRequestError(
        "Unable to establish the central registry HTTP connection"
    ) from last_error


def http_get(
    url: str,
    user_agent: str,
    timeout: float,
    max_bytes: int,
) -> SecureHTTPResponse:
    """Download one bounded HTTP resource from the fixed registry host."""

    parsed = urlparse(url)
    if parsed.scheme.lower() != "http":
        raise NetworkSecurityError("Only HTTP registry requests are allowed")
    host = (parsed.hostname or "").lower()
    if host not in ALLOWED_NETWORK_HOSTS:
        raise NetworkSecurityError(
            "Central registry host is not allowed: {}".format(
                host or "<missing>"
            )
        )
    try:
        port = parsed.port or 80
    except ValueError as exc:
        raise NetworkSecurityError(
            "Central registry URL port is invalid"
        ) from exc
    if port != 80:
        raise NetworkSecurityError("Only the standard HTTP port is allowed")
    if parsed.username is not None or parsed.password is not None:
        raise NetworkSecurityError(
            "Credentials in registry URLs are forbidden"
        )
    if parsed.params or parsed.query:
        raise NetworkSecurityError(
            "Parameters and queries in registry URLs are forbidden"
        )
    if parsed.fragment:
        raise NetworkSecurityError("Fragments in registry URLs are forbidden")
    if "\r" in user_agent or "\n" in user_agent:
        raise NetworkSecurityError("Central registry user agent is invalid")
    try:
        user_agent.encode("ascii")
    except UnicodeEncodeError as exc:
        raise NetworkSecurityError(
            "Central registry user agent is invalid"
        ) from exc

    target = parsed.path or "/"
    if any(
        ord(character) < 32 or ord(character) == 127
        for character in target
    ):
        raise NetworkSecurityError(
            "Central registry request target is invalid"
        )
    try:
        request_bytes = (
            "GET {} HTTP/1.1\r\n"
            "Host: {}\r\n"
            "User-Agent: {}\r\n"
            "Accept: application/json\r\n"
            "Accept-Encoding: identity\r\n"
            "Connection: close\r\n"
            "\r\n"
        ).format(target, host, user_agent).encode("ascii")
    except UnicodeEncodeError as exc:
        raise NetworkSecurityError(
            "Central registry request target is invalid"
        ) from exc

    raw_socket = None
    stream = None
    try:
        raw_socket = _connect_tcp(host, port, timeout)
        raw_socket.sendall(request_bytes)
        stream = raw_socket.makefile("rb")
        while True:
            status_line = _readline(
                stream,
                _MAX_STATUS_LINE_BYTES,
                "status line",
            )
            status, reason = _parse_status_line(status_line)
            headers = _read_headers(stream)
            if status == 100:
                continue
            body = _read_response_body(stream, status, headers, max_bytes)
            return SecureHTTPResponse(status, reason, headers, body)
    except (NetworkRequestError, NetworkSecurityError):
        raise
    except (OSError, ValueError) as exc:
        raise NetworkRequestError(
            "Unable to download the central registry"
        ) from exc
    finally:
        if stream is not None:
            try:
                stream.close()
            except OSError:
                pass
        if raw_socket is not None:
            try:
                raw_socket.close()
            except OSError:
                pass
