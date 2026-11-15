"""Signing in to DuuniScript (PRD non-functional: authenticated local API).

- Until a passphrase is created the API stays open, as before (it only listens on 127.0.0.1).
- Once it exists, every ``/api/v1`` request except ``/api/v1/auth/*`` needs
  ``Authorization: Bearer <session token>``; ``/health`` stays open.
- The passphrase is stored as a salted scrypt hash; session tokens are random and stored only
  as SHA-256 hashes. Sessions expire after ``AUTH_SESSION_DAYS``.
- Five wrong passphrases in a row lock sign-in for 60 seconds.
- Changing the passphrase signs out every other session.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.persistence.models import AppCredential, AppSession, utcnow
from app.services import audit

MIN_LENGTH = 10
SCRYPT = {"n": 2**14, "r": 8, "p": 1, "dklen": 32}
MAX_FAILURES = 5
LOCKOUT_SECONDS = 60

_failures = 0
_locked_until = 0.0
_lock = threading.Lock()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, **SCRYPT)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(digest).decode()


def check_password(password: str, stored: str) -> bool:
    try:
        _, salt_b64, digest_b64 = stored.split("$")
        expected = base64.b64decode(digest_b64)
        digest = hashlib.scrypt(password.encode("utf-8"), salt=base64.b64decode(salt_b64), **SCRYPT)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest, expected)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def credential(session: Session) -> AppCredential | None:
    return session.scalar(select(AppCredential).limit(1))


def password_set(session: Session) -> bool:
    return credential(session) is not None


def _validate(password: str) -> None:
    if len(password) < MIN_LENGTH:
        raise AppError(422, "password_too_short", f"Use at least {MIN_LENGTH} characters.")


def _new_session(session: Session, days: int) -> tuple[str, datetime]:
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(days=days)
    session.add(AppSession(token_hash=_token_hash(token), expires_at=expires))
    return token, expires


def setup(session: Session, password: str, days: int) -> tuple[str, datetime]:
    if password_set(session):
        raise AppError(409, "password_already_set", "A sign-in passphrase already exists. Sign in, or change it.")
    _validate(password)
    session.add(AppCredential(password_hash=hash_password(password)))
    token, expires = _new_session(session, days)
    audit.record(session, "auth.password_created", "app_credential", None)
    session.commit()
    return token, expires


def login(session: Session, password: str, days: int) -> tuple[str, datetime]:
    global _failures, _locked_until
    with _lock:
        if time.monotonic() < _locked_until:
            raise AppError(429, "sign_in_locked", "Too many wrong attempts. Wait a minute and try again.")
    stored = credential(session)
    if stored is None:
        raise AppError(409, "password_not_set", "Create a sign-in passphrase first.")
    if not check_password(password, stored.password_hash):
        with _lock:
            _failures += 1
            if _failures >= MAX_FAILURES:
                _locked_until = time.monotonic() + LOCKOUT_SECONDS
                _failures = 0
        audit.record(session, "auth.sign_in", "app_session", None, result="failure")
        session.commit()
        raise AppError(401, "wrong_password", "That passphrase is not correct.")
    with _lock:
        _failures = 0
    session.execute(delete(AppSession).where(AppSession.expires_at < datetime.now(timezone.utc)))
    token, expires = _new_session(session, days)
    audit.record(session, "auth.sign_in", "app_session", None)
    session.commit()
    return token, expires


def session_for(session: Session, token: str | None) -> AppSession | None:
    if not token:
        return None
    found = session.scalar(select(AppSession).where(AppSession.token_hash == _token_hash(token)))
    if found is None or found.expires_at <= datetime.now(timezone.utc):
        return None
    now = utcnow()
    if (now - found.last_used_at) > timedelta(minutes=5):
        found.last_used_at = now
        session.commit()
    return found


def logout(session: Session, token: str | None) -> None:
    if token:
        session.execute(delete(AppSession).where(AppSession.token_hash == _token_hash(token)))
        audit.record(session, "auth.sign_out", "app_session", None)
        session.commit()


def change(session: Session, token: str | None, current: str, new: str) -> None:
    stored = credential(session)
    if stored is None or not check_password(current, stored.password_hash):
        raise AppError(401, "wrong_password", "The current passphrase is not correct.")
    _validate(new)
    stored.password_hash = hash_password(new)
    stored.updated_at = utcnow()
    keep = _token_hash(token) if token else ""
    session.execute(delete(AppSession).where(AppSession.token_hash != keep))
    audit.record(session, "auth.password_changed", "app_credential", None)
    session.commit()


def reset_lockout() -> None:
    """For tests."""
    global _failures, _locked_until
    with _lock:
        _failures, _locked_until = 0, 0.0
