#!/usr/bin/env python3
"""
Test script for the v3beta1 org-group-limits API.
Creates test organizations and attempts to set group limits on them.
"""
import requests
import json
import os
import time
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("DEVIN_SERVICE_ACCOUNT_API_KEY")
BASE_URL = "https://api.devin.ai/v3beta1"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}


def create_org(name: str) -> dict | None:
    """Create an organization and return the response."""
    url = f"{BASE_URL}/enterprise/organizations"
    data = {"name": name}
    
    print(f"Creating org: {name}...")
    resp = requests.post(url, headers=HEADERS, json=data)
    
    if resp.ok:
        result = resp.json()
        print(f"  ✓ Created: {result.get('org_id')}")
        return result
    else:
        print(f"  ✗ Failed: {resp.status_code} - {resp.text}")
        return None


def get_org_group_limits() -> dict | None:
    """Get current org group limits configuration."""
    url = f"{BASE_URL}/enterprise/org-group-limits"
    
    print("\nGetting current org-group-limits...")
    resp = requests.get(url, headers=HEADERS)
    
    if resp.ok:
        result = resp.json()
        print(f"  ✓ Response: {json.dumps(result, indent=2)}")
        return result
    else:
        print(f"  ✗ Failed: {resp.status_code} - {resp.text}")
        return None


def update_org_group_limits(groups_config: dict) -> dict | None:
    """Update org group limits configuration."""
    url = f"{BASE_URL}/enterprise/org-group-limits"
    data = {"groups": groups_config}
    
    print(f"\nUpdating org-group-limits with:")
    print(json.dumps(data, indent=2))
    
    resp = requests.put(url, headers=HEADERS, json=data)
    
    if resp.ok:
        result = resp.json()
        print(f"  ✓ Response: {json.dumps(result, indent=2)}")
        return result
    else:
        print(f"  ✗ Failed: {resp.status_code} - {resp.text}")
        return None


def delete_org(org_id: str) -> bool:
    """Delete an organization."""
    url = f"{BASE_URL}/enterprise/organizations/{org_id}"
    
    print(f"Deleting org: {org_id}...")
    resp = requests.delete(url, headers=HEADERS)
    
    if resp.ok:
        print(f"  ✓ Deleted")
        return True
    else:
        print(f"  ✗ Failed: {resp.status_code} - {resp.text}")
        return False


def main():
    print("=" * 60)
    print("Testing v3beta1 org-group-limits API")
    print("=" * 60)
    
    # Step 1: Check current org-group-limits state
    print("\n--- Step 1: Get current org-group-limits ---")
    current_config = get_org_group_limits()
    
    # Step 2: Create test organizations
    print("\n--- Step 2: Create test organizations ---")
    timestamp = int(time.time())
    
    org1 = create_org(f"test-group-limit-alpha-{timestamp}")
    org2 = create_org(f"test-group-limit-beta-{timestamp}")
    
    if not org1 or not org2:
        print("\nFailed to create test orgs. Exiting.")
        return 1
    
    org1_id = org1.get("org_id")
    org2_id = org2.get("org_id")
    
    print(f"\nCreated orgs:")
    print(f"  - {org1.get('name')}: {org1_id}")
    print(f"  - {org2.get('name')}: {org2_id}")
    
    # Step 3: Try to set group limits
    print("\n--- Step 3: Test org-group-limits configurations ---")
    
    # Test A: Simple group with org_ids
    print("\n[Test A] Simple config with org_ids:")
    config_a = {
        "test-group": {
            "org_ids": [org1_id, org2_id]
        }
    }
    update_org_group_limits(config_a)
    
    # Test B: Group with ACU limit
    print("\n[Test B] Config with acu_limit:")
    config_b = {
        "test-group": {
            "org_ids": [org1_id, org2_id],
            "acu_limit": 1000
        }
    }
    update_org_group_limits(config_b)
    
    # Test C: Group with max_cycle_acu_limit
    print("\n[Test C] Config with max_cycle_acu_limit:")
    config_c = {
        "test-group": {
            "org_ids": [org1_id, org2_id],
            "max_cycle_acu_limit": 1000
        }
    }
    update_org_group_limits(config_c)
    
    # Test D: Multiple groups
    print("\n[Test D] Multiple groups:")
    config_d = {
        "alpha-group": {
            "org_ids": [org1_id]
        },
        "beta-group": {
            "org_ids": [org2_id]
        }
    }
    update_org_group_limits(config_d)
    
    # Test E: Empty groups (reset)
    print("\n[Test E] Reset to empty config:")
    update_org_group_limits({})
    
    # Step 4: Verify final state
    print("\n--- Step 4: Verify final state ---")
    get_org_group_limits()
    
    # Step 5: Cleanup - delete test orgs
    print("\n--- Step 5: Cleanup test organizations ---")
    delete_org(org1_id)
    delete_org(org2_id)
    
    print("\n" + "=" * 60)
    print("Test complete!")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    exit(main())
