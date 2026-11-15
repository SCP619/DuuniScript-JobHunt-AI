"""Fetcher for user-initiated URL import and for official job feeds and APIs.

Safety rules:
- http/https only, standard ports only, no credentials in URLs.
- Every hop (including redirects) must resolve only to public internet addresses; private,
  loopback, link-local and reserved ranges are refused (SSRF protection).
- Bounded time, bounded size, bounded redirects, HTML responses only.
- No cookies, no authentication, no JavaScript execution, no retries.
- robots.txt is honoured for every hop (RFC 9309). A user-initiated import is still an
  automated request made by DuuniScript, so a site's "no bots" rule applies to it.

Known limitation: the address check and the connection resolve DNS separately, so a
hostile DNS server could still rebind between them. Acceptable for a loopback-only,
single-user tool; revisit before any multi-user or LAN deployment.
"""

from __future__ import annotations

import ipaddress
import socket
import time
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx

from app import __version__
from app.adapters.robots import MAX_ROBOTS_BYTES, RobotsRules, parse_robots
from app.core.errors import AppError
from app.services.urls import validate_http_url

Resolver = Callable[[str], list[str]]

USER_AGENT = f"DuuniScript/{__version__} (personal job tracker; single user-initiated import)"
FEED_USER_AGENT = f"DuuniScript/{__version__} (personal job tracker for one user; reads official job feeds)"
FEED_TYPES = ("json", "xml", "rss", "atom")
ALLOWED_PORTS = {None, 80, 443}
ROBOTS_CACHE_SECONDS = 3600
# Ask for English first. Most Finnish boards ignore this, and an English page may still carry
# a Finnish advertisement, so the posting language is always read from the posting itself.
ACCEPT_LANGUAGE = "en, fi;q=0.5, sv;q=0.3"


def system_resolver(host: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise FetchError("dns_failed", "The address could not be resolved.") from exc
    return sorted({info[4][0] for info in infos})


class FetchError(AppError):
    def __init__(self, reason: str, message: str, status_code: int = 502, extra: dict | None = None) -> None:
        super().__init__(status_code, "fetch_failed", message, {"reason": reason, **(extra or {})})
        self.reason = reason


@dataclass(frozen=True)
class FetchResult:
    requested_url: str
    final_url: str
    status_code: int
    content_type: str
    text: str
    content: bytes = b""


class SafeFetcher:
    def __init__(
        self,
        transport: httpx.BaseTransport | None = None,
        resolver: Resolver = system_resolver,
        timeout_seconds: float = 15.0,
        max_bytes: int = 3 * 1_048_576,
        max_redirects: int = 5,
        respect_robots: bool = True,
    ) -> None:
        self.respect_robots = respect_robots
        self._robots_cache: dict[str, tuple[RobotsRules, float]] = {}
        self.transport = transport
        self.resolver = resolver
        self.timeout = httpx.Timeout(timeout_seconds)
        self.max_bytes = max_bytes
        self.max_redirects = max_redirects

    def check_destination(self, url: str) -> None:
        validate_http_url(url)
        parts = urlsplit(url)
        if parts.port not in ALLOWED_PORTS:
            raise FetchError("blocked_port", "Only standard web ports (80 and 443) can be imported.", 422)
        host = parts.hostname or ""
        try:
            addresses = [str(ipaddress.ip_address(host.strip("[]")))]
        except ValueError:
            if host.lower() in ("localhost",) or host.lower().endswith((".localhost", ".local", ".internal")):
                raise FetchError("blocked_address", "Local and private addresses cannot be imported.", 422) from None
            addresses = self.resolver(host)
        if not addresses:
            raise FetchError("dns_failed", "The address could not be resolved.")
        for address in addresses:
            ip = ipaddress.ip_address(address.split("%")[0])
            if not ip.is_global or ip.is_multicast:
                raise FetchError("blocked_address", "Local and private addresses cannot be imported.", 422)

    def _client(self) -> httpx.Client:
        return httpx.Client(
            transport=self.transport,
            timeout=self.timeout,
            follow_redirects=False,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": ACCEPT_LANGUAGE,
            },
            trust_env=False,
        )

    def robots_for(self, client: httpx.Client, url: str) -> RobotsRules:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}".lower()
        cached = self._robots_cache.get(origin)
        if cached and cached[1] > time.monotonic():
            return cached[0]
        current = origin + "/robots.txt"
        rules = RobotsRules.unreachable()
        try:
            for _ in range(self.max_redirects + 1):
                self.check_destination(current)
                response = client.get(current, headers={"Accept": "text/plain"})
                if response.is_redirect and response.headers.get("location"):
                    current = urljoin(current, response.headers["location"])
                    continue
                if response.status_code == 200:
                    rules = parse_robots(response.content[:MAX_ROBOTS_BYTES].decode("utf-8", errors="replace"))
                elif 400 <= response.status_code < 500:
                    rules = RobotsRules.allow_everything()  # RFC 9309: unavailable means unrestricted
                break
        except (httpx.HTTPError, FetchError):
            rules = RobotsRules.unreachable()
        self._robots_cache[origin] = (rules, time.monotonic() + ROBOTS_CACHE_SECONDS)
        return rules

    def fetch_html(self, url: str) -> FetchResult:
        return self._fetch(url, ("html",), self.respect_robots, self.max_bytes)

    def fetch_feed(self, url: str, honour_robots: bool = True, max_bytes: int = 10 * 1_048_576) -> FetchResult:
        """An official feed or API response (JSON or XML). ``honour_robots`` is False only for
        an address the site's own API documentation tells programs to use."""
        return self._fetch(url, FEED_TYPES, self.respect_robots and honour_robots, max_bytes, feed=True)

    def _fetch(
        self, url: str, accepted: tuple[str, ...], respect_robots: bool, max_bytes: int, feed: bool = False
    ) -> FetchResult:
        current = url
        with self._client() as client:
            if feed:
                client.headers["User-Agent"] = FEED_USER_AGENT
                client.headers["Accept"] = "application/json, application/rss+xml, application/xml;q=0.9, */*;q=0.1"
            for _ in range(self.max_redirects + 1):
                self.check_destination(current)
                if respect_robots and not self.robots_for(client, current).allows(current):
                    raise FetchError(
                        "robots_disallowed",
                        "This site does not allow automated access to this page. Add the job manually instead.",
                        422,
                    )
                try:
                    with client.stream("GET", current) as response:
                        if response.is_redirect:
                            location = response.headers.get("location")
                            if not location:
                                raise FetchError("bad_redirect", "The page redirected without a destination.")
                            current = urljoin(current, location)
                            continue
                        if response.status_code != 200:
                            raise FetchError(
                                "http_status",
                                "The page could not be retrieved.",
                                extra={"http_status": response.status_code},
                            )
                        content_type = response.headers.get("content-type", "").lower()
                        if not any(kind in content_type for kind in accepted):
                            if feed:
                                raise FetchError("not_feed", "The address did not return a job feed.", 422)
                            raise FetchError("not_html", "The address did not return a web page.", 422)
                        body = bytearray()
                        for chunk in response.iter_bytes():
                            body.extend(chunk)
                            if len(body) > max_bytes:
                                raise FetchError("too_large", "The page is too large to import.", 422)
                        encoding = response.charset_encoding or "utf-8"
                        text = "" if feed else bytes(body).decode(encoding, errors="replace")
                        return FetchResult(url, current, response.status_code, content_type, text, bytes(body))
                except httpx.TimeoutException as exc:
                    raise FetchError("timeout", "The page took too long to respond.", 504) from exc
                except httpx.HTTPError as exc:
                    raise FetchError("network_error", "The page could not be reached.") from exc
        raise FetchError("too_many_redirects", "The page redirected too many times.")
