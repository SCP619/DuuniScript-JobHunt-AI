"""Audit logging. Details hold field names and state values only, never personal content."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.persistence.models import AuditEvent

USER_ACTOR = "user"


def record(
    session: Session,
    action: str,
    entity_type: str,
    entity_id: str | None,
    details: dict[str, Any] | None = None,
    actor: str = USER_ACTOR,
    result: str = "success",
) -> None:
    session.add(
        AuditEvent(
            actor=actor,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            result=result,
            details=details,
        )
    )
