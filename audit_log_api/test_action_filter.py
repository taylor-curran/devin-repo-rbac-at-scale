#!/usr/bin/env python3
"""
test_action_filter.py - Test script for filtering audit logs by action type

Demonstrates how to use the 'action' query parameter to filter audit logs.
"""

import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("DEVIN_SERVICE_ACCOUNT_API_KEY")
BASE_URL = "https://api.devin.ai/v3beta1"

# Example action types to test
TEST_ACTIONS = [
    "login",
    "create_session",
    "ai_guardrail_violation",
]


def fetch_logs_by_action(action: str, time_after: int, time_before: int):
    """Fetch audit logs filtered by a specific action type."""
    url = f"{BASE_URL}/enterprise/audit-logs"
    
    params = {
        "action": action,
        "time_after": time_after,
        "time_before": time_before,
        "first": 10  # Small page for testing
    }
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    print(f"\n[TEST] Fetching action='{action}'")
    print(f"[TEST] URL: {url}")
    print(f"[TEST] Params: {params}")
    
    response = requests.get(url, headers=headers, params=params, timeout=30)
    
    print(f"[TEST] Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        items = data.get("items", [])
        print(f"[TEST] Found {len(items)} events")
        
        for item in items[:3]:  # Show first 3
            print(f"  - {item.get('action')}: {item.get('user_email', 'N/A')} at {datetime.fromtimestamp(item.get('created_at', 0))}")
        
        return data
    else:
        print(f"[TEST] Error: {response.text}")
        return None


def main():
    if not API_KEY:
        print("ERROR: Set DEVIN_SERVICE_ACCOUNT_API_KEY environment variable")
        print("Example: export DEVIN_SERVICE_ACCOUNT_API_KEY='cog_...'")
        return
    
    # Time window: last 7 days
    time_before = int(datetime.now().timestamp())
    time_after = int((datetime.now() - timedelta(days=7)).timestamp())
    
    print("=" * 60)
    print("Audit Log Action Filter Test")
    print(f"Time window: {datetime.fromtimestamp(time_after)} → {datetime.fromtimestamp(time_before)}")
    print("=" * 60)
    
    for action in TEST_ACTIONS:
        fetch_logs_by_action(action, time_after, time_before)
    
    print("\n" + "=" * 60)
    print("Test complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
