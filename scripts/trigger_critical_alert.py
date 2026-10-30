import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.db import SessionLocal
from app.models.db_models import Ticket
from app.services.notifier import notifier
import uuid
from datetime import datetime, timezone

def trigger_alert():
    print("[*] Connecting to database...")
    db = SessionLocal()
    ticket_id = f"TKT-{uuid.uuid4().hex[:10].upper()}"

    ticket = Ticket(
        id=ticket_id,
        title="Ransomware Encryption Activity Detected on Production Database",
        threat_type="ransomware",
        severity="critical",
        status="open",
        source_ip="198.51.100.45",
        target_host="db-prod-primary.corp",
        description="Massive unauthorized file extension modification (.locked) and Shadow Copy deletion commands detected in PowerShell execution logs."
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    print(f"[+] Created CRITICAL ticket: {ticket_id}")

    print("[*] Triggering critical email notification dispatcher...")
    result = notifier.send_critical_alert(ticket, db=db)
    print(f"[+] Result: {result}")
    db.close()

if __name__ == "__main__":
    trigger_alert()
