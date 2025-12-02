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

# Repositories to index (format: owner/repo)
REPOSITORIES = [
    "taylorcurranpython/prefect"
]

# ====================================

def main():
    """Index repositories for use in Devin sessions."""
    
    # API endpoint
    url = "https://api.devin.ai/beta/v2/enterprise/repositories/bulk-index"
    
    # Request headers
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Request data
    data = {
        "org_id": ORG_ID,
        "repo_names": REPOSITORIES
    }
    
    print(f"\nIndexing repositories for organization: {ORG_ID}")
    print("Repositories to index:")
    for repo in REPOSITORIES:
        print(f"  - {repo}")
    
    try:
        # Make the API request
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        
        print("\n✓ Indexing started successfully!")
        print(f"Response: {json.dumps(result, indent=2)}")
        print("\nNote: Indexing is asynchronous. Use the repository status endpoint to check progress.")
        
    except requests.exceptions.RequestException as e:
        print(f"\nError: {e}")
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            print(f"Details: {e.response.text}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
