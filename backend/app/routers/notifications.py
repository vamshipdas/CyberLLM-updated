"""
Notification API Router.
Provides endpoints for sending test alerts, inspecting notification audit logs,
querying notification delivery status per alert, and managing notification settings.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_admin, require_any_user
from app.db import get_db
from app.models.db_models import NotificationLog, Ticket, Finding as DBFinding, LogEvent, User
from app.services.log_collector import log_collector
from app.models.schemas import (
    NotificationLogOut,
    NotificationSettingsOut,
    NotificationSettingsUpdate,
    TestNotificationResponse,
)
from app.services.notifier import notifier

router = APIRouter(prefix="/notifications", tags=["Email Notifications"])


@router.post("/test", response_model=TestNotificationResponse)
def trigger_test_notification(
    user: User = Depends(require_any_user),
    db: Session = Depends(get_db),
):
    """
    Sends a clearly labeled TEST critical alert email to the configured recipients.
    Logs the attempt in NotificationLog.
    """
    print(f"[AUDIT] User '{user.username}' triggered a notification test email.")
    result = notifier.send_test_email(db=db)

    if result.get("status") == "sent":
        return TestNotificationResponse(
            status="sent",
            message=f"Test alert email successfully delivered to {', '.join(result.get('recipients', []))}.",
            recipients=result.get("recipients", []),
            log_id=result.get("log_id"),
        )
    else:
        err = result.get("error") or result.get("reason") or "Delivery failed"
        return TestNotificationResponse(
            status="failed",
            message=f"Test email failed: {err}",
            recipients=result.get("recipients", []),
            log_id=result.get("log_id"),
        )


@router.get("/log", response_model=List[NotificationLogOut])
def get_notification_logs(
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(require_any_user),
    db: Session = Depends(get_db),
):
    """
    Returns recent notification send attempts with status (sent, failed, skipped).
    """
    logs = (
        db.query(NotificationLog)
        .order_by(NotificationLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return logs


@router.get("/settings", response_model=NotificationSettingsOut)
def get_notification_settings(
    user: User = Depends(require_any_user),
    db: Session = Depends(get_db),
):
    """
    Get active notification settings (enabled, min_severity, recipients, cooldown).
    SMTP password is never returned.
    """
    settings_dict = notifier.get_settings(db)
    return NotificationSettingsOut(**settings_dict)


@router.put("/settings", response_model=NotificationSettingsOut)
def update_notification_settings(
    payload: NotificationSettingsUpdate,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Updates persistent notification settings.
    Requires ADMIN privileges. SMTP credentials cannot be altered or exposed via API.
    """
    print(f"[AUDIT] Admin '{user.username}' updated notification settings: {payload.model_dump(exclude_none=True)}")
    updated = notifier.update_settings(db, payload.model_dump(exclude_none=True))
    return NotificationSettingsOut(**updated)


@router.get("/status/{alert_id}")
def get_alert_notification_status(
    alert_id: str,
    user: User = Depends(require_any_user),
    db: Session = Depends(get_db),
):
    """
    Returns the latest notification status for a specific alert ID (sent, failed, skipped, or not_dispatched).
    Used by frontend alert cards to display email delivery indicators.
    """
    latest = (
        db.query(NotificationLog)
        .filter(NotificationLog.alert_id == alert_id)
        .order_by(NotificationLog.created_at.desc())
        .first()
    )
    if not latest:
        return {"alert_id": alert_id, "status": "none", "log": None}

    return {
        "alert_id": alert_id,
        "status": latest.status,
        "recipients": latest.recipients,
        "error_message": latest.error_message,
        "created_at": latest.created_at.isoformat(),
        "log_id": latest.id,
    }


@router.post("/resend/{alert_id}")
def resend_alert_notification(
    alert_id: str,
    user: User = Depends(require_any_user),
    db: Session = Depends(get_db),
):
    """
    Manually retries/resends email notification for a specific critical alert.
    Bypasses deduplication check.
    """
    print(f"[AUDIT] User '{user.username}' requested manual resend for alert '{alert_id}'")

    # Locate entity in DB (ticket or finding)
    ticket = db.query(Ticket).filter(Ticket.id == alert_id).first()
    if ticket:
        res = notifier.send_critical_alert(ticket, db=db, is_test=True)
        return res

    finding = db.query(DBFinding).filter(DBFinding.id == alert_id).first()
    if finding:
        res = notifier.send_critical_alert(finding, db=db, is_test=True)
        return res

    log_evt = db.query(LogEvent).filter(LogEvent.id == alert_id).first()
    if not log_evt:
        log_evt = db.query(LogEvent).filter(LogEvent.event_id == alert_id).first()
    if log_evt:
        res = notifier.send_critical_alert({
            "id": log_evt.id,
            "alert_type": "log",
            "title": f"Log Event {log_evt.event_id or ''}: {log_evt.source}".strip(),
            "severity": log_evt.severity,
            "description": log_evt.message,
            "threat_type": "log_anomaly",
        }, db=db, is_test=True)
        return res

    # Also check in-memory live buffer
    match = next((e for e in log_collector.buffer if e.get("id") == alert_id or str(e.get("event_id")) == alert_id), None)
    if match:
        res = notifier.send_critical_alert({
            "id": match.get("id", alert_id),
            "alert_type": "log",
            "title": f"Log Event {match.get('event_id') or ''}: {match.get('source')}".strip(),
            "severity": match.get("severity", "high"),
            "description": match.get("message", ""),
            "threat_type": "log_anomaly",
        }, db=db, is_test=True)
        return res

    raise HTTPException(status_code=404, detail=f"Alert with ID '{alert_id}' not found.")
