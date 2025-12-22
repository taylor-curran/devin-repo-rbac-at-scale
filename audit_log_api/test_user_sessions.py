#!/usr/bin/env python3
"""
test_user_sessions.py - Track who logged in and what sessions they ran by org

Uses:
- v3 API for audit logs (login events) and organizations - requires service account key
- v2 API for sessions (includes user_id, org_id) - requires admin user key

API Endpoints Used:
- GET /v3beta1/enterprise/organizations
- GET /v3beta1/enterprise/audit-logs?action=login
- GET /v2/enterprise/sessions
"""

import os
import requests
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Any
from dotenv import load_dotenv

load_dotenv()

# Configuration
API_KEY = os.getenv("DEVIN_SERVICE_ACCOUNT_API_KEY")  # cog_* for v3
ADMIN_API_KEY = os.getenv("DEVIN_ADMIN_USER_API_KEY")  # apk_user_* for v2
N_ORGS = int(os.getenv("N_ORGS", "4"))  # Number of orgs to display (default: 4)

API_V3 = "https://api.devin.ai/v3beta1"
API_V2 = "https://api.devin.ai/v2"


def get_headers(api_key: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }


# ========== ORGANIZATIONS (v3 API) ==========
def fetch_organizations() -> List[Dict[str, Any]]:
    """Fetch all organizations from v3 API."""
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
    
    return all_orgs


# ========== AUDIT LOG: Get Logins (v3 API) ==========
def fetch_login_events(time_after: int, time_before: int) -> List[Dict[str, Any]]:
    """
    Fetch login events from v3 audit logs API.
    
    Returns list of login events with user_email, user_id, created_at.
    """
    url = f"{API_V3}/enterprise/audit-logs"
    params = {
        "action": "login",
        "time_after": time_after,
        "time_before": time_before,
        "first": 200
    }
    
    all_logins = []
    cursor = None
    
    while True:
        if cursor:
            params["after"] = cursor
        
        response = requests.get(url, headers=get_headers(API_KEY), params=params, timeout=30)
        
        if response.status_code != 200:
            print(f"[ERROR] Failed to fetch logins: {response.status_code} - {response.text}")
            break
        
        data = response.json()
        all_logins.extend(data.get("items", []))
        
        if not data.get("has_next_page"):
            break
        cursor = data.get("end_cursor")
    
    return all_logins


# ========== SESSIONS: Get Enterprise Sessions (v2 API) ==========
def fetch_sessions_v2() -> List[Dict[str, Any]]:
    """
    Fetch sessions from v2 API (enterprise-wide).
    
    Requires DEVIN_ADMIN_USER_API_KEY (apk_user_* format).
    """
    url = f"{API_V2}/enterprise/sessions"
    params = {"limit": 200}
    
    all_sessions = []
    skip = 0
    
    while True:
        params["skip"] = skip
        response = requests.get(url, headers=get_headers(ADMIN_API_KEY), params=params, timeout=30)
        
        if response.status_code != 200:
            print(f"[ERROR] v2 sessions failed: {response.status_code} - {response.text}")
            break
        
        data = response.json()
        items = data.get("items", [])
        all_sessions.extend(items)
        
        if not data.get("has_more"):
            break
        skip += len(items)
    
    return all_sessions


# ========== MAIN ==========
def main():
    print("=" * 80)
    print(f"User Login & Session Tracker by Organization (Top {N_ORGS})")
    print("=" * 80)
    
    # Check required env vars
    if not API_KEY:
        print("ERROR: Set DEVIN_SERVICE_ACCOUNT_API_KEY environment variable")
        return
    
    if not ADMIN_API_KEY:
        print("ERROR: Set DEVIN_ADMIN_USER_API_KEY environment variable")
        return
    
    # Time window: last 2 days
    time_before = int(datetime.now().timestamp())
    time_after = int((datetime.now() - timedelta(days=2)).timestamp())
    
    print(f"\nTime window: {datetime.fromtimestamp(time_after)} → {datetime.fromtimestamp(time_before)}")
    print(f"Showing top {N_ORGS} organizations by session count")
    
    # Step 1: Fetch organizations (v3 API)
    print("\n[1/3] Fetching organizations from v3 API...")
    orgs = fetch_organizations()
    print(f"      Found {len(orgs)} organizations")
    
    # Build org_id -> org_name lookup
    org_lookup = {org.get("org_id"): org.get("name", org.get("org_id")) for org in orgs}
    
    # Step 2: Fetch login events (v3 API)
    print("\n[2/3] Fetching login events from v3 audit logs...")
    logins = fetch_login_events(time_after, time_before)
    print(f"      Found {len(logins)} login events")
    
    # Step 3: Fetch sessions (v2 API)
    print("\n[3/3] Fetching sessions from v2 enterprise API...")
    sessions = fetch_sessions_v2()
    print(f"      Found {len(sessions)} sessions")
    
    # Display LOGIN EVENTS
    print("\n" + "=" * 80)
    print("LOGIN EVENTS (last 20)")
    print("=" * 80)
    
    for login in logins[:20]:
        ts = datetime.fromtimestamp(login.get("created_at", 0)).isoformat()
        email = login.get("user_email", "N/A")
        user_id = login.get("user_id", "N/A")
        print(f"[{ts}] {email} (user_id: {user_id})")
    
    # Group sessions by org_id
    sessions_by_org = defaultdict(list)
    for session in sessions:
        sessions_by_org[session.get("org_id", "unknown")].append(session)
    
    # Display SESSIONS BY ORGANIZATION → USER
    print("\n" + "=" * 80)
    print("SESSIONS BY ORGANIZATION → USER")
    print("=" * 80)
    
    # Sort orgs by session count (descending), limit to N_ORGS
    sorted_orgs = sorted(sessions_by_org.items(), key=lambda x: len(x[1]), reverse=True)[:N_ORGS]
    
    for org_id, org_sessions in sorted_orgs:
        org_name = org_lookup.get(org_id, org_id)
        
        print("\n" + "=" * 80)
        print(f"🏢 Organization: {org_name}")
        print(f"   Org ID: {org_id}")
        print(f"   Total Sessions: {len(org_sessions)}")
        print("=" * 80)
        
        # Group by user within this org
        users_in_org = defaultdict(list)
        for session in org_sessions:
            users_in_org[session.get("user_id", "unknown")].append(session)
        
        # Sort users by session count (descending)
        sorted_users = sorted(users_in_org.items(), key=lambda x: len(x[1]), reverse=True)
        
        for user_id, user_sessions in sorted_users:
            print(f"\n  👤 User ID: {user_id}")
            print(f"     Sessions: {len(user_sessions)}")
            
            for session in user_sessions[:3]:
                title = session.get("title", "N/A") or "N/A"
                if len(title) > 45:
                    title = title[:45]
                status = session.get("status", "unknown")
                created = session.get("created_at", "N/A")
                acus = session.get("acus_consumed", 0)
                print(f"     - [{status}] {title}")
                print(f"       Created: {created} | ACUs: {acus}")
    
    # Display SUMMARY BY ORGANIZATION
    print("\n" + "=" * 80)
    print(f"SUMMARY BY ORGANIZATION (Top {N_ORGS})")
    print("=" * 80)
    
    for org_id, org_sessions in sorted_orgs:
        org_name = org_lookup.get(org_id, org_id)
        users_in_org = set(s.get("user_id") for s in org_sessions)
        print(f"{org_name}: {len(org_sessions)} session(s), {len(users_in_org)} user(s)")
    
    print("\n" + "=" * 80)
    print("Done!")


if __name__ == "__main__":
    main()
