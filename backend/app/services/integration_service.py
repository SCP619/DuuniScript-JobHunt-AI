"""Connected accounts: Gmail (Google) and a Microsoft 365 mailbox such as the UTU one.

What they do:
- Read job alert emails straight from the mailbox (no IMAP app password, no Gmail label or
  filter needed; alerts are found by the job sites' sender domains).
- Gmail only: create a Gmail draft of an approved application, or send it after the user's
  explicit confirmation (with the package hash they reviewed); the sent email is recorded.

What they never do: sign in to other websites for the user, store passwords, or bypass 2FA.
The user signs in on Google's or Microsoft's own page; only refresh tokens are kept, in
Windows Credential Manager. Disconnecting revokes (Google) and deletes them.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.job_sources.email_alerts import SITES
from app.adapters.oauth_mail import (
    GmailAlertMailbox,
    GmailApi,
    GoogleClient,
    GoogleOAuth,
    GraphMailbox,
    MicrosoftDeviceFlow,
    OAuthError,
    TokenStore,
    expires_in,
)
from app.core.config import Settings
from app.core.errors import AppError
from app.persistence.models import Integration, utcnow
from app.services import audit

GOOGLE = "google"
MICROSOFT = "microsoft"
TOKEN_NAMES = {GOOGLE: "google-refresh-token", MICROSOFT: "microsoft-refresh-token"}
MICROSOFT_SOURCE = "email_alerts_microsoft"
SIGN_IN_MESSAGES = {
    "admin_consent_required": (
        "Your organisation (for example the University of Turku) requires an administrator to approve "
        "this app before it can read your mailbox. Ask the IT service to approve it, or keep uploading "
        "the alert emails as .eml files."
    ),
    "expired_token": "The sign-in code expired. Start again.",
    "access_denied": "The sign-in was cancelled.",
    "device_code_failed": "Microsoft did not start the sign-in. Check MS_CLIENT_ID and that public client flows are allowed.",
}


def sender_domains() -> list[str]:
    return sorted({d for site in SITES for d in site.sender_domains})


@dataclass
class DeviceSignIn:
    status: str = "idle"  # idle, waiting, connected, failed
    user_code: str | None = None
    verification_uri: str | None = None
    expires_at: datetime | None = None
    message: str | None = None
    thread: threading.Thread | None = field(default=None, repr=False)


class Integrations:
    """Per-app state: HTTP client, token store, pending sign-ins."""

    def __init__(self, settings: Settings, http: httpx.Client | None = None, tokens: TokenStore | None = None) -> None:
        self.settings = settings
        self.http = http or httpx.Client(timeout=30.0, follow_redirects=False)
        self.tokens = tokens or TokenStore()
        self.device = DeviceSignIn()
        self._google: GoogleOAuth | None = None

    # ----- configuration -----

    def google_client(self) -> GoogleClient | None:
        return GoogleClient.from_file(self.settings.google_oauth_client_file)

    def google(self) -> GoogleOAuth:
        client = self.google_client()
        if client is None:
            raise AppError(409, "google_not_configured",
                           "Gmail is not set up: save the Google OAuth client file and set GOOGLE_OAUTH_CLIENT_FILE.")
        if self._google is None or self._google.client != client:
            self._google = GoogleOAuth(client, self.http)
        return self._google

    def microsoft(self) -> MicrosoftDeviceFlow:
        if not self.settings.ms_client_id:
            raise AppError(409, "microsoft_not_configured",
                           "The Microsoft mailbox is not set up: register an app and set MS_CLIENT_ID.")
        return MicrosoftDeviceFlow(self.settings.ms_client_id, self.settings.ms_tenant, self.http)

    # ----- mailboxes -----

    def gmail_api(self) -> GmailApi | None:
        token = self.tokens.get(TOKEN_NAMES[GOOGLE])
        if not token or self.google_client() is None:
            return None
        return GmailApi(self.google(), token, pause=0.0 if self.settings.oauth_fast_poll else 0.05,
                        backoff_scale=0.0 if self.settings.oauth_fast_poll else 1.0)

    def gmail_mailbox(self) -> GmailAlertMailbox | None:
        api = self.gmail_api()
        return GmailAlertMailbox(api, sender_domains()) if api else None

    def graph_mailbox(self) -> GraphMailbox | None:
        token = self.tokens.get(TOKEN_NAMES[MICROSOFT])
        if not token or not self.settings.ms_client_id:
            return None
        return GraphMailbox(self.microsoft(), token, sender_domains(),
                            lambda new: self.tokens.set(TOKEN_NAMES[MICROSOFT], new))


# ---------- Rows ----------


def _row(session: Session, provider: str) -> Integration | None:
    return session.scalar(select(Integration).where(Integration.provider == provider))


def _save(session: Session, provider: str, account: str | None, scopes: str) -> Integration:
    row = _row(session, provider)
    if row is None:
        row = Integration(provider=provider, scopes=scopes)
        session.add(row)
    row.account, row.scopes, row.connected_at = account, scopes, utcnow()
    row.last_error = row.last_error_at = None
    audit.record(session, "integration.connected", "integration", None, {"provider": provider})
    session.commit()
    return row


def record_sync(session: Session, provider: str, error: str | None) -> None:
    row = _row(session, provider)
    if row is None:
        return
    if error:
        row.last_error, row.last_error_at = error[:300], utcnow()
    else:
        row.last_sync_at, row.last_error, row.last_error_at = utcnow(), None, None
    session.commit()


# ---------- Google ----------


def google_start(integrations: Integrations) -> str:
    redirect = f"http://127.0.0.1:{integrations.settings.api_port}/api/v1/integrations/google/callback"
    return integrations.google().authorization_url(redirect)


def google_finish(session: Session, integrations: Integrations, state: str | None, code: str | None,
                  error: str | None) -> tuple[bool, str]:
    if error or not state or not code:
        return False, "Google sign-in was cancelled."
    try:
        tokens = integrations.google().exchange(state, code)
    except OAuthError as exc:
        return False, "This sign-in link has expired. Start again from DuuniScript." if exc.reason == "bad_state" \
            else "Google did not accept the sign-in. Start again from DuuniScript."
    integrations.tokens.set(TOKEN_NAMES[GOOGLE], tokens["refresh_token"])
    api = integrations.gmail_api()
    try:
        account = api.profile_email() if api else None
    except Exception:  # noqa: BLE001 - the account address is only shown, not needed
        account = None
    _save(session, GOOGLE, account, tokens.get("scope", ""))
    return True, f"Gmail is connected{f' ({account})' if account else ''}. You can close this tab."


# ---------- Microsoft ----------


def microsoft_start(integrations: Integrations, session_factory) -> DeviceSignIn:  # noqa: ANN001
    flow = integrations.microsoft()
    current = integrations.device
    if current.status == "waiting" and current.expires_at and current.expires_at > datetime.now(timezone.utc):
        return current
    try:
        data = flow.start()
    except OAuthError as exc:
        raise AppError(502, "microsoft_error", SIGN_IN_MESSAGES.get(exc.reason, "Microsoft sign-in could not start.")) from exc
    sign_in = DeviceSignIn(
        status="waiting",
        user_code=data["user_code"],
        verification_uri=data.get("verification_uri", "https://microsoft.com/devicelogin"),
        expires_at=expires_in(data),
    )
    integrations.device = sign_in
    interval = max(1, int(data.get("interval", 5)))

    def wait() -> None:
        while datetime.now(timezone.utc) < sign_in.expires_at:
            time.sleep(interval if not integrations.settings.oauth_fast_poll else 0.01)
            try:
                tokens = flow.poll(data["device_code"])
            except OAuthError as exc:
                sign_in.status, sign_in.message = "failed", SIGN_IN_MESSAGES.get(exc.reason, "Microsoft sign-in failed.")
                return
            except httpx.HTTPError:
                continue
            if tokens is None:
                continue
            integrations.tokens.set(TOKEN_NAMES[MICROSOFT], tokens["refresh_token"])
            account = None
            mailbox = integrations.graph_mailbox()
            try:
                account = mailbox.account() if mailbox else None
            except Exception:  # noqa: BLE001 - shown only
                account = None
            with session_factory() as session:
                _save(session, MICROSOFT, account, tokens.get("scope", ""))
            sign_in.status, sign_in.message = "connected", None
            return
        sign_in.status, sign_in.message = "failed", SIGN_IN_MESSAGES["expired_token"]

    sign_in.thread = threading.Thread(target=wait, name="microsoft-sign-in", daemon=True)
    sign_in.thread.start()
    return sign_in


# ---------- Disconnect ----------


def disconnect(session: Session, integrations: Integrations, provider: str) -> None:
    token = integrations.tokens.get(TOKEN_NAMES[provider])
    if token and provider == GOOGLE and integrations.google_client() is not None:
        integrations.google().revoke(token)
    integrations.tokens.delete(TOKEN_NAMES[provider])
    row = _row(session, provider)
    if row is not None:
        session.delete(row)
    if provider == MICROSOFT:
        integrations.device = DeviceSignIn()
    audit.record(session, "integration.disconnected", "integration", None, {"provider": provider})
    session.commit()


def connected(session: Session, integrations: Integrations, provider: str) -> bool:
    return _row(session, provider) is not None and bool(integrations.tokens.get(TOKEN_NAMES[provider]))
