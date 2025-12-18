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
    """List all Git connections at the enterprise level."""
    
    # API endpoint (v3beta1) - connections are now enterprise-level, not org-scoped
    url = "https://api.devin.ai/v3beta1/enterprise/git-providers/connections"
    
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
        print("\nEnterprise Git Connections:")
        print("=" * 60)
        
        if not connections:
            print("No Git connections found.")
            print("You may need to set up Git integrations in Devin Enterprise.")
        else:
            for conn in connections:
                conn_id = conn.get('git_connection_id', 'No ID')
                conn_name = conn.get('name', 'Unnamed')
                provider_type = conn.get('git_provider_type', 'Unknown')
                host = conn.get('host', 'No host')
                
                print(f"Name:       {conn_name}")
                print(f"ID:         {conn_id}")
                print(f"Provider:   {provider_type}")
                print(f"Host:       {host}")
                print("-" * 60)
        
        print(f"\nTotal: {len(connections)} connections")
        
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
