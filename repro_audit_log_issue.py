#!/usr/bin/env python3
"""
repro_audit_log_issue.py - Reproduce Audit Log API Issue

Issue reported:
- /v3beta1/enterprise/audit-logs - returns logs as expected
- /v3beta1/enterprise/organizations/{org_id}/audit-logs - returns empty (not 403)
- /v3beta1/enterprise/organizations/{invalid_org_id}/audit-logs - returns 403

Both endpoints require ManageEnterpriseSettings permission per docs:
- https://docs.devin.ai/api-reference/v3/audit-logs/enterprise-audit-logs#permissions
- https://docs.devin.ai/api-reference/v3/audit-logs/organizations-audit-logs#permissions

v2 API Context:
- v2 only has enterprise-level audit logs: GET /v2/enterprise/audit-logs
- There is NO org-level audit logs endpoint in v2
- The org-level endpoint is NEW in v3beta1
- v2 uses Personal API Keys (apk_user_*), v3 uses Service User credentials (cog_*)

This script tests:
1. List organizations to get valid org_ids
2. Fetch enterprise-level audit logs (should work)
3. Fetch org-level audit logs for each org (currently returning empty)
4. Fetch org-level audit logs with invalid org_id (should return 403)
"""

import os
import json
import requests
from datetime import datetime
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

load_dotenv()

# ========== CONFIGURATION ==========
# Use Taylor's demo account to reproduce
API_KEY = os.getenv("DEVIN_SERVICE_ACCOUNT_TAYLOR_DEMO_ACCOUNT")
BASE_URL = "https://api.devin.ai/v3beta1"

# Fallback to other keys if Taylor's isn't set
if not API_KEY:
    API_KEY = os.getenv("DEVIN_SERVICE_ACCOUNT_API_KEY")


def make_request(method: str, url: str, params: Optional[Dict] = None) -> Dict[str, Any]:
    """Make an API request and return response details."""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.request(method, url, headers=headers, params=params, timeout=30)
        return {
            "status_code": response.status_code,
            "ok": response.ok,
            "data": response.json() if response.text else None,
            "error": None
        }
    except requests.exceptions.HTTPError as e:
        return {
            "status_code": e.response.status_code if e.response else None,
            "ok": False,
            "data": e.response.json() if e.response and e.response.text else None,
            "error": str(e)
        }
    except Exception as e:
        return {
            "status_code": None,
            "ok": False,
            "data": None,
            "error": str(e)
        }


def list_organizations() -> List[Dict[str, Any]]:
    """Fetch all organizations in the enterprise."""
    print("\n" + "="*70)
    print("STEP 1: List Organizations")
    print("="*70)
    
    url = f"{BASE_URL}/enterprise/organizations"
    result = make_request("GET", url)
    
    print(f"URL: {url}")
    print(f"Status: {result['status_code']}")
    
    if not result["ok"]:
        print(f"ERROR: {result['error']}")
        print(f"Response: {json.dumps(result['data'], indent=2)}")
        return []
    
    orgs = result["data"].get("items", [])
    print(f"\nFound {len(orgs)} organizations:")
    for org in orgs:
        print(f"  - {org.get('name', 'unnamed')} (ID: {org.get('org_id')})")
    
    return orgs


def fetch_enterprise_audit_logs(limit: int = 10) -> Dict[str, Any]:
    """Fetch audit logs at enterprise level."""
    print("\n" + "="*70)
    print("STEP 2: Fetch Enterprise-Level Audit Logs")
    print("="*70)
    
    url = f"{BASE_URL}/enterprise/audit-logs"
    params = {"first": limit}
    
    result = make_request("GET", url, params)
    
    print(f"URL: {url}")
    print(f"Params: {params}")
    print(f"Status: {result['status_code']}")
    
    if not result["ok"]:
        print(f"ERROR: {result['error']}")
        print(f"Response: {json.dumps(result['data'], indent=2)}")
        return result
    
    data = result["data"]
    items = data.get("items", [])
    total = data.get("total", len(items))
    
    print(f"\nResults: {len(items)} items returned (total: {total})")
    
    if items:
        print("\nSample logs (first 3):")
        for i, log in enumerate(items[:3]):
            ts = datetime.fromtimestamp(log.get("created_at", 0))
            print(f"  {i+1}. [{ts}] action={log.get('action')}, org_id={log.get('org_id')}")
    
    # Summarize org_ids in the logs
    org_ids_in_logs = set(log.get("org_id") for log in items if log.get("org_id"))
    if org_ids_in_logs:
        print(f"\nUnique org_ids found in enterprise logs: {org_ids_in_logs}")
    
    return result


def fetch_org_audit_logs(org_id: str, org_name: str, limit: int = 10) -> Dict[str, Any]:
    """Fetch audit logs for a specific organization."""
    print("\n" + "-"*70)
    print(f"Testing org: {org_name} ({org_id})")
    print("-"*70)
    
    url = f"{BASE_URL}/enterprise/organizations/{org_id}/audit-logs"
    params = {"first": limit}
    
    result = make_request("GET", url, params)
    
    print(f"URL: {url}")
    print(f"Params: {params}")
    print(f"Status: {result['status_code']}")
    
    if not result["ok"]:
        print(f"ERROR: {result['error']}")
        if result["data"]:
            print(f"Response: {json.dumps(result['data'], indent=2)}")
        return result
    
    data = result["data"]
    items = data.get("items", [])
    total = data.get("total", len(items))
    
    print(f"Results: {len(items)} items returned (total: {total})")
    
    if items:
        print("Sample logs (first 3):")
        for i, log in enumerate(items[:3]):
            ts = datetime.fromtimestamp(log.get("created_at", 0))
            print(f"  {i+1}. [{ts}] action={log.get('action')}")
    else:
        print("*** EMPTY RESPONSE - This is the reported bug! ***")
    
    return result


def test_invalid_org_id() -> Dict[str, Any]:
    """Test with an invalid org_id - should return 403."""
    print("\n" + "="*70)
    print("STEP 4: Test Invalid Org ID (expect 403)")
    print("="*70)
    
    invalid_org_id = "org-invalid-nonexistent-12345"
    url = f"{BASE_URL}/enterprise/organizations/{invalid_org_id}/audit-logs"
    params = {"first": 10}
    
    result = make_request("GET", url, params)
    
    print(f"URL: {url}")
    print(f"Params: {params}")
    print(f"Status: {result['status_code']}")
    
    if result["status_code"] == 403:
        print("Got expected 403 for invalid org_id")
    else:
        print(f"Unexpected status! Expected 403, got {result['status_code']}")
    
    if result["data"]:
        print(f"Response: {json.dumps(result['data'], indent=2)}")
    
    return result


def main():
    """Run the reproduction script."""
    print("\n" + "#"*70)
    print("# Audit Log API Issue Reproduction Script")
    print("# Testing with service account: DEVIN_SERVICE_ACCOUNT_TAYLOR_DEMO_ACCOUNT")
    print("#"*70)
    
    if not API_KEY:
        print("\nERROR: No API key configured!")
        print("Set DEVIN_SERVICE_ACCOUNT_TAYLOR_DEMO_ACCOUNT or DEVIN_SERVICE_ACCOUNT_API_KEY")
        return 1
    
    print(f"\nAPI Key (masked): {API_KEY[:10]}...{API_KEY[-4:]}")
    
    # Step 1: List organizations
    orgs = list_organizations()
    
    # Step 2: Fetch enterprise-level audit logs
    enterprise_result = fetch_enterprise_audit_logs(limit=20)
    enterprise_logs = enterprise_result.get("data", {}).get("items", [])
    
    # Step 3: Fetch org-level audit logs for each org
    print("\n" + "="*70)
    print("STEP 3: Fetch Organization-Level Audit Logs (per org)")
    print("="*70)
    
    org_results = {}
    for org in orgs:
        org_id = org.get("org_id")
        org_name = org.get("name", "unnamed")
        if org_id:
            result = fetch_org_audit_logs(org_id, org_name)
            org_results[org_id] = {
                "name": org_name,
                "status": result["status_code"],
                "count": len(result.get("data", {}).get("items", [])) if result["ok"] else None,
                "total": result.get("data", {}).get("total") if result["ok"] else None
            }
    
    # Step 4: Test invalid org_id
    invalid_result = test_invalid_org_id()
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    
    print(f"\n1. Enterprise audit logs: {len(enterprise_logs)} logs returned")
    
    print(f"\n2. Org-level audit logs:")
    for org_id, info in org_results.items():
        status = "OK" if info["status"] == 200 else f"HTTP {info['status']}"
        count = info["count"] if info["count"] is not None else "N/A"
        print(f"   - {info['name']} ({org_id}): {status}, {count} logs")
    
    print(f"\n3. Invalid org_id test: HTTP {invalid_result['status_code']}")
    
    # Analyze the bug
    print("\n" + "="*70)
    print("ANALYSIS")
    print("="*70)
    
    # Check if enterprise logs have org_ids that match our orgs
    org_ids_in_enterprise_logs = set(
        log.get("org_id") for log in enterprise_logs if log.get("org_id")
    )
    our_org_ids = set(org.get("org_id") for org in orgs)
    
    matching_org_ids = org_ids_in_enterprise_logs & our_org_ids
    
    print(f"\nOrg IDs in enterprise logs: {org_ids_in_enterprise_logs}")
    print(f"Our org IDs: {our_org_ids}")
    print(f"Matching org IDs: {matching_org_ids}")
    
    if matching_org_ids:
        empty_orgs_with_logs = [
            org_id for org_id in matching_org_ids
            if org_results.get(org_id, {}).get("count") == 0
        ]
        if empty_orgs_with_logs:
            print(f"\n*** BUG CONFIRMED ***")
            print(f"These orgs have logs at enterprise level but return empty at org level:")
            for org_id in empty_orgs_with_logs:
                print(f"  - {org_results[org_id]['name']} ({org_id})")
    
    return 0


if __name__ == "__main__":
    exit(main())
