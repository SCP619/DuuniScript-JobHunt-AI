"""URL validation and canonicalization for user-supplied job links."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.core.errors import AppError

MAX_URL_LENGTH = 2000
TRACKING_PARAMS = {"fbclid", "gclid", "dclid", "msclkid", "mc_cid", "mc_eid", "igshid", "trk", "trackingid", "ref"}
TRACKING_PREFIXES = ("utm_",)


def validate_http_url(url: str, field: str = "url") -> str:
    """Accept only absolute http(s) URLs without embedded credentials."""
    url = (url or "").strip()
    if not url or len(url) > MAX_URL_LENGTH:
        raise AppError(422, "invalid_url", f"{field} must be an http(s) URL of at most {MAX_URL_LENGTH} characters.")
    parts = urlsplit(url)
    if parts.scheme.lower() not in ("http", "https") or not parts.hostname:
        raise AppError(422, "invalid_url", f"{field} must be an absolute http or https URL.")
    if parts.username or parts.password:
        raise AppError(422, "invalid_url", f"{field} must not contain a username or password.")
    try:
        parts.port  # noqa: B018 - raises ValueError on an invalid port
    except ValueError as exc:
        raise AppError(422, "invalid_url", f"{field} has an invalid port.") from exc
    return url


def canonicalize_url(url: str) -> str:
    """Normalize a URL for duplicate detection.

    Lowercases scheme and host, drops default ports, fragments and common tracking
    parameters, sorts the remaining query parameters and trims a trailing slash.
    """
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower().rstrip(".")
    port = parts.port
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        host = f"{host}:{port}"
    path = parts.path or "/"
    if len(path) > 1:
        path = path.rstrip("/")
    query = sorted(
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() not in TRACKING_PARAMS and not k.lower().startswith(TRACKING_PREFIXES)
    )
    return urlunsplit((scheme, host, path, urlencode(query), ""))


def domain_of(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()
