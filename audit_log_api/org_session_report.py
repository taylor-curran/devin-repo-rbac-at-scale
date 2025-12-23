#!/usr/bin/env python3
"""
org_session_report.py - Generate detailed org/user/session report

Fetches and saves:
- Organizations with user counts
- Sessions by status (running/suspended/finished/exit)
- Unique users per org
- Session date ranges (created_at, updated_at)
- Saves to JSON file for analysis

Uses:
- v3 API for organizations and enterprise users
- v2 API for sessions (includes user_id, org_id)
"""

import os
import json
import requests
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Any
from dotenv import load_dotenv

load_dotenv()

# Configuration
API_KEY = os.getenv("DEVIN_SERVICE_ACCOUNT_API_KEY")  # cog_* for v3
ADMIN_API_KEY = os.getenv("DEVIN_ADMIN_USER_API_KEY")  # apk_user_* for v2
N_ORGS = int(os.getenv("N_ORGS", "4"))  # Number of orgs to include (default: 4)

API_V3 = "https://api.devin.ai/v3beta1"
API_V2 = "https://api.devin.ai/v2"

OUTPUT_FILE = "org_session_report.json"


def get_headers(api_key: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }


# ========== FETCH ORGANIZATIONS (v3 API) ==========
def fetch_organizations() -> List[Dict[str, Any]]:
    """Fetch all organizations from v3 API."""
    print("[1/4] Fetching organizations...")
    url = f"{API_V3}/enterprise/organizations"
    params = {"first": 200}
    
    all_orgs = []
    cursor = None
    
    while True:
        if cursor:
            params["after"] = cursor
        
        response = requests.get(url, headers=get_headers(API_KEY), params=params, timeout=30)
        
        if response.status_code != 200:
            print(f"[ERROR] Failed to fetch orgs: {response.status_code} - {response.text}")
            break
        
        data = response.json()
        all_orgs.extend(data.get("items", []))
        
        if not data.get("has_next_page"):
            break
        cursor = data.get("end_cursor")
    
    print(f"      Found {len(all_orgs)} organizations")
    return all_orgs


# ========== FETCH ENTERPRISE USERS (v3 API) ==========
def fetch_enterprise_users() -> List[Dict[str, Any]]:
    """Fetch all enterprise users from v3 API."""
    print("[2/4] Fetching enterprise users...")
    url = f"{API_V3}/enterprise/members/users"
    params = {"first": 200}
    
    all_users = []
    cursor = None
    
    while True:
        if cursor:
            params["after"] = cursor
        
        response = requests.get(url, headers=get_headers(API_KEY), params=params, timeout=30)
        
        if response.status_code != 200:
            print(f"[ERROR] Failed to fetch users: {response.status_code} - {response.text}")
            break
        
        data = response.json()
        all_users.extend(data.get("items", []))
        
        if not data.get("has_next_page"):
            break
        cursor = data.get("end_cursor")
    
    print(f"      Found {len(all_users)} enterprise users")
    return all_users


# ========== FETCH ALL SESSIONS (v2 API) ==========
def fetch_all_sessions() -> List[Dict[str, Any]]:
    """Fetch ALL sessions from v2 API (no time limit)."""
    print("[3/4] Fetching all sessions (this may take a while)...")
    url = f"{API_V2}/enterprise/sessions"
    params = {"limit": 200}
    
    all_sessions = []
    skip = 0
    
    while True:
        params["skip"] = skip
        response = requests.get(url, headers=get_headers(ADMIN_API_KEY), params=params, timeout=60)
        
        if response.status_code != 200:
            print(f"[ERROR] v2 sessions failed: {response.status_code} - {response.text}")
            break
        
        data = response.json()
        items = data.get("items", [])
        all_sessions.extend(items)
        
        if len(all_sessions) % 1000 == 0 and len(all_sessions) > 0:
            print(f"      ... fetched {len(all_sessions)} sessions so far")
        
        if not data.get("has_more"):
            break
        skip += len(items)
    
    print(f"      Found {len(all_sessions)} total sessions")
    return all_sessions


# ========== BUILD REPORT ==========
def build_report(orgs: List[Dict], users: List[Dict], sessions: List[Dict]) -> Dict:
    """Build comprehensive report data structure."""
    print("[4/4] Building report...")
    
    # Build org_id -> org_name lookup
    org_lookup = {org.get("org_id"): org.get("name", org.get("org_id")) for org in orgs}
    
    # Build user_id -> user_email lookup
    user_lookup = {user.get("user_id"): user.get("email", user.get("user_id")) for user in users}
    
    # Group sessions by org_id
    sessions_by_org = defaultdict(list)
    for session in sessions:
        sessions_by_org[session.get("org_id", "unknown")].append(session)
    
    # Sort orgs by session count, take top N_ORGS
    sorted_org_ids = sorted(sessions_by_org.keys(), key=lambda x: len(sessions_by_org[x]), reverse=True)[:N_ORGS]
    
    # Calculate totals
    total_sessions = sum(len(sessions_by_org[org_id]) for org_id in sorted_org_ids)
    total_unique_users = set()
    
    # Build org reports
    org_reports = []
    
    for org_id in sorted_org_ids:
        org_sessions = sessions_by_org[org_id]
        org_name = org_lookup.get(org_id, org_id)
        
        # Group sessions by user within this org
        users_in_org = defaultdict(list)
        for session in org_sessions:
            user_id = session.get("user_id", "unknown")
            users_in_org[user_id].append(session)
            total_unique_users.add(user_id)
        
        # Count sessions by status
        status_counts = defaultdict(int)
        for session in org_sessions:
            status = session.get("status", "unknown")
            status_counts[status] += 1
        
        # Find date range of sessions
        created_dates = [s.get("created_at") for s in org_sessions if s.get("created_at")]
        updated_dates = [s.get("updated_at") for s in org_sessions if s.get("updated_at")]
        
        earliest_created = min(created_dates) if created_dates else None
        latest_created = max(created_dates) if created_dates else None
        latest_updated = max(updated_dates) if updated_dates else None
        
        # Build user reports for this org
        user_reports = []
        sorted_users = sorted(users_in_org.items(), key=lambda x: len(x[1]), reverse=True)
        
        for user_id, user_sessions in sorted_users:
            user_email = user_lookup.get(user_id, user_id)
            
            # Count sessions by status for this user
            user_status_counts = defaultdict(int)
            for session in user_sessions:
                status = session.get("status", "unknown")
                user_status_counts[status] += 1
            
            # Find date range for this user's sessions
            user_created_dates = [s.get("created_at") for s in user_sessions if s.get("created_at")]
            user_updated_dates = [s.get("updated_at") for s in user_sessions if s.get("updated_at")]
            
            # Sample sessions (first 5)
            sample_sessions = []
            for s in user_sessions[:5]:
                sample_sessions.append({
                    "session_id": s.get("session_id"),
                    "title": s.get("title", "N/A"),
                    "status": s.get("status"),
                    "created_at": s.get("created_at"),
                    "updated_at": s.get("updated_at"),
                    "acus_consumed": s.get("acus_consumed", 0),
                    "url": s.get("url")
                })
            
            user_reports.append({
                "user_id": user_id,
                "user_email": user_email,
                "total_sessions": len(user_sessions),
                "sessions_by_status": dict(user_status_counts),
                "earliest_session_created": min(user_created_dates) if user_created_dates else None,
                "latest_session_created": max(user_created_dates) if user_created_dates else None,
                "latest_session_updated": max(user_updated_dates) if user_updated_dates else None,
                "sample_sessions": sample_sessions
            })
        
        org_reports.append({
            "org_id": org_id,
            "org_name": org_name,
            "total_sessions": len(org_sessions),
            "unique_users": len(users_in_org),
            "sessions_by_status": dict(status_counts),
            "earliest_session_created": earliest_created,
            "latest_session_created": latest_created,
            "latest_session_updated": latest_updated,
            "users": user_reports
        })
    
    # Build final report
    report = {
        "report_generated_at": datetime.now().isoformat(),
        "summary": {
            "total_organizations_in_enterprise": len(orgs),
            "organizations_in_report": len(org_reports),
            "total_sessions_across_report_orgs": total_sessions,
            "total_unique_users_across_report_orgs": len(total_unique_users),
            "total_enterprise_users": len(users)
        },
        "notes": {
            "total_sessions": "Count of individual sessions created across the orgs in this report from day one of Devin usage",
            "unique_users": "Count of distinct user_ids who have created at least one session in that org",
            "session_dates": "created_at = when session was started, updated_at = last activity on that session",
            "session_status": "running = currently active, suspended = paused/idle, finished = completed normally, exit = terminated",
            "long_running_sessions": "Sessions can remain 'suspended' for extended periods - they are snapshots that persist until explicitly terminated",
            "multiple_sessions_per_user": "Valid scenario - users can create many sessions for different tasks"
        },
        "organizations": org_reports
    }
    
    return report


# ========== MAIN ==========
def main():
    print("=" * 80)
    print(f"Organization Session Report Generator (Top {N_ORGS} orgs)")
    print("=" * 80)
    
    # Check required env vars
    if not API_KEY:
        print("ERROR: Set DEVIN_SERVICE_ACCOUNT_API_KEY environment variable")
        return
    
    if not ADMIN_API_KEY:
        print("ERROR: Set DEVIN_ADMIN_USER_API_KEY environment variable")
        return
    
    print(f"\nThis will fetch ALL sessions and generate a detailed report.")
    print(f"Output will be saved to: {OUTPUT_FILE}\n")
    
    # Fetch data
    orgs = fetch_organizations()
    users = fetch_enterprise_users()
    sessions = fetch_all_sessions()
    
    # Build report
    report = build_report(orgs, users, sessions)
    
    # Save to file
    output_path = os.path.join(os.path.dirname(__file__), OUTPUT_FILE)
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    
    print(f"\n{'=' * 80}")
    print(f"Report saved to: {output_path}")
    print(f"{'=' * 80}")
    
    # Print summary to console
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total Organizations in Enterprise: {report['summary']['total_organizations_in_enterprise']}")
    print(f"Organizations in Report: {report['summary']['organizations_in_report']}")
    print(f"Total Sessions (across report orgs): {report['summary']['total_sessions_across_report_orgs']}")
    print(f"Total Unique Users (across report orgs): {report['summary']['total_unique_users_across_report_orgs']}")
    print(f"Total Enterprise Users: {report['summary']['total_enterprise_users']}")
    
    print("\n" + "-" * 80)
    print("BY ORGANIZATION:")
    print("-" * 80)
    
    for org in report["organizations"]:
        print(f"\n🏢 {org['org_name']}")
        print(f"   Total Sessions: {org['total_sessions']}")
        print(f"   Unique Users: {org['unique_users']}")
        print(f"   Sessions by Status: {org['sessions_by_status']}")
        print(f"   Date Range: {org['earliest_session_created']} → {org['latest_session_created']}")
        
        print(f"\n   Top Users:")
        for user in org["users"][:5]:
            print(f"     - {user['user_email']}: {user['total_sessions']} sessions")
            print(f"       Status breakdown: {user['sessions_by_status']}")
    
    print("\n" + "=" * 80)
    print("Done!")


if __name__ == "__main__":
    main()
