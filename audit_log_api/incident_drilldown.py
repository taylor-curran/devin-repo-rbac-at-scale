"""
incident_drilldown.py - On-Demand Deep Dive for Session Investigation

This script demonstrates how to:
1. Look up detailed session information for incident response
2. Correlate audit logs with session data
3. Generate an investigation "case packet" for SOC analysts

Use Cases:
- SOC receives an ai_guardrail_violation alert → investigate that session
- Security needs full context on what a user was doing
- Compliance audit requires detailed session reconstruction

API References:
- v2 Get Enterprise Session: https://docs.devin.ai/api-reference/v2/sessions/get-enterprise-session
- v3 Audit Logs: https://docs.devin.ai/api-reference/v3/audit-logs/enterprise-audit-logs

Authentication:
- Session details: DEVIN_ADMIN_USER_API_KEY (apk_user_*)
- Audit logs: DEVIN_SERVICE_ACCOUNT_API_KEY (cog_*)

This is an ON-DEMAND tool, not a continuous poller.
Run it when you have a specific session or user to investigate.
"""

import os
import json
import time
import requests
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

# ========== CONFIGURATION ==========
ADMIN_API_KEY = os.getenv("DEVIN_ADMIN_USER_API_KEY")
SERVICE_API_KEY = os.getenv("DEVIN_SERVICE_ACCOUNT_API_KEY")

V2_BASE_URL = "https://api.devin.ai/v2"
V3_BASE_URL = "https://api.devin.ai/v3beta1"

OUTPUT_DIR = "investigation_reports"


# ========== API CALLS ==========
def get_session_details(session_id: str) -> Dict[str, Any]:
    """
    Fetch full session details including analysis data.
    
    This is the "deep dive" endpoint - includes:
    - session_analysis (timeline, issues, action_items, suggested_prompt)
    - initial_user_message
    - pull_requests with state
    - Full metadata
    """
    url = f"{V2_BASE_URL}/enterprise/sessions/{session_id}"
    
    headers = {
        "Authorization": f"Bearer {ADMIN_API_KEY}",
        "Content-Type": "application/json"
    }
    
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()


def get_audit_logs_for_session(
    session_id: str,
    time_after: Optional[int] = None,
    time_before: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Fetch all audit logs related to a session.
    
    Note: The audit log API doesn't have a session_id filter,
    so we fetch by time window and filter client-side.
    
    In production, you might also filter by user_id if known.
    """
    if not time_after:
        # Default: look back 7 days
        time_after = int(time.time()) - (7 * 24 * 60 * 60)
    if not time_before:
        time_before = int(time.time())
    
    url = f"{V3_BASE_URL}/enterprise/audit-logs"
    
    headers = {
        "Authorization": f"Bearer {SERVICE_API_KEY}",
        "Content-Type": "application/json"
    }
    
    all_logs = []
    cursor = None
    
    while True:
        params = {
            "time_after": time_after,
            "time_before": time_before,
            "first": 200
        }
        if cursor:
            params["after"] = cursor
        
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        page = response.json()
        
        for item in page.get("items", []):
            # Check if this log relates to our session
            # Session ID might be in the 'data' field
            data = item.get("data", {})
            if data.get("session_id") == session_id:
                all_logs.append(item)
            # Also check for session lifecycle events
            if item.get("action") in ["create_session", "terminate_session", "sleep_session"]:
                if data.get("session_id") == session_id:
                    all_logs.append(item)
        
        if not page.get("has_next_page"):
            break
        cursor = page.get("end_cursor")
    
    return all_logs


def get_audit_logs_for_user(
    user_id: str,
    time_after: int,
    time_before: int
) -> List[Dict[str, Any]]:
    """
    Fetch all audit logs for a specific user in a time window.
    
    Useful when you know the user but not the specific session.
    """
    url = f"{V3_BASE_URL}/enterprise/audit-logs"
    
    headers = {
        "Authorization": f"Bearer {SERVICE_API_KEY}",
        "Content-Type": "application/json"
    }
    
    all_logs = []
    cursor = None
    
    while True:
        params = {
            "time_after": time_after,
            "time_before": time_before,
            "first": 200
        }
        if cursor:
            params["after"] = cursor
        
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        page = response.json()
        
        for item in page.get("items", []):
            if item.get("user_id") == user_id:
                all_logs.append(item)
        
        if not page.get("has_next_page"):
            break
        cursor = page.get("end_cursor")
    
    return all_logs


# ========== INVESTIGATION WORKFLOW ==========
def investigate_session(session_id: str) -> Dict[str, Any]:
    """
    Generate a complete investigation packet for a session.
    
    Returns a structured report suitable for:
    - SOC analyst review
    - Compliance documentation
    - Incident response records
    """
    print(f"\n{'='*60}")
    print(f"[INVESTIGATE] Session: {session_id}")
    print(f"{'='*60}")
    
    report = {
        "investigation_id": f"inv-{session_id}-{int(time.time())}",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "status": "complete",
        "findings": {}
    }
    
    # 1. Get session details
    print("[1/3] Fetching session details...")
    try:
        session = get_session_details(session_id)
        report["session"] = session
        report["findings"]["session_status"] = session.get("status")
        report["findings"]["user_id"] = session.get("user_id")
        report["findings"]["org_id"] = session.get("org_id")
        report["findings"]["acus_consumed"] = session.get("acus_consumed")
        report["findings"]["created_at"] = session.get("created_at")
        report["findings"]["initial_prompt"] = session.get("initial_user_message", "")[:500]  # Truncate for summary
        
        # Extract PR info
        prs = session.get("pull_requests", [])
        report["findings"]["pull_requests"] = prs
        report["findings"]["pr_count"] = len(prs)
        
        # Extract analysis highlights
        analysis = session.get("session_analysis", {})
        report["findings"]["issues_count"] = len(analysis.get("issues", []))
        report["findings"]["action_items_count"] = len(analysis.get("action_items", []))
        
        print(f"    Status: {session.get('status')}")
        print(f"    User: {session.get('user_id')}")
        print(f"    ACUs: {session.get('acus_consumed')}")
        print(f"    PRs: {len(prs)}")
        
    except requests.exceptions.HTTPError as e:
        print(f"    [ERROR] Could not fetch session: {e}")
        report["session"] = None
        report["errors"] = [f"Session fetch failed: {str(e)}"]
    
    # 2. Get related audit logs
    print("[2/3] Fetching related audit logs...")
    try:
        # Look back 7 days for related logs
        time_after = int(time.time()) - (7 * 24 * 60 * 60)
        time_before = int(time.time())
        
        audit_logs = get_audit_logs_for_session(session_id, time_after, time_before)
        report["audit_logs"] = audit_logs
        report["findings"]["audit_log_count"] = len(audit_logs)
        
        # Check for guardrail violations
        violations = [l for l in audit_logs if l.get("action") == "ai_guardrail_violation"]
        report["findings"]["guardrail_violations"] = violations
        report["findings"]["violation_count"] = len(violations)
        
        print(f"    Found {len(audit_logs)} related audit log entries")
        if violations:
            print(f"    ⚠️  Found {len(violations)} GUARDRAIL VIOLATIONS")
        
    except requests.exceptions.HTTPError as e:
        print(f"    [ERROR] Could not fetch audit logs: {e}")
        report["audit_logs"] = []
    
    # 3. Generate summary
    print("[3/3] Generating summary...")
    report["summary"] = generate_summary(report)
    print(f"\n{report['summary']}")
    
    return report


def generate_summary(report: Dict[str, Any]) -> str:
    """Generate a human-readable summary of the investigation."""
    findings = report.get("findings", {})
    
    lines = [
        "=" * 60,
        "INVESTIGATION SUMMARY",
        "=" * 60,
        f"Session ID: {report.get('session_id')}",
        f"Generated: {report.get('generated_at')}",
        "",
        "KEY FINDINGS:",
        f"  - Status: {findings.get('session_status', 'unknown')}",
        f"  - User ID: {findings.get('user_id', 'unknown')}",
        f"  - Organization: {findings.get('org_id', 'unknown')}",
        f"  - ACUs Consumed: {findings.get('acus_consumed', 0)}",
        f"  - Pull Requests Created: {findings.get('pr_count', 0)}",
        f"  - Related Audit Logs: {findings.get('audit_log_count', 0)}",
        f"  - Guardrail Violations: {findings.get('violation_count', 0)}",
        "",
    ]
    
    if findings.get("violation_count", 0) > 0:
        lines.append("⚠️  GUARDRAIL VIOLATIONS DETECTED - REVIEW REQUIRED")
        lines.append("")
    
    if findings.get("initial_prompt"):
        lines.append("INITIAL PROMPT (truncated):")
        lines.append(f"  {findings['initial_prompt'][:200]}...")
        lines.append("")
    
    if findings.get("pull_requests"):
        lines.append("PULL REQUESTS:")
        for pr in findings["pull_requests"]:
            lines.append(f"  - {pr.get('url')} [{pr.get('state')}]")
        lines.append("")
    
    lines.append("=" * 60)
    
    return "\n".join(lines)


def save_report(report: Dict[str, Any], output_dir: str = OUTPUT_DIR) -> str:
    """Save investigation report to JSON file."""
    os.makedirs(output_dir, exist_ok=True)
    
    filename = f"{report['investigation_id']}.json"
    filepath = os.path.join(output_dir, filename)
    
    with open(filepath, "w") as f:
        json.dump(report, f, indent=2, default=str)
    
    print(f"\n[SAVED] Report saved to: {filepath}")
    return filepath


# ========== ENTRY POINT ==========
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Investigate a Devin session for incident response",
        epilog="Example: python incident_drilldown.py --session sess-abc123"
    )
    parser.add_argument("--session", required=True, help="Session ID to investigate")
    parser.add_argument("--save", action="store_true", help="Save report to file")
    parser.add_argument("--output-dir", default=OUTPUT_DIR, help="Output directory for reports")
    args = parser.parse_args()
    
    # Validate API keys
    if not ADMIN_API_KEY:
        print("[ERROR] DEVIN_ADMIN_USER_API_KEY not set")
        exit(1)
    if not SERVICE_API_KEY:
        print("[ERROR] DEVIN_SERVICE_ACCOUNT_API_KEY not set")
        exit(1)
    
    # Run investigation
    report = investigate_session(args.session)
    
    if args.save:
        save_report(report, args.output_dir)
    
    # Exit with error code if violations found
    if report.get("findings", {}).get("violation_count", 0) > 0:
        exit(1)  # Non-zero exit for alerting/automation
    
    exit(0)
