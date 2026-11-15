"""Sign-in to DuuniScript, and the Gmail / Microsoft 365 connectors (simulated providers)."""

from __future__ import annotations

import base64
import json
import time
from email import message_from_bytes
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi.testclient import TestClient

from app.adapters.oauth_mail import MemoryTokenStore
from app.core.config import Settings
from app.main import create_app
from app.services import auth_service
from app.services.integration_service import Integrations
from tests.test_applications import JOB, _approve_all, _start
from tests.test_job_alerts import linkedin_email
from tests.test_outcomes_notifications import _verified


@pytest.fixture(autouse=True)
def _no_lockout():
    auth_service.reset_lockout()
    yield
    auth_service.reset_lockout()


# ---------- Sign-in ----------


def test_open_until_a_passphrase_exists(client: TestClient) -> None:
    assert client.get("/api/v1/auth/status").json() == {"password_set": False, "signed_in": False}
    assert client.get("/api/v1/jobs").status_code == 200  # no passphrase: open as before


def test_setup_login_logout_change(client: TestClient) -> None:
    assert client.post("/api/v1/auth/setup", json={"password": "short"}).json()["error"]["code"] == "password_too_short"
    made = client.post("/api/v1/auth/setup", json={"password": "correct horse battery"})
    assert made.status_code == 200
    token = made.json()["token"]
    assert client.post("/api/v1/auth/setup", json={"password": "another passphrase"}).status_code == 409

    blocked = client.get("/api/v1/jobs")
    assert blocked.status_code == 401 and blocked.json()["error"]["code"] == "auth_required"
    assert client.get("/health").status_code == 200
    auth = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/jobs", headers=auth).status_code == 200
    assert client.get("/api/v1/auth/status", headers=auth).json() == {"password_set": True, "signed_in": True}

    assert client.post("/api/v1/auth/login", json={"password": "wrong passphrase"}).status_code == 401
    second = client.post("/api/v1/auth/login", json={"password": "correct horse battery"}).json()["token"]
    client.post("/api/v1/auth/change", headers=auth,
                json={"current_password": "correct horse battery", "new_password": "a brand new passphrase"})
    assert client.get("/api/v1/jobs", headers={"Authorization": f"Bearer {second}"}).status_code == 401  # signed out
    assert client.get("/api/v1/jobs", headers=auth).status_code == 200  # this browser stays in
    client.post("/api/v1/auth/logout", headers=auth)
    assert client.get("/api/v1/jobs", headers=auth).status_code == 401


def test_lockout_after_five_wrong_attempts(client: TestClient) -> None:
    client.post("/api/v1/auth/setup", json={"password": "correct horse battery"})
    for _ in range(5):
        client.post("/api/v1/auth/login", json={"password": "nope nope nope"})
    locked = client.post("/api/v1/auth/login", json={"password": "correct horse battery"})
    assert locked.status_code == 429 and locked.json()["error"]["code"] == "sign_in_locked"


def test_unauthorised_responses_carry_cors_headers(client: TestClient) -> None:
    client.post("/api/v1/auth/setup", json={"password": "correct horse battery"})
    response = client.get("/api/v1/jobs", headers={"Origin": "http://localhost:8080"})
    assert response.status_code == 401
    assert response.headers.get("access-control-allow-origin") == "http://localhost:8080"


def test_password_is_hashed() -> None:
    stored = auth_service.hash_password("correct horse battery")
    assert "correct" not in stored and stored.startswith("scrypt$")
    assert auth_service.check_password("correct horse battery", stored)
    assert not auth_service.check_password("correct horse batterY", stored)


# ---------- Simulated providers ----------


class FakeProviders:
    def __init__(self) -> None:
        self.sent: list[bytes] = []
        self.drafts: list[bytes] = []
        self.ms_polls = 0
        self.ms_error: str | None = None
        self.alert = linkedin_email(("Data Analyst", "Example Oy", "Turku", "4100000001"))

    def handler(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        body = request.content.decode() if request.content else ""
        if url.startswith("https://oauth2.googleapis.com/token"):
            form = parse_qs(body)
            if form.get("grant_type") == ["authorization_code"]:
                assert form["code_verifier"][0]  # PKCE
                return httpx.Response(200, json={"refresh_token": "g-refresh", "access_token": "g-access",
                                                 "scope": "gmail.readonly gmail.compose"})
            return httpx.Response(200, json={"access_token": "g-access"})
        if url.startswith("https://oauth2.googleapis.com/revoke"):
            return httpx.Response(200)
        if url.startswith("https://gmail.googleapis.com/gmail/v1/users/me/profile"):
            return httpx.Response(200, json={"emailAddress": "synthetic.user@example.com"})
        if url.startswith("https://gmail.googleapis.com/gmail/v1/users/me/messages/send"):
            self.sent.append(base64.urlsafe_b64decode(json.loads(body)["raw"]))
            return httpx.Response(200, json={"id": "sent-1"})
        if url.startswith("https://gmail.googleapis.com/gmail/v1/users/me/drafts"):
            self.drafts.append(base64.urlsafe_b64decode(json.loads(body)["message"]["raw"]))
            return httpx.Response(200, json={"id": "draft-1"})
        if url.startswith("https://gmail.googleapis.com/gmail/v1/users/me/messages/m1"):
            raw = base64.urlsafe_b64encode(self.alert).decode()
            return httpx.Response(200, json={"raw": raw, "sizeEstimate": len(self.alert)})
        if url.startswith("https://gmail.googleapis.com/gmail/v1/users/me/messages"):
            assert "from:(" in request.url.params["q"]
            return httpx.Response(200, json={"messages": [{"id": "m1"}]})
        if url.endswith("/oauth2/v2.0/devicecode"):
            return httpx.Response(200, json={"device_code": "dev", "user_code": "ABCD-EFGH", "interval": 1,
                                             "verification_uri": "https://microsoft.com/devicelogin", "expires_in": 60})
        if url.endswith("/oauth2/v2.0/token"):
            form = parse_qs(body)
            if form["grant_type"][0].endswith("device_code"):
                self.ms_polls += 1
                if self.ms_error:
                    return httpx.Response(400, json={"error": "invalid_grant", "error_description": self.ms_error})
                if self.ms_polls < 2:
                    return httpx.Response(400, json={"error": "authorization_pending"})
                return httpx.Response(200, json={"refresh_token": "m-refresh", "access_token": "m-access",
                                                 "scope": "Mail.Read User.Read"})
            return httpx.Response(200, json={"access_token": "m-access", "refresh_token": "m-refresh-2"})
        if url.startswith("https://graph.microsoft.com/v1.0/me/messages/x1/$value"):
            return httpx.Response(200, content=self.alert)
        if url.startswith("https://graph.microsoft.com/v1.0/me/messages"):
            return httpx.Response(200, json={"value": [
                {"id": "x1", "from": {"emailAddress": {"address": "jobalerts-noreply@linkedin.com"}},
                 "internetMessageId": "<not-seen@example>"},
                {"id": "x2", "from": {"emailAddress": {"address": "teacher@utu.fi"}}, "internetMessageId": "<private@x>"},
            ]})
        if url.startswith("https://graph.microsoft.com/v1.0/me"):
            return httpx.Response(200, json={"mail": "synthetic.student@example.fi"})
        return httpx.Response(404)


@pytest.fixture
def providers() -> FakeProviders:
    return FakeProviders()


@pytest.fixture
def connected_client(tmp_path: Path, providers: FakeProviders, fake_web):  # noqa: ANN001, ANN201
    client_file = tmp_path / "google-client.json"
    client_file.write_text(json.dumps({"installed": {"client_id": "cid.apps.googleusercontent.com", "client_secret": "s"}}))
    settings = Settings(
        app_data_dir=tmp_path / "DuuniScriptTest", feed_sync_interval_minutes=0, backup_interval_hours=0,
        mail_sync_interval_minutes=0, google_oauth_client_file=client_file, ms_client_id="ms-client",
        oauth_fast_poll=True, _env_file=None,
    )
    app = create_app(settings)
    app.state.fetcher = fake_web.fetcher()
    app.state.feed_fetcher = fake_web.fetcher()
    app.state.integrations = Integrations(settings, http=httpx.Client(transport=httpx.MockTransport(providers.handler)),
                                          tokens=MemoryTokenStore())
    with TestClient(app) as test_client:
        yield test_client


def test_status_when_not_set_up(client: TestClient) -> None:
    body = client.get("/api/v1/integrations").json()
    assert body["google"] == {"configured": False, "connected": False, "account": None, "connected_at": None,
                              "last_sync_at": None, "last_error": None}
    assert client.post("/api/v1/integrations/google/connect").json()["error"]["code"] == "google_not_configured"
    assert client.post("/api/v1/integrations/microsoft/connect").json()["error"]["code"] == "microsoft_not_configured"


def test_google_connect_sync_and_disconnect(connected_client: TestClient, providers: FakeProviders) -> None:
    url = connected_client.post("/api/v1/integrations/google/connect").json()["url"]
    query = parse_qs(urlparse(url).query)
    assert query["redirect_uri"] == ["http://127.0.0.1:8000/api/v1/integrations/google/callback"]
    assert query["code_challenge_method"] == ["S256"] and "gmail.compose" in query["scope"][0]
    bad = connected_client.get("/api/v1/integrations/google/callback", params={"state": "forged", "code": "x"})
    assert bad.status_code == 400 and "expired" in bad.text
    done = connected_client.get("/api/v1/integrations/google/callback", params={"state": query["state"][0], "code": "c"})
    assert done.status_code == 200 and "Gmail is connected (synthetic.user@example.com)" in done.text
    state = connected_client.get("/api/v1/integrations").json()["google"]
    assert state["connected"] and state["account"] == "synthetic.user@example.com"
    assert connected_client.app.state.integrations.tokens.get("google-refresh-token") == "g-refresh"

    synced = connected_client.post("/api/v1/integrations/google/sync")
    assert synced.status_code == 200, synced.text
    assert synced.json()["emails_checked"] == 1
    assert connected_client.get("/api/v1/integrations").json()["google"]["last_sync_at"]

    assert connected_client.delete("/api/v1/integrations/google").status_code == 204
    assert connected_client.app.state.integrations.tokens.get("google-refresh-token") is None
    assert connected_client.get("/api/v1/integrations").json()["google"]["connected"] is False


def test_google_callback_needs_no_sign_in_but_api_does(connected_client: TestClient) -> None:
    connected_client.post("/api/v1/auth/setup", json={"password": "correct horse battery"})
    assert connected_client.post("/api/v1/integrations/google/connect").status_code == 401
    assert connected_client.get("/api/v1/integrations/google/callback", params={"state": "x", "code": "y"}).status_code == 400


def _connect_google(client: TestClient) -> None:
    url = client.post("/api/v1/integrations/google/connect").json()["url"]
    state = parse_qs(urlparse(url).query)["state"][0]
    client.get("/api/v1/integrations/google/callback", params={"state": state, "code": "c"})


def test_gmail_draft_and_send_with_approval(connected_client: TestClient, providers: FakeProviders) -> None:
    client = connected_client
    client.put("/api/v1/profile", json={"display_name": "Testi Käyttäjä", "email": "testi.kayttaja@example.com"})
    _verified(client)
    job = client.post("/api/v1/jobs", json=JOB).json()
    app = _start(client, job)
    assert client.post(f"/api/v1/applications/{app['id']}/gmail-draft").json()["error"]["code"] == "application_not_ready"
    app = _approve_all(client, app)
    assert client.post(f"/api/v1/applications/{app['id']}/gmail-draft").json()["error"]["code"] == "gmail_not_connected"
    _connect_google(client)

    draft = client.post(f"/api/v1/applications/{app['id']}/gmail-draft")
    assert draft.status_code == 200 and draft.json()["draft_id"] == "draft-1"
    message = message_from_bytes(providers.drafts[0])
    assert message["To"] == "jobs@example.com" and message["Subject"] == "Application: Data Analyst"
    assert providers.sent == []  # a draft sends nothing

    stale = client.post(f"/api/v1/applications/{app['id']}/send-email",
                        json={"confirm": True, "package_hash": "0" * 64, "to": "jobs@example.com"})
    assert stale.status_code == 409 and providers.sent == []
    unconfirmed = client.post(f"/api/v1/applications/{app['id']}/send-email",
                              json={"confirm": False, "package_hash": app["package_hash"], "to": "jobs@example.com"})
    assert unconfirmed.status_code == 422 and providers.sent == []

    sent = client.post(f"/api/v1/applications/{app['id']}/send-email",
                       json={"confirm": True, "package_hash": app["package_hash"], "to": "jobs@example.com"})
    assert sent.status_code == 200, sent.text
    body = sent.json()
    assert body["status"] == "submitted" and body["submission_method"] == "email"
    assert body["confirmation_reference"] == "Gmail message sent-1"
    assert len(providers.sent) == 1 and message_from_bytes(providers.sent[0])["To"] == "jobs@example.com"
    again = client.post(f"/api/v1/applications/{app['id']}/send-email",
                        json={"confirm": True, "package_hash": app["package_hash"], "to": "jobs@example.com"})
    assert again.status_code == 409 and len(providers.sent) == 1  # never twice
    events = [e["event_type"] for e in client.get(f"/api/v1/applications/{app['id']}/events").json()]
    assert "email_sent_on_user_approval" in events and events[-1] == "submitted_by_user"


def _wait(client: TestClient, status: str) -> dict:
    for _ in range(200):
        body = client.get("/api/v1/integrations").json()
        if body["microsoft_sign_in"]["status"] == status:
            return body
        time.sleep(0.02)
    raise AssertionError(client.get("/api/v1/integrations").json())


def test_microsoft_device_sign_in_and_sync(connected_client: TestClient, providers: FakeProviders) -> None:
    started = connected_client.post("/api/v1/integrations/microsoft/connect").json()
    assert started["status"] == "waiting" and started["user_code"] == "ABCD-EFGH"
    assert started["verification_uri"] == "https://microsoft.com/devicelogin"
    body = _wait(connected_client, "connected")
    assert body["microsoft"]["connected"] and body["microsoft"]["account"] == "synthetic.student@example.fi"

    synced = connected_client.post("/api/v1/integrations/microsoft/sync")
    assert synced.status_code == 200, synced.text
    assert synced.json()["emails_checked"] == 1  # the teacher's email was never downloaded
    tokens = connected_client.app.state.integrations.tokens
    assert tokens.get("microsoft-refresh-token") == "m-refresh-2"  # rotated token saved


def test_microsoft_admin_consent_message(connected_client: TestClient, providers: FakeProviders) -> None:
    providers.ms_error = "AADSTS90094: Admin approval required."
    connected_client.post("/api/v1/integrations/microsoft/connect")
    body = _wait(connected_client, "failed")
    assert "requires an administrator to approve" in body["microsoft_sign_in"]["message"]
    assert body["microsoft"]["connected"] is False


def test_jobteaser_alert_site() -> None:
    from app.adapters.job_sources.email_alerts import SITES_BY_KEY

    site = SITES_BY_KEY["alert_jobteaser"]
    assert site.verified is False
    assert site.link.match("https://utu.jobteaser.com/en/job-offers/1234567-data-analyst").group(1) == "1234567"
    assert site.link.match("https://www.jobteaser.com/fi/job-offers/7654321").group(1) == "7654321"
    assert site.link.match("https://jobteaser.com.evil.example/en/job-offers/1234567") is None


def test_gmail_slow_down_is_retried_then_reported() -> None:
    from app.adapters.mailbox import MailboxError
    from app.adapters.oauth_mail import GmailApi, GoogleClient, GoogleOAuth

    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if "oauth2.googleapis.com/token" in str(request.url):
            return httpx.Response(200, json={"access_token": "a"})
        calls["n"] += 1
        if calls["n"] <= 2:
            return httpx.Response(403, json={"error": {"message": "Quota exceeded for quota metric 'Total Query Cost'"}})
        return httpx.Response(200, json={"emailAddress": "synthetic.user@example.com"})

    oauth = GoogleOAuth(GoogleClient("c", "s"), httpx.Client(transport=httpx.MockTransport(handler)))
    api = GmailApi(oauth, "r", pause=0, backoff_scale=0)
    assert api.profile_email() == "synthetic.user@example.com" and calls["n"] == 3

    always = GmailApi(GoogleOAuth(GoogleClient("c", "s"), httpx.Client(transport=httpx.MockTransport(
        lambda r: httpx.Response(200, json={"access_token": "a"}) if "token" in str(r.url)
        else httpx.Response(429, json={})))), "r", pause=0, backoff_scale=0)
    with pytest.raises(MailboxError) as raised:
        always.profile_email()
    assert raised.value.reason == "rate_limited"
    denied = GmailApi(GoogleOAuth(GoogleClient("c", "s"), httpx.Client(transport=httpx.MockTransport(
        lambda r: httpx.Response(200, json={"access_token": "a"}) if "token" in str(r.url)
        else httpx.Response(403, json={"error": {"message": "Insufficient Permission"}})))), "r", pause=0)
    with pytest.raises(MailboxError) as raised:
        denied.profile_email()
    assert raised.value.reason == "auth_failed"
