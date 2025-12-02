import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ========== CONFIGURATION ==========
# Your Devin API Key
API_KEY = os.getenv("DEVIN_API_KEY", "YOUR_API_KEY_HERE")

# Organization ID (get this from list_organizations.py)
ORG_ID = "org-406782bf7ec34819b0c3bd0ba67a5c84"  # org-2

# Git connection ID (get this from list_connections.py)
CONNECTION_ID = "git-connection-54e8883977654c76ae4fc1746cb68fd6"  # taylorcurranpython on GitHub

# Repository to grant access to
REPOSITORY_OWNER = "taylorcurranpython"
REPOSITORY_NAME = "prefect"

# ====================================

def main():
    """Add repository permissions to a Devin organization."""
    
    # API endpoint
    url = f"https://api.devin.ai/v2/enterprise/organizations/{ORG_ID}/git/permissions"
    
    # Request headers
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Permission data - must be sent as an array
    data = [{
        "connection_id": CONNECTION_ID,
        "repo_path": [REPOSITORY_OWNER, REPOSITORY_NAME]
    }]
    
    print(f"\nAdding permissions for: {REPOSITORY_OWNER}/{REPOSITORY_NAME}")
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