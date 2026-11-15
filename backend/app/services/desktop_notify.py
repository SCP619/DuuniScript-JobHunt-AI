"""Windows desktop notifications for new in-app notifications (good matches, near deadlines…).

Uses the Windows notification system through ``winrt`` (no extra program, nothing online). Each
in-app notification is shown on the desktop once (``toasted_at``); at most three per check, with
a summary when there are more. Off with ``DESKTOP_NOTIFICATIONS=false`` or on other systems.
"""

from __future__ import annotations

import logging
from xml.sax.saxutils import escape

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.persistence.models import Notification, utcnow
from app.services import notification_service

logger = logging.getLogger("duuniscript.desktop")
# Windows needs an app identity for notifications; PowerShell's is always registered.
APP_ID = "{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\\WindowsPowerShell\\v1.0\\powershell.exe"
MAX_PER_CHECK = 3
KINDS = ("good_match", "deadline_soon", "ready_not_sent", "follow_up")


def windows_toast(title: str, message: str, link: str | None = None) -> bool:
    try:
        from winrt.windows.data.xml.dom import XmlDocument
        from winrt.windows.ui.notifications import ToastNotification, ToastNotificationManager
    except Exception:  # noqa: BLE001 - not Windows or packages missing
        return False
    launch = f' activationType="protocol" launch="{escape(link)}"' if link else ""
    xml = XmlDocument()
    xml.load_xml(
        f"<toast{launch}><visual><binding template='ToastGeneric'>"
        f"<text>{escape(title[:120])}</text><text>{escape(message[:240])}</text>"
        "</binding></visual></toast>"
    )
    try:
        ToastNotificationManager.create_toast_notifier_with_id(APP_ID).show(ToastNotification(xml))
    except Exception as exc:  # noqa: BLE001
        logger.info("Desktop notification not shown: %s", type(exc).__name__)
        return False
    return True


def check(session: Session, app_url: str, toast=windows_toast) -> int:  # noqa: ANN001
    notification_service.refresh(session)
    pending = list(session.scalars(select(Notification).where(
        Notification.toasted_at.is_(None), Notification.dismissed_at.is_(None), Notification.read_at.is_(None),
        Notification.kind.in_(KINDS)).order_by(Notification.created_at)))
    if not pending:
        return 0
    shown = 0
    for item in pending[:MAX_PER_CHECK]:
        if toast(item.title, item.message, f"{app_url}{item.link}"):
            shown += 1
    if len(pending) > MAX_PER_CHECK:
        if toast(f"{len(pending) - MAX_PER_CHECK} more in DuuniScript", "Open DuuniScript to see all notifications.",
                 app_url):
            shown += 1
    now = utcnow()
    for item in pending:
        item.toasted_at = now  # shown once, even when more than the first three were waiting
    session.commit()
    return shown
