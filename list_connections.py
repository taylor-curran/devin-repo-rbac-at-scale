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
ORG_ID = "org-462b0fb046724b299a37f0830095aff7" 

# ====================================

def main():
    """List all Git connections for an organization."""
    
    # API endpoint - connections are per organization
    url = f"https://api.devin.ai/v2/enterprise/organizations/{ORG_ID}/git/connections"
    
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
        
        # Get connections from response
        connections = data.get('items', [])
        
        # Display connections
        print(f"\nGit Connections for Organization: {ORG_ID}")
        print("=" * 60)
        
        if not connections:
            print("No Git connections found for this organization.")
            print("You may need to set up Git integrations in Devin Enterprise.")
        else:
            for conn in connections:
                # v2 API uses different field names
                conn_id = conn.get('id', conn.get('connection_id', 'No ID'))
                conn_name = conn.get('name', 'Unnamed')
                provider_type = conn.get('type', conn.get('provider', 'Unknown'))
                host = conn.get('host', 'No host')
                
                print(f"Name:       {conn_name}")
                print(f"ID:         {conn_id}")
                print(f"Provider:   {provider_type}")
                print(f"Host:       {host}")
                print("-" * 60)
        
        print(f"\nTotal: {len(connections)} connections")
        
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            print(f"Details: {e.response.text}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
