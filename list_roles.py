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
    """List all available roles in the enterprise."""
    
    # API endpoint (v3beta1)
    url = "https://api.devin.ai/v3beta1/enterprise/roles"
    
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
        
        # Get roles from response
        roles = data.get('items', [])
        
        # Display roles
        print("\nAvailable Roles:")
        print("=" * 50)
        
        if not roles:
            print("No roles found.")
        else:
            for role in roles:
                role_id = role.get('role_id', 'Unknown')
                role_name = role.get('role_name', 'Unknown')
                role_type = role.get('role_type', 'Unknown')
                
                print(f"  {role_name}")
                print(f"    ID:   {role_id}")
                print(f"    Type: {role_type}")
                print("-" * 50)
        
        print(f"\nTotal: {len(roles)} roles")
        
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            print(f"Details: {e.response.text}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
