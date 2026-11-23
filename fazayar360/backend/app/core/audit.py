import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import Request
from sqlalchemy.orm import Session

from ..models import AuditLog

log = logging.getLogger("fazayar.audit")


def write_audit(db: Session, actor, action: str, entity_type: str, entity_id=None,
                before=None, after=None, request_id: str | None = None, ip: str | None = None) -> None:
    entry = AuditLog(
        actor_id=actor.id if actor else None,
        actor_name=actor.display_name if actor else None,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id else None,
        before=json.dumps(before, ensure_ascii=False, default=str) if before else None,
        after=json.dumps(after, ensure_ascii=False, default=str) if after else None,
        ip=ip,
        request_id=request_id or uuid.uuid4().hex[:12],
        created_at=datetime.now(timezone.utc),
    )
    db.add(entry)
