"""Read-only access to the mailbox label that holds job alert emails.

- IMAP over TLS with certificate checks; the label is opened read-only and messages are
  fetched with BODY.PEEK, so nothing is marked read, moved or deleted.
- The password comes from Windows Credential Manager (``keyring``), never from files or
  settings. For Gmail it is an app password, which can be revoked at any time.
- Already processed emails are skipped by Message-ID before their bodies are downloaded.
"""

from __future__ import annotations

import imaplib
import re
import socket
import ssl
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import date
from typing import Protocol

KEYRING_SERVICE = "DuuniScript mailbox"
MAX_MESSAGES_PER_SYNC = 500
MAX_MESSAGE_BYTES = 5 * 1024 * 1024
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


class MailboxError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class AlertMailbox(Protocol):
    def fetch_since(self, since: date, skip: Callable[[str], bool]) -> Iterator[bytes]:
        """Raw emails received on or after ``since`` whose Message-ID ``skip`` does not reject."""
        ...


def get_password(user: str) -> str | None:
    try:
        import keyring

        return keyring.get_password(KEYRING_SERVICE, user)
    except Exception:  # noqa: BLE001 - no usable credential store means "not set up"
        return None


def set_password(user: str, password: str) -> None:
    import keyring

    keyring.set_password(KEYRING_SERVICE, user, password)


def imap_date(day: date) -> str:
    return f"{day.day:02d}-{_MONTHS[day.month - 1]}-{day.year}"


def _quote(folder: str) -> str:
    return '"' + folder.replace("\\", "\\\\").replace('"', '\\"') + '"'


@dataclass
class ImapMailbox:
    host: str
    port: int
    user: str
    password: str
    folder: str
    timeout: float = 30.0

    def fetch_since(self, since: date, skip: Callable[[str], bool]) -> Iterator[bytes]:
        try:
            client = imaplib.IMAP4_SSL(
                self.host, self.port, ssl_context=ssl.create_default_context(), timeout=self.timeout
            )
        except (socket.timeout, TimeoutError) as exc:
            raise MailboxError("timeout") from exc
        except (OSError, imaplib.IMAP4.error) as exc:
            raise MailboxError("connection_failed") from exc
        try:
            try:
                client.login(self.user, self.password)
            except imaplib.IMAP4.error as exc:
                raise MailboxError("auth_failed") from exc
            status, _ = client.select(_quote(self.folder), readonly=True)
            if status != "OK":
                raise MailboxError("folder_missing")
            status, data = client.search(None, "SINCE", imap_date(since))
            if status != "OK":
                raise MailboxError("search_failed")
            numbers = (data[0] or b"").split()[-MAX_MESSAGES_PER_SYNC:]
            for number in numbers:
                raw = self._fetch_one(client, number, skip)
                if raw is not None:
                    yield raw
        except (socket.timeout, TimeoutError) as exc:
            raise MailboxError("timeout") from exc
        except (OSError, imaplib.IMAP4.abort) as exc:
            raise MailboxError("connection_failed") from exc
        finally:
            try:
                client.logout()
            except Exception:  # noqa: BLE001
                pass

    @staticmethod
    def _fetch_one(client: imaplib.IMAP4_SSL, number: bytes, skip: Callable[[str], bool]) -> bytes | None:
        status, data = client.fetch(number, "(RFC822.SIZE BODY.PEEK[HEADER.FIELDS (MESSAGE-ID)])")
        if status != "OK" or not data or not isinstance(data[0], tuple):
            return None
        # Servers may put RFC822.SIZE before or after the header literal.
        envelope = b" ".join(item[0] if isinstance(item, tuple) else item for item in data if item)
        size = re.search(rb"RFC822\.SIZE (\d+)", envelope)
        if size and int(size.group(1)) > MAX_MESSAGE_BYTES:
            return None
        message_id = re.search(rb"<[^>\r\n]{1,250}>", data[0][1] or b"")
        if message_id and skip(message_id.group(0).decode("ascii", "replace")):
            return None
        status, data = client.fetch(number, "(BODY.PEEK[])")
        if status != "OK" or not data or not isinstance(data[0], tuple):
            return None
        return data[0][1]
