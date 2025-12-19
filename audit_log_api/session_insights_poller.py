"""
session_insights_poller.py - Poll Devin v2 Session Insights for Usage Analytics

This script demonstrates how to:
1. Poll the v2 enterprise sessions insights API
2. Track session lifecycle (created, updated, status changes)
3. Capture ACU consumption, PR activity, and session outcomes
4. Send lightweight session events to Splunk

API Reference:
https://docs.devin.ai/api-reference/v2/sessions/list-enterprise-sessions-insights

Authentication:
- Requires Personal API Key for Enterprise Admin (prefix: apk_user_)
- Set via DEVIN_ADMIN_USER_API_KEY environment variable

Use Cases:
- Adoption dashboards (who's using Devin, how often)
- ACU burn rate analytics
- Outcome tracking (PR creation, merge rates)
- Identifying sessions that may need attention

Note: This does NOT store full session_analysis by default.
That's expensive and should be pulled on-demand (see incident_drilldown.py).
"""

import os
import json
import time
import requests
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any, Tuple
from dotenv import load_dotenv

# Import our mock Splunk sender
from splunk_hec_sender import send_to_splunk, create_session_event

load_dotenv()

# ========== CONFIGURATION ==========
API_KEY = os.getenv("DEVIN_ADMIN_USER_API_KEY")
BASE_URL = "https://api.devin.ai/v2"
STATE_FILE = "session_poller_state.json"

# How far back to look on first run (hours)
INITIAL_LOOKBACK_HOURS = 24


# ========== STATE MANAGEMENT ==========
def load_state() -> Dict[str, Any]:
    """
    Load polling state from file.
    
    State tracks:
    - last_updated_after: ISO timestamp for updated_date_from filter
    - seen_sessions: Dict of session_id -> last_seen_updated_at
    """
    if not os.path.exists(STATE_FILE):
        # Initialize: look back INITIAL_LOOKBACK_HOURS
        lookback = datetime.now(timezone.utc) - timedelta(hours=INITIAL_LOOKBACK_HOURS)
        return {
            "last_updated_after": lookback.isoformat(),
            "seen_sessions": {}
        }
    
    with open(STATE_FILE, "r") as f:
        return json.load(f)


def save_state(state: Dict[str, Any]) -> None:
    """Save polling state to file."""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)
    print(f"[STATE] Saved. Watermark: {state['last_updated_after']}")


# ========== API CALLS ==========
def fetch_session_insights(
    updated_date_from: Optional[str] = None,
    updated_date_to: Optional[str] = None,
    skip: int = 0,
    limit: int = 100
) -> Dict[str, Any]:
    """
    Fetch session insights from v2 API.
    
    Args:
        updated_date_from: ISO datetime string for filtering
        updated_date_to: ISO datetime string for filtering
        skip: Pagination offset
        limit: Page size (max 200)
    
    Returns:
        API response with items, has_more, total, next_cursor
    """
    url = f"{BASE_URL}/enterprise/sessions/insights"
    
    params = {
        "skip": skip,
        "limit": limit
    }
    
    if updated_date_from:
        params["updated_date_from"] = updated_date_from
    if updated_date_to:
        params["updated_date_to"] = updated_date_to
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    response = requests.get(url, headers=headers, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def poll_updated_sessions(
    updated_after: str,
    seen_sessions: Dict[str, str]
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """
    Poll for sessions updated since the watermark.
    
    Uses (session_id, updated_at) for deduplication - we only emit
    an event if the session has actually been updated since we last saw it.
    
    Args:
        updated_after: ISO datetime string
        seen_sessions: Dict mapping session_id -> last seen updated_at
    
    Returns:
        Tuple of (new/updated sessions list, updated seen_sessions dict)
    """
    new_sessions = []
    skip = 0
    limit = 100
    
    print(f"[POLL] Fetching sessions updated since {updated_after}")
    
    while True:
        try:
            page = fetch_session_insights(
                updated_date_from=updated_after,
                skip=skip,
                limit=limit
            )
        except requests.exceptions.HTTPError as e:
            print(f"[ERROR] Failed to fetch sessions: {e}")
            break
        
        items = page.get("items", [])
        
        for session in items:
            session_id = session.get("session_id")
            updated_at = session.get("updated_at")
            
            # Check if this is a new update
            last_seen = seen_sessions.get(session_id)
            if last_seen == updated_at:
                # No change since we last saw it
                continue
            
            new_sessions.append(session)
            seen_sessions[session_id] = updated_at
        
        # Check for more pages
        if not page.get("has_more"):
            break
        
        skip += limit
        
        # Safety limit to avoid infinite loops
        if skip > 10000:
            print("[WARN] Hit pagination safety limit")
            break
    
    return new_sessions, seen_sessions


# ========== ANALYTICS HELPERS ==========
def summarize_sessions(sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate summary statistics for a batch of sessions.
    
    Useful for quick visibility into what's happening.
    """
    if not sessions:
        return {}
    
    total_acus = sum(s.get("acus_consumed", 0) for s in sessions)
    
    status_counts = {}
    for s in sessions:
        status = s.get("status", "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
    
    prs_created = sum(len(s.get("pull_requests", [])) for s in sessions)
    
    return {
        "session_count": len(sessions),
        "total_acus": total_acus,
        "avg_acus": round(total_acus / len(sessions), 2) if sessions else 0,
        "status_breakdown": status_counts,
        "prs_created": prs_created
    }


# ========== MAIN POLLER ==========
def run_poll_cycle(dry_run: bool = True, include_analysis: bool = False) -> Dict[str, Any]:
    """
    Execute one polling cycle for session insights.
    
    Args:
        dry_run: If True, don't actually send to Splunk
        include_analysis: If True, include session_analysis in Splunk events (expensive)
    
    Returns:
        Summary of what was polled/sent
    """
    if not API_KEY:
        raise ValueError("DEVIN_ADMIN_USER_API_KEY not set")
    
    # Load state
    state = load_state()
    updated_after = state["last_updated_after"]
    seen_sessions = state.get("seen_sessions", {})
    
    print(f"\n{'='*60}")
    print(f"[POLL] Session Insights Polling Cycle")
    print(f"[POLL] Looking for updates since: {updated_after}")
    print(f"[POLL] Tracking {len(seen_sessions)} known sessions")
    print(f"{'='*60}")
    
    # Fetch updated sessions
    new_sessions, seen_sessions = poll_updated_sessions(updated_after, seen_sessions)
    
    if not new_sessions:
        print("[POLL] No new/updated sessions found")
        # Update watermark to now
        state["last_updated_after"] = datetime.now(timezone.utc).isoformat()
        state["seen_sessions"] = seen_sessions
        save_state(state)
        return {"status": "success", "sessions_found": 0, "events_sent": 0}
    
    # Summarize what we found
    summary = summarize_sessions(new_sessions)
    print(f"\n[POLL] Found {len(new_sessions)} new/updated sessions")
    print(f"[POLL] Summary: {json.dumps(summary, indent=2)}")
    
    # Convert to Splunk events
    splunk_events = [
        create_session_event(s, include_analysis=include_analysis) 
        for s in new_sessions
    ]
    
    # Send to Splunk
    result = send_to_splunk(splunk_events, dry_run=dry_run)
    
    # Update state
    state["last_updated_after"] = datetime.now(timezone.utc).isoformat()
    state["seen_sessions"] = seen_sessions
    
    # Trim seen_sessions to avoid unbounded growth (keep last 50k)
    if len(state["seen_sessions"]) > 50000:
        # Keep most recent entries (simple approach: just truncate)
        print("[WARN] Trimming seen_sessions cache")
        items = list(state["seen_sessions"].items())[-50000:]
        state["seen_sessions"] = dict(items)
    
    save_state(state)
    
    return {
        "status": "success",
        "sessions_found": len(new_sessions),
        "events_sent": result.get("count", 0),
        "bytes": result.get("bytes", 0),
        "summary": summary
    }


# ========== CONTINUOUS POLLING ==========
def run_continuous(interval_seconds: int = 60, dry_run: bool = True):
    """
    Run the poller continuously.
    
    Session insights don't change as frequently as audit logs,
    so a longer interval (60s) is usually sufficient.
    """
    print(f"Starting continuous session polling (interval: {interval_seconds}s)")
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
    
    parser = argparse.ArgumentParser(description="Poll Devin session insights and send to Splunk")
    parser.add_argument("--once", action="store_true", help="Run single poll cycle and exit")
    parser.add_argument("--interval", type=int, default=60, help="Seconds between polls (default: 60)")
    parser.add_argument("--live", action="store_true", help="Actually send to Splunk (default: dry run)")
    parser.add_argument("--include-analysis", action="store_true", help="Include session_analysis (large)")
    args = parser.parse_args()
    
    dry_run = not args.live
    
    if args.once:
        result = run_poll_cycle(dry_run=dry_run, include_analysis=args.include_analysis)
        print(f"\nFinal result: {json.dumps(result, indent=2)}")
    else:
        run_continuous(interval_seconds=args.interval, dry_run=dry_run)
