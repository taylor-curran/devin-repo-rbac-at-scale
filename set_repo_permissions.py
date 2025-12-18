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

# Git connection ID (get this from list_connections.py)
CONNECTION_ID = "git-connection-3ea0a2d0b7904885b8a5a42a10d77fd9"  # alexpeng-cognition

# Repository to grant access to (format: "owner/repo")
REPOSITORY_PATH = "alexpeng-cognition/openvsx"

# ====================================

def main():
    """Add repository permissions to a Devin organization."""
    
    # API endpoint (v3beta1)
    url = f"https://api.devin.ai/v3beta1/enterprise/organizations/{ORG_ID}/git-providers/permissions"
    
    # Request headers
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Permission data - v3 uses 'permissions' array with 'repo_path' as string
    data = {
        "permissions": [{
            "git_connection_id": CONNECTION_ID,
            "repo_path": REPOSITORY_PATH
        }]
    }
    
    print(f"\nAdding permissions for: {REPOSITORY_PATH}")
    print(f"Organization: {ORG_ID}")
    print(f"Connection: {CONNECTION_ID}")
    
    try:
        # Make the API request
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        
        print("\n✓ Success!")
        print(f"Response: {json.dumps(result, indent=2)}")
        
    except requests.exceptions.RequestException as e:
        print(f"\nError: {e}")
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            print(f"Details: {e.response.text}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
