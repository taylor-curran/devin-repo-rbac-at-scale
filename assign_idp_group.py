import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ========== CONFIGURATION ==========
# Your Devin API Key (Service User credential with prefix: cog_)
API_KEY = os.getenv("DEVIN_SERVICE_ACCOUNT_API_KEY", "YOUR_API_KEY_HERE")

# Organization ID to assign the IDP group to
ORG_ID = "org-45ecc3f2730d46a5a7ebe433d0813678"  # taylor-demos

# IDP group name (must match exactly as it appears in your Identity Provider)
IDP_GROUP_NAME = "My-SSO-Group"

# Role to assign - use list_roles.py to see available roles
# Built-in roles: "org_member", "org_admin", "org_deepwiki", "account_admin", "account_member"
# Custom roles look like: "role-ba0343eca0d34ddc98f19c38222de668"
ROLE_ID = "org_member"

# ====================================

def main():
    """Assign an IDP group to a Devin organization with a specific role.
    
    This enables JIT (Just-In-Time) provisioning: when users in this IDP group
    sign in via SSO, they'll automatically get access to this organization.
    
    Tip: Run list_roles.py first to see available role IDs.
    """
    
    # API endpoint (v3beta1) - assign IDP group to specific org
    url = f"https://api.devin.ai/v3beta1/enterprise/organizations/{ORG_ID}/members/idp-groups/{IDP_GROUP_NAME}"
    
    # Request headers
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Request body
    data = {
        "role_id": ROLE_ID
    }
    
    print(f"\nAssigning IDP group to organization:")
    print(f"  IDP Group: {IDP_GROUP_NAME}")
    print(f"  Org ID:    {ORG_ID}")
    print(f"  Role:      {ROLE_ID}")
    
    try:
        # Make the API request
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        
        print("\n✓ IDP group assigned!")
        print(f"\nUsers in '{IDP_GROUP_NAME}' will now get '{ROLE_ID}' access")
        print(f"to organization '{ORG_ID}' when they sign in via SSO.")
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
