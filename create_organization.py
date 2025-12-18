import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ========== CONFIGURATION ==========
# Your Devin API Key (Service User credential with prefix: cog_)
API_KEY = os.getenv("DEVIN_SERVICE_ACCOUNT_API_KEY", "YOUR_API_KEY_HERE")

# New organization name
ORG_NAME = "my-new-org"

# Optional: ACU limits (set to None to use defaults)
MAX_CYCLE_ACU_LIMIT = None    # Max ACUs per billing cycle
MAX_SESSION_ACU_LIMIT = None  # Max ACUs per session

# ====================================

def main():
    """Create a new organization in Devin Enterprise."""
    
    # API endpoint (v3beta1)
    url = "https://api.devin.ai/v3beta1/enterprise/organizations"
    
    # Request headers
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Request body
    data = {
        "name": ORG_NAME
    }
    
    # Add optional limits if specified
    if MAX_CYCLE_ACU_LIMIT is not None:
        data["max_cycle_acu_limit"] = MAX_CYCLE_ACU_LIMIT
    if MAX_SESSION_ACU_LIMIT is not None:
        data["max_session_acu_limit"] = MAX_SESSION_ACU_LIMIT
    
    print(f"\nCreating organization: {ORG_NAME}")
    
    try:
        # Make the API request
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        
        print("\n✓ Organization created!")
        print(f"  Name:   {result.get('name')}")
        print(f"  Org ID: {result.get('org_id')}")
        print(f"\nFull response:")
        print(json.dumps(result, indent=2))
        
    except requests.exceptions.RequestException as e:
        print(f"\nError: {e}")
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            print(f"Details: {e.response.text}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
