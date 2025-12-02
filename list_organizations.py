import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ========== CONFIGURATION ==========
# Your Devin API Key
API_KEY = os.getenv("DEVIN_API_KEY", "YOUR_API_KEY_HERE")

# ====================================

def main():
    """List all organizations in your Devin Enterprise account."""
    
    # API endpoint
    url = "https://api.devin.ai/v2/enterprise/organizations"
    
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
        
        # Get organizations from response
        organizations = data.get('items', [])
        
        # Display organizations
        print("\nOrganizations:")
        print("-" * 40)
        for org in organizations:
            org_name = org.get('org_name', 'Unnamed')  # Fixed: API uses 'org_name' not 'name'
            org_id = org.get('org_id', 'No ID')
            print(f"Name: {org_name}")
            print(f"ID:   {org_id}")
            print("-" * 40)
        
        print(f"\nTotal: {len(organizations)} organizations")
        
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            print(f"Details: {e.response.text}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
