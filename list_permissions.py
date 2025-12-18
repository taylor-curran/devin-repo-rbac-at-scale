import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ========== CONFIGURATION ==========
# Your Devin API Key (Service User credential with prefix: cog_)
API_KEY = os.getenv("DEVIN_SERVICE_ACCOUNT_API_KEY", "YOUR_API_KEY_HERE")

# Organization ID (get this from list_organizations.py)
ORG_ID = "org-45ecc3f2730d46a5a7ebe433d0813678"  # taylor-demos

# ====================================

def main():
    """List git permissions for an organization."""
    
    # API endpoint (v3beta1)
    url = f"https://api.devin.ai/v3beta1/enterprise/organizations/{ORG_ID}/git-providers/permissions"
    
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
        
        # Get permissions from response
        permissions = data.get('items', [])
        
        # Display permissions
        print(f"\nGit Permissions for Organization: {ORG_ID}")
        print("=" * 60)
        
        if not permissions:
            print("No git permissions found for this organization.")
        else:
            for perm in permissions:
                perm_id = perm.get('git_permission_id', 'No ID')
                conn_id = perm.get('git_connection_id', 'No connection')
                repo_path = perm.get('repo_path', 'No path')
                prefix_path = perm.get('prefix_path', '')
                group_prefix = perm.get('group_prefix', '')
                
                print(f"Permission ID:  {perm_id}")
                print(f"Connection ID:  {conn_id}")
                print(f"Repo Path:      {repo_path}")
                if prefix_path:
                    print(f"Prefix Path:    {prefix_path}")
                if group_prefix:
                    print(f"Group Prefix:   {group_prefix}")
                print("-" * 60)
        
        print(f"\nTotal: {len(permissions)} permissions")
        
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
