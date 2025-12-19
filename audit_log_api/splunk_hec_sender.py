"""
splunk_hec_sender.py - Mock Splunk HTTP Event Collector (HEC) Sender

This module provides a reusable interface for sending events to Splunk HEC.
Currently mocked for development/demo purposes.

In production, you would:
1. Configure SPLUNK_HEC_URL and SPLUNK_HEC_TOKEN
2. Uncomment the actual HTTP POST logic
3. Add retry logic with exponential backoff
4. Consider batching events for efficiency

Splunk HEC Documentation:
https://docs.splunk.com/Documentation/Splunk/latest/Data/UsetheHTTPEventCollector
"""

import os
import json
import time
from typing import List, Dict, Any
from dataclasses import dataclass, field

# ========== CONFIGURATION ==========
# These would be set in .env for production
SPLUNK_HEC_URL = os.getenv("SPLUNK_HEC_URL", "https://splunk.example.com:8088/services/collector/event")
SPLUNK_HEC_TOKEN = os.getenv("SPLUNK_HEC_TOKEN", "mock-token")
SPLUNK_INDEX = os.getenv("SPLUNK_INDEX", "devin_logs")
SPLUNK_SOURCE = os.getenv("SPLUNK_SOURCE", "devin_api")


@dataclass
class SplunkEvent:
    """
    Represents a single event to send to Splunk HEC.
    
    Fields:
        event: The actual event data (dict)
        sourcetype: Splunk sourcetype (e.g., "devin:audit_log")
        index: Target Splunk index (optional, uses default if not set)
        time: Event timestamp as Unix epoch (optional)
        host: Source host (optional)
    """
    event: Dict[str, Any]
    sourcetype: str
    index: str = SPLUNK_INDEX
    time: float = field(default_factory=time.time)
    host: str = "devin-api"

    def to_hec_format(self) -> Dict[str, Any]:
        """Convert to Splunk HEC JSON format."""
        return {
            "time": self.time,
            "host": self.host,
            "source": SPLUNK_SOURCE,
            "sourcetype": self.sourcetype,
            "index": self.index,
            "event": self.event
        }


def send_to_splunk(events: List[SplunkEvent], dry_run: bool = True) -> Dict[str, Any]:
    """
    Send events to Splunk HEC.
    
    Args:
        events: List of SplunkEvent objects to send
        dry_run: If True, just log what would be sent (default: True for safety)
    
    Returns:
        Dict with status and details
    
    Example:
        events = [
            SplunkEvent(
                event={"action": "login", "user_email": "user@example.com"},
                sourcetype="devin:audit_log"
            )
        ]
        result = send_to_splunk(events, dry_run=False)
    """
    if not events:
        return {"status": "success", "message": "No events to send", "count": 0}

    # Convert events to HEC format
    hec_payloads = [e.to_hec_format() for e in events]
    
    # Calculate payload size for volume estimation
    payload_bytes = sum(len(json.dumps(p)) for p in hec_payloads)
    
    if dry_run:
        # MOCK MODE: Just log what would be sent
        print(f"\n{'='*60}")
        print(f"[MOCK SPLUNK HEC] Would send {len(events)} events")
        print(f"[MOCK SPLUNK HEC] Total payload size: {payload_bytes:,} bytes")
        print(f"[MOCK SPLUNK HEC] Target: {SPLUNK_HEC_URL}")
        print(f"[MOCK SPLUNK HEC] Index: {SPLUNK_INDEX}")
        print(f"{'='*60}")
        
        # Show first event as sample
        if events:
            print("\nSample event (first):")
            print(json.dumps(hec_payloads[0], indent=2, default=str))
        
        return {
            "status": "mock_success",
            "message": "Dry run - events logged but not sent",
            "count": len(events),
            "bytes": payload_bytes
        }
    
    # PRODUCTION MODE: Actually send to Splunk
    # Uncomment and configure for real usage:
    #
    # import requests
    # 
    # headers = {
    #     "Authorization": f"Splunk {SPLUNK_HEC_TOKEN}",
    #     "Content-Type": "application/json"
    # }
    # 
    # # Send events as newline-delimited JSON (batch mode)
    # payload = "\n".join(json.dumps(p) for p in hec_payloads)
    # 
    # response = requests.post(
    #     SPLUNK_HEC_URL,
    #     headers=headers,
    #     data=payload,
    #     timeout=30
    # )
    # response.raise_for_status()
    # 
    # return {
    #     "status": "success",
    #     "count": len(events),
    #     "bytes": payload_bytes,
    #     "splunk_response": response.json()
    # }
    
    print(f"[SPLUNK HEC] Sent {len(events)} events ({payload_bytes:,} bytes)")
    return {
        "status": "success",
        "count": len(events),
        "bytes": payload_bytes
    }


def create_audit_log_event(audit_log: Dict[str, Any]) -> SplunkEvent:
    """
    Helper to create a Splunk event from a Devin audit log entry.
    
    This normalizes the audit log data and adds consistent metadata.
    """
    return SplunkEvent(
        event={
            "event_type": "devin_audit_log",
            "audit_log_id": audit_log.get("audit_log_id"),
            "action": audit_log.get("action"),
            "created_at": audit_log.get("created_at"),
            "org_id": audit_log.get("org_id"),
            "user_id": audit_log.get("user_id"),
            "user_email": audit_log.get("user_email"),
            "service_user_id": audit_log.get("service_user_id"),
            "service_user_name": audit_log.get("service_user_name"),
            "data": audit_log.get("data", {})
        },
        sourcetype="devin:audit_log",
        time=audit_log.get("created_at", time.time())
    )


def create_session_event(session: Dict[str, Any], include_analysis: bool = False) -> SplunkEvent:
    """
    Helper to create a Splunk event from a Devin session.
    
    Args:
        session: Session data from v2 API
        include_analysis: If True, include session_analysis (can be large)
    """
    event_data = {
        "event_type": "devin_session",
        "session_id": session.get("session_id"),
        "org_id": session.get("org_id"),
        "user_id": session.get("user_id"),
        "status": session.get("status"),
        "created_at": session.get("created_at"),
        "updated_at": session.get("updated_at"),
        "acus_consumed": session.get("acus_consumed"),
        "title": session.get("title"),
        "tags": session.get("tags", []),
        "pull_requests": session.get("pull_requests", []),
        "url": session.get("url")
    }
    
    # Optionally include the initial prompt (useful for investigation)
    if session.get("initial_user_message"):
        event_data["initial_user_message"] = session.get("initial_user_message")
    
    # Only include analysis if explicitly requested (it's large)
    if include_analysis and session.get("session_analysis"):
        event_data["session_analysis"] = session.get("session_analysis")
    
    return SplunkEvent(
        event=event_data,
        sourcetype="devin:session",
        time=time.time()  # Use current time for session updates
    )


# ========== DEMO / TEST ==========
if __name__ == "__main__":
    # Demo: Create and "send" sample events
    print("Splunk HEC Sender - Demo Mode\n")
    
    sample_audit_log = {
        "audit_log_id": "abc123",
        "action": "login",
        "created_at": int(time.time()),
        "org_id": "org-456",
        "user_id": "user-789",
        "user_email": "developer@example.com",
        "data": {"ip_address": "10.0.0.1"}
    }
    
    sample_session = {
        "session_id": "sess-001",
        "org_id": "org-456",
        "user_id": "user-789",
        "status": "running",
        "created_at": "2024-01-15T10:30:00Z",
        "updated_at": "2024-01-15T11:00:00Z",
        "acus_consumed": 5,
        "title": "Fix login bug",
        "tags": ["bugfix", "auth"],
        "pull_requests": [{"url": "https://github.com/org/repo/pull/123", "state": "open"}],
        "initial_user_message": "Please fix the login timeout issue in auth.py"
    }
    
    events = [
        create_audit_log_event(sample_audit_log),
        create_session_event(sample_session)
    ]
    
    result = send_to_splunk(events, dry_run=True)
    print(f"\nResult: {result}")
