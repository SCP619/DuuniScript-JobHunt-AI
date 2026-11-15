"""Mailbox access with OAuth: Gmail (Google) and Microsoft 365 (e.g. a university mailbox).

The user signs in on Google's or Microsoft's own page, including any two-factor step;
DuuniScript never sees a password or a 2FA code. Refresh tokens are kept in Windows
Credential Manager (``keyring``), never in files, settings or the database.

Scopes:
- Google: ``gmail.readonly`` (read alert emails) and ``gmail.compose`` (create drafts and send
  an application email the user approved), plus ``openid email``.
- Microsoft: ``Mail.Read`` and ``User.Read`` (read alert emails only), ``offline_access``.

Both mailboxes implement the ``AlertMailbox`` protocol of ``adapters.mailbox``, so their
emails go through exactly the same sender (DKIM) checks and parsing as IMAP.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

import httpx

from app.adapters.mailbox import MAX_MESSAGE_BYTES, MAX_MESSAGES_PER_SYNC, MailboxError

KEYRING_SERVICE = "DuuniScript accounts"
GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
GOOGLE_REVOKE = "https://oauth2.googleapis.com/revoke"
GMAIL = "https://gmail.googleapis.com/gmail/v1/users/me"
GOOGLE_SCOPES = (
    "openid email https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/gmail.compose"
)
MS_LOGIN = "https://login.microsoftonline.com"
GRAPH = "https://graph.microsoft.com/v1.0"
MS_SCOPES = "offline_access User.Read Mail.Read"


# ---------- Token storage ----------


class TokenStore:
    """Refresh tokens in Windows Credential Manager."""

    def get(self, name: str) -> str | None:
        try:
            import keyring

            return keyring.get_password(KEYRING_SERVICE, name)
        except Exception:  # noqa: BLE001 - no keyring backend: treat as not connected
            return None

    def set(self, name: str, value: str) -> None:
        import keyring

        keyring.set_password(KEYRING_SERVICE, name, value)

    def delete(self, name: str) -> None:
        try:
            import keyring

            keyring.delete_password(KEYRING_SERVICE, name)
        except Exception:  # noqa: BLE001 - already gone
            pass


class MemoryTokenStore(TokenStore):
    """For tests."""

    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def get(self, name: str) -> str | None:
        return self.values.get(name)

    def set(self, name: str, value: str) -> None:
        self.values[name] = value

    def delete(self, name: str) -> None:
        self.values.pop(name, None)


class OAuthError(Exception):
    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


def _json(response: httpx.Response) -> dict:
    try:
        return response.json()
    except ValueError:
        return {}


# ---------- Google ----------


@dataclass(frozen=True)
class GoogleClient:
    client_id: str
    client_secret: str

    @classmethod
    def from_file(cls, path: Path | None) -> GoogleClient | None:
        """The OAuth client JSON downloaded from Google Cloud Console (type "Desktop app")."""
        if path is None or not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            section = data.get("installed") or data.get("web") or {}
            return cls(section["client_id"], section["client_secret"])
        except (ValueError, KeyError, OSError):
            return None


@dataclass
class _Pending:
    verifier: str
    redirect_uri: str
    created: float = field(default_factory=time.monotonic)


class GoogleOAuth:
    """Authorization code flow with PKCE and a loopback redirect to the local API."""

    PENDING_SECONDS = 600

    def __init__(self, client: GoogleClient, http: httpx.Client) -> None:
        self.client = client
        self.http = http
        self._pending: dict[str, _Pending] = {}
        self._lock = threading.Lock()

    def authorization_url(self, redirect_uri: str) -> str:
        verifier = secrets.token_urlsafe(48)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        state = secrets.token_urlsafe(24)
        with self._lock:
            now = time.monotonic()
            self._pending = {k: v for k, v in self._pending.items() if now - v.created < self.PENDING_SECONDS}
            self._pending[state] = _Pending(verifier, redirect_uri)
        query = {
            "client_id": self.client.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": GOOGLE_SCOPES,
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        return f"{GOOGLE_AUTH}?{urlencode(query)}"

    def exchange(self, state: str, code: str) -> dict:
        with self._lock:
            pending = self._pending.pop(state, None)
        if pending is None or time.monotonic() - pending.created > self.PENDING_SECONDS:
            raise OAuthError("bad_state")
        response = self.http.post(GOOGLE_TOKEN, data={
            "code": code,
            "client_id": self.client.client_id,
            "client_secret": self.client.client_secret,
            "redirect_uri": pending.redirect_uri,
            "grant_type": "authorization_code",
            "code_verifier": pending.verifier,
        })
        data = _json(response)
        if response.status_code != 200 or "refresh_token" not in data:
            raise OAuthError("token_exchange_failed", str(data.get("error", response.status_code)))
        return data

    def access_token(self, refresh_token: str) -> str:
        response = self.http.post(GOOGLE_TOKEN, data={
            "client_id": self.client.client_id,
            "client_secret": self.client.client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        })
        data = _json(response)
        if response.status_code != 200 or "access_token" not in data:
            raise OAuthError("refresh_failed", str(data.get("error", response.status_code)))
        return data["access_token"]

    def revoke(self, token: str) -> None:
        try:
            self.http.post(GOOGLE_REVOKE, data={"token": token})
        except httpx.HTTPError:
            pass


BACKOFF_SECONDS = (2, 4, 8, 16, 32)


def is_rate_limited(response: httpx.Response) -> bool:
    """429, or 403 with a quota/rate-limit reason (Google and Microsoft both use these)."""
    if response.status_code == 429:
        return True
    if response.status_code != 403:
        return False
    text = response.text.lower()
    return any(word in text for word in ("ratelimitexceeded", "quota exceeded", "userratelimitexceeded", "throttl"))


class GmailApi:
    def __init__(self, oauth: GoogleOAuth, refresh_token: str, pause: float = 0.05, backoff_scale: float = 1.0) -> None:
        self.oauth = oauth
        self.refresh_token = refresh_token
        self.pause = pause
        self.backoff_scale = backoff_scale
        self._token: str | None = None

    def _headers(self) -> dict[str, str]:
        if self._token is None:
            try:
                self._token = self.oauth.access_token(self.refresh_token)
            except OAuthError as exc:
                raise MailboxError("auth_failed") from exc
        return {"Authorization": f"Bearer {self._token}"}

    def _get(self, url: str, **params) -> dict:  # noqa: ANN003
        for attempt in range(len(BACKOFF_SECONDS) + 1):
            time.sleep(self.pause)  # pace requests well under Gmail's per-user limits
            try:
                response = self.oauth.http.get(url, params=params, headers=self._headers())
            except httpx.HTTPError as exc:
                raise MailboxError("connection_failed") from exc
            if not is_rate_limited(response):
                break
            if attempt == len(BACKOFF_SECONDS):
                raise MailboxError("rate_limited")
            time.sleep(BACKOFF_SECONDS[attempt] * self.backoff_scale)
        if response.status_code in (401, 403):
            raise MailboxError("auth_failed")
        if response.status_code != 200:
            raise MailboxError("connection_failed")
        return _json(response)

    def profile_email(self) -> str | None:
        return self._get(f"{GMAIL}/profile").get("emailAddress")

    def fetch_query(self, query: str, skip: Callable[[str], bool]) -> Iterator[bytes]:
        from app.adapters.job_sources.email_alerts import message_key

        seen = 0
        page: str | None = None
        while seen < MAX_MESSAGES_PER_SYNC:
            params = {"q": query, "maxResults": 100}
            if page:
                params["pageToken"] = page
            listing = self._get(f"{GMAIL}/messages", **params)
            for item in listing.get("messages", []):
                seen += 1
                if seen > MAX_MESSAGES_PER_SYNC:
                    return
                data = self._get(f"{GMAIL}/messages/{item['id']}", format="raw")
                if int(data.get("sizeEstimate") or 0) > MAX_MESSAGE_BYTES:
                    continue
                raw = base64.urlsafe_b64decode(data.get("raw", "") + "===")
                if not skip(message_key(raw)):
                    yield raw
            page = listing.get("nextPageToken")
            if not page:
                return

    def _post(self, url: str, payload: dict) -> dict:
        try:
            response = self.oauth.http.post(url, json=payload, headers=self._headers())
        except httpx.HTTPError as exc:
            raise OAuthError("connection_failed") from exc
        if response.status_code not in (200, 201):
            raise OAuthError("gmail_refused", str(_json(response).get("error", {}).get("message", response.status_code)))
        return _json(response)

    def create_draft(self, raw: bytes) -> str:
        data = self._post(f"{GMAIL}/drafts", {"message": {"raw": base64.urlsafe_b64encode(raw).decode()}})
        return data.get("id", "")

    def send(self, raw: bytes) -> str:
        data = self._post(f"{GMAIL}/messages/send", {"raw": base64.urlsafe_b64encode(raw).decode()})
        return data.get("id", "")


class GmailAlertMailbox:
    """Alert emails from the known job sites, found by sender (no label or filter needed)."""

    def __init__(self, api: GmailApi, sender_domains: list[str]) -> None:
        self.api = api
        self.domains = sender_domains

    def fetch_since(self, since: date, skip: Callable[[str], bool]) -> Iterator[bytes]:
        senders = " OR ".join(self.domains)
        query = f"after:{since:%Y/%m/%d} from:({senders})"
        yield from self.api.fetch_query(query, skip)


# ---------- Microsoft 365 ----------

CONSENT_ERRORS = ("AADSTS65001", "AADSTS90094", "AADSTS90095", "AADSTS50105", "AADSTS65004")


class MicrosoftDeviceFlow:
    """Device code sign-in: the user opens microsoft.com/devicelogin, types the code and signs in
    (with their own 2FA) in the browser. DuuniScript polls for the result."""

    def __init__(self, client_id: str, tenant: str, http: httpx.Client) -> None:
        self.client_id = client_id
        self.tenant = tenant
        self.http = http

    def start(self) -> dict:
        response = self.http.post(f"{MS_LOGIN}/{self.tenant}/oauth2/v2.0/devicecode",
                                  data={"client_id": self.client_id, "scope": MS_SCOPES})
        data = _json(response)
        if response.status_code != 200 or "device_code" not in data:
            raise OAuthError("device_code_failed", str(data.get("error_description", data.get("error", ""))))
        return data

    def poll(self, device_code: str) -> dict | None:
        """Tokens when signed in; None while waiting; OAuthError when it failed or expired."""
        response = self.http.post(f"{MS_LOGIN}/{self.tenant}/oauth2/v2.0/token", data={
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "client_id": self.client_id,
            "device_code": device_code,
        })
        data = _json(response)
        if response.status_code == 200 and "refresh_token" in data:
            return data
        error = data.get("error", "")
        if error in ("authorization_pending", "slow_down"):
            return None
        description = str(data.get("error_description", ""))
        if any(code in description for code in CONSENT_ERRORS):
            raise OAuthError("admin_consent_required", description[:300])
        raise OAuthError(error or "sign_in_failed", description[:300])

    def access_token(self, refresh_token: str) -> tuple[str, str | None]:
        response = self.http.post(f"{MS_LOGIN}/{self.tenant}/oauth2/v2.0/token", data={
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "refresh_token": refresh_token,
            "scope": MS_SCOPES,
        })
        data = _json(response)
        if response.status_code != 200 or "access_token" not in data:
            description = str(data.get("error_description", ""))
            if any(code in description for code in CONSENT_ERRORS):
                raise OAuthError("admin_consent_required", description[:300])
            raise OAuthError("refresh_failed", str(data.get("error", response.status_code)))
        return data["access_token"], data.get("refresh_token")


class GraphMailbox:
    """Alert emails from known job sites in a Microsoft 365 mailbox, read-only."""

    def __init__(self, flow: MicrosoftDeviceFlow, refresh_token: str, sender_domains: list[str],
                 on_new_refresh_token: Callable[[str], None] | None = None) -> None:
        self.flow = flow
        self.refresh_token = refresh_token
        self.domains = [d.lower() for d in sender_domains]
        self.on_new_refresh_token = on_new_refresh_token
        self._token: str | None = None

    def _headers(self) -> dict[str, str]:
        if self._token is None:
            try:
                self._token, rotated = self.flow.access_token(self.refresh_token)
            except OAuthError as exc:
                raise MailboxError("consent_required" if exc.reason == "admin_consent_required" else "auth_failed") from exc
            if rotated and rotated != self.refresh_token and self.on_new_refresh_token:
                self.on_new_refresh_token(rotated)
        return {"Authorization": f"Bearer {self._token}"}

    def _get(self, url: str, params: dict | None = None) -> httpx.Response:
        for attempt in range(len(BACKOFF_SECONDS) + 1):
            try:
                response = self.flow.http.get(url, params=params, headers=self._headers())
            except httpx.HTTPError as exc:
                raise MailboxError("connection_failed") from exc
            if not is_rate_limited(response):
                break
            if attempt == len(BACKOFF_SECONDS):
                raise MailboxError("rate_limited")
            time.sleep(BACKOFF_SECONDS[attempt])
        if response.status_code in (401, 403):
            raise MailboxError("auth_failed")
        if response.status_code != 200:
            raise MailboxError("connection_failed")
        return response

    def account(self) -> str | None:
        data = _json(self._get(f"{GRAPH}/me", {"$select": "mail,userPrincipalName"}))
        return data.get("mail") or data.get("userPrincipalName")

    def _wanted(self, address: str) -> bool:
        domain = address.rsplit("@", 1)[-1].lower()
        return any(domain == d or domain.endswith("." + d) for d in self.domains)

    def fetch_since(self, since: date, skip: Callable[[str], bool]) -> Iterator[bytes]:
        start = datetime(since.year, since.month, since.day, tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        url: str | None = f"{GRAPH}/me/messages"
        params: dict | None = {
            "$filter": f"receivedDateTime ge {start}",
            "$select": "id,from,internetMessageId",
            "$orderby": "receivedDateTime desc",
            "$top": "50",
        }
        seen = 0
        while url and seen < MAX_MESSAGES_PER_SYNC:
            data = _json(self._get(url, params))
            for item in data.get("value", []):
                seen += 1
                address = ((item.get("from") or {}).get("emailAddress") or {}).get("address", "")
                if not self._wanted(address):
                    continue
                key = item.get("internetMessageId")
                if key and skip(key):
                    continue
                raw = self._get(f"{GRAPH}/me/messages/{item['id']}/$value").content
                if len(raw) <= MAX_MESSAGE_BYTES:
                    yield raw
            url, params = data.get("@odata.nextLink"), None


def expires_in(data: dict) -> datetime:
    return datetime.now(timezone.utc) + timedelta(seconds=int(data.get("expires_in", 900)))
