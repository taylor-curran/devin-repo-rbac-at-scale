import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ========== CONFIGURATION ==========
# Your Devin API Key (Service User credential with prefix: cog_)
API_KEY = os.getenv("DEVIN_SERVICE_ACCOUNT_API_KEY", "YOUR_API_KEY_HERE")

# ====================================

def main():
    """List all IDP groups in the enterprise."""
    
    # API endpoint (v3beta1)
    url = "https://api.devin.ai/v3beta1/enterprise/members/idp-groups"
    
    # Request headers
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        # Make the API request
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        # Print raw JSON for inspection
        print("\nRaw Response:")
        print(json.dumps(data, indent=2))
        
        # Get groups from response
        groups = data.get('items', [])
        
        # Display groups
        print(f"\n{'='*60}")
        print("IDP Groups Summary:")
        print(f"{'='*60}")
        
        if not groups:
            print("No IDP groups found.")
        else:
            for group in groups:
                group_name = group.get('idp_group_name', 'Unknown')
                role_assignments = group.get('role_assignments', [])
                
                print(f"\nGroup: {group_name}")
                print(f"  Role Assignments: {len(role_assignments)}")
                for assignment in role_assignments:
                    role = assignment.get('role', {})
                    org_id = assignment.get('org_id', 'N/A')
                    print(f"    - Role: {role.get('role_name', 'Unknown')} ({role.get('role_type', 'unknown')})")
                    if org_id:
                        print(f"      Org: {org_id}")
        
        print(f"\n{'='*60}")
        print(f"Total: {len(groups)} IDP groups")
        
        # Handle pagination if needed
        if data.get('has_next_page'):
            print(f"\nMore results available. Use cursor: {data.get('end_cursor')}")
        
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            print(f"Details: {e.response.text}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
