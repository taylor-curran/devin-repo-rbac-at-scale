"""
audit_log_poller.py - Poll Devin v3 Audit Logs and Send to Splunk

This script demonstrates how to:
1. Poll the v3beta1 audit logs API with time-bounded queries
2. Filter for security-relevant actions
3. Handle pagination with cursors
4. Maintain state (watermark) to avoid re-pulling old data
5. Send events to Splunk HEC

API Reference:
https://docs.devin.ai/api-reference/v3/audit-logs/enterprise-audit-logs

Authentication:
- Requires Service User credential (prefix: cog_)
- Set via DEVIN_SERVICE_ACCOUNT_API_KEY environment variable

Key API behaviors:
- time_after/time_before are Unix timestamps (seconds, UTC)
- If you provide time_before, you must also provide time_after
- Time range must be <= 100 days
- Pagination uses 'after' cursor and 'has_next_page' flag
- Max 200 items per page (via 'first' parameter)
"""

import os
import json
import time
import requests
from datetime import datetime
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

# Import our mock Splunk sender
from splunk_hec_sender import send_to_splunk, create_audit_log_event

load_dotenv()

# ========== CONFIGURATION ==========
API_KEY = os.getenv("DEVIN_SERVICE_ACCOUNT_API_KEY")
BASE_URL = "https://api.devin.ai/v3beta1"
STATE_FILE = "audit_poller_state.json"

# Actions to always ingest (high-signal, security-relevant)
# See full list: https://docs.devin.ai/api-reference/v3/audit-logs/enterprise-audit-logs
SECURITY_ACTIONS = [
    "ai_guardrail_violation",  # DLP-style triggers - CRITICAL
    "login",                   # User authentication
    "create_session",          # Session lifecycle
    "terminate_session",
    "sleep_session",
]

# Optional: Additional actions for governance/compliance
GOVERNANCE_ACTIONS = [
    "create_github_integration",
    "delete_github_integration",
    "create_gitlab_integration",
    "delete_gitlab_integration",
    "mcp_server_install",
    "mcp_server_enable",
    "mcp_server_disable",
]

# Combine based on your needs
ACTIONS_TO_POLL = SECURITY_ACTIONS  # Add + GOVERNANCE_ACTIONS if needed


# ========== STATE MANAGEMENT ==========
def load_state() -> Dict[str, Any]:
    """
    Load polling state from file.
    
    State tracks:
    - last_time_after: Unix timestamp of last successful poll
    - seen_ids: Set of audit_log_ids already processed (for deduplication)
    """
    if not os.path.exists(STATE_FILE):
        # Initialize: start from 60 seconds ago
        return {
            "last_time_after": int(time.time()) - 60,
            "seen_ids": []
        }
    
    with open(STATE_FILE, "r") as f:
        return json.load(f)


def save_state(state: Dict[str, Any]) -> None:
    """Save polling state to file."""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)
    print(f"[STATE] Saved. Watermark: {datetime.fromtimestamp(state['last_time_after'])}")


# ========== API CALLS ==========
def fetch_audit_logs(
    time_after: int,
    time_before: int,
    action: Optional[str] = None,
    cursor: Optional[str] = None
) -> Dict[str, Any]:
    """
    Fetch audit logs from v3beta1 API.
    
    Args:
        time_after: Start of time window (Unix seconds, UTC)
        time_before: End of time window (Unix seconds, UTC)
        action: Optional action type to filter
        cursor: Pagination cursor from previous response
    
    Returns:
        API response with items, has_next_page, end_cursor
    """
    url = f"{BASE_URL}/enterprise/audit-logs"
    
    params = {
        "time_after": time_after,
        "time_before": time_before,
        "first": 200  # Max page size
    }
    
    if action:
        params["action"] = action
    
    if cursor:
        params["after"] = cursor
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    response = requests.get(url, headers=headers, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def poll_all_actions(
    time_after: int,
    time_before: int,
    actions: List[str],
    seen_ids: set
) -> List[Dict[str, Any]]:
    """
    Poll audit logs for multiple action types.
    
    Args:
        time_after: Start of time window
        time_before: End of time window
        actions: List of action types to fetch
        seen_ids: Set of already-processed audit_log_ids for deduplication
    
    Returns:
        List of new (unseen) audit log entries
    """
    all_logs = []
    
    for action in actions:
        print(f"[POLL] Fetching '{action}' logs...")
        cursor = None
        action_count = 0
        
        while True:
            try:
                page = fetch_audit_logs(time_after, time_before, action, cursor)
            except requests.exceptions.HTTPError as e:
                print(f"[ERROR] Failed to fetch {action}: {e}")
                break
            
            items = page.get("items", [])
            
            for item in items:
                log_id = item.get("audit_log_id")
                
                # Deduplicate: skip if we've already seen this ID
                if log_id in seen_ids:
                    continue
                
                all_logs.append(item)
                seen_ids.add(log_id)
                action_count += 1
            
            # Check for more pages
            if not page.get("has_next_page"):
                break
            
            cursor = page.get("end_cursor")
        
        if action_count > 0:
            print(f"[POLL] Found {action_count} new '{action}' events")
    
    return all_logs


# ========== MAIN POLLER ==========
def run_poll_cycle(dry_run: bool = True) -> Dict[str, Any]:
    """
    Execute one polling cycle.
    
    This is designed to be called periodically (e.g., every 5-10 seconds).
    
    Args:
        dry_run: If True, don't actually send to Splunk
    
    Returns:
        Summary of what was polled/sent
    """
    if not API_KEY:
        raise ValueError("DEVIN_SERVICE_ACCOUNT_API_KEY not set")
    
    # Load state
    state = load_state()
    time_after = state["last_time_after"]
    seen_ids = set(state.get("seen_ids", []))
    
    # Time window: from last watermark to now
    time_before = int(time.time())
    
    print(f"\n{'='*60}")
    print(f"[POLL] Audit Log Polling Cycle")
    print(f"[POLL] Window: {datetime.fromtimestamp(time_after)} → {datetime.fromtimestamp(time_before)}")
    print(f"[POLL] Actions: {ACTIONS_TO_POLL}")
    print(f"{'='*60}")
    
    # Fetch logs for all configured actions
    new_logs = poll_all_actions(time_after, time_before, ACTIONS_TO_POLL, seen_ids)
    
    if not new_logs:
        print("[POLL] No new events found")
        # Still advance watermark (with small overlap to handle clock skew)
        state["last_time_after"] = time_before - 5
        save_state(state)
        return {"status": "success", "events_found": 0, "events_sent": 0}
    
    print(f"\n[POLL] Found {len(new_logs)} total new events")
    
    # Convert to Splunk events
    splunk_events = [create_audit_log_event(log) for log in new_logs]
    
    # Send to Splunk
    result = send_to_splunk(splunk_events, dry_run=dry_run)
    
    # Update state
    state["last_time_after"] = time_before - 5  # Small overlap for safety
    state["seen_ids"] = list(seen_ids)[-10000:]  # Keep last 10k IDs to limit file size
    save_state(state)
    
    return {
        "status": "success",
        "events_found": len(new_logs),
        "events_sent": result.get("count", 0),
        "bytes": result.get("bytes", 0)
    }


# ========== CONTINUOUS POLLING (Optional) ==========
def run_continuous(interval_seconds: int = 10, dry_run: bool = True):
    """
    Run the poller continuously.
    
    In production, you might run this as a systemd service, 
    Kubernetes CronJob, or scheduled task.
    
    Args:
        interval_seconds: Seconds between poll cycles
        dry_run: If True, mock the Splunk send
    """
    print(f"Starting continuous polling (interval: {interval_seconds}s)")
    print("Press Ctrl+C to stop\n")
    
    try:
        while True:
            try:
                result = run_poll_cycle(dry_run=dry_run)
                print(f"[CYCLE] Complete: {result}")
            except Exception as e:
                print(f"[ERROR] Poll cycle failed: {e}")
            
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        print("\n[STOP] Polling stopped by user")


# ========== ENTRY POINT ==========
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Poll Devin audit logs and send to Splunk")
    parser.add_argument("--once", action="store_true", help="Run single poll cycle and exit")
    parser.add_argument("--interval", type=int, default=10, help="Seconds between polls (default: 10)")
    parser.add_argument("--live", action="store_true", help="Actually send to Splunk (default: dry run)")
    args = parser.parse_args()
    
    dry_run = not args.live
    
    if args.once:
        result = run_poll_cycle(dry_run=dry_run)
        print(f"\nFinal result: {result}")
    else:
        run_continuous(interval_seconds=args.interval, dry_run=dry_run)
