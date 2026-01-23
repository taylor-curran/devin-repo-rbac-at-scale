#!/usr/bin/env python3
"""
Fetch official OpenAPI specs from Devin API documentation.
Generates SEPARATE spec files for v1, v2, and v3beta1.
"""

import re
import yaml
import json
import requests
from pathlib import Path

BASE_URL = "https://docs.devin.ai"

ENDPOINT_PATHS = {
    "v1": [
        "/api-reference/v1/sessions/list-sessions",
        "/api-reference/v1/sessions/create-a-new-devin-session",
        "/api-reference/v1/sessions/retrieve-details-about-an-existing-session",
        "/api-reference/v1/sessions/send-a-message-to-an-existing-devin-session",
        "/api-reference/v1/sessions/terminate-a-session",
        "/api-reference/v1/sessions/update-session-tags",
        "/api-reference/v1/attachments/upload-files-for-devin-to-work-with",
        "/api-reference/v1/knowledge/list-knowledge",
        "/api-reference/v1/knowledge/create-knowledge",
        "/api-reference/v1/knowledge/update-knowledge",
        "/api-reference/v1/knowledge/delete-knowledge",
        "/api-reference/v1/playbooks/list-playbooks",
        "/api-reference/v1/playbooks/create-playbook",
        "/api-reference/v1/playbooks/get-playbook",
        "/api-reference/v1/playbooks/update-playbook",
        "/api-reference/v1/playbooks/delete-playbook",
        "/api-reference/v1/secrets/list-secrets",
        "/api-reference/v1/secrets/delete-secret",
    ],
    "v2": [
        "/api-reference/v2/organizations/list-organizations",
        "/api-reference/v2/organizations/create-organization",
        "/api-reference/v2/organizations/get-organization-details",
        "/api-reference/v2/organizations/update-organization",
        "/api-reference/v2/organizations/delete-organization",
        "/api-reference/v2/members/list-enterprise-members",
        "/api-reference/v2/members/get-member-details",
        "/api-reference/v2/members/invite-enterprise-members",
        "/api-reference/v2/members/update-member-roles",
        "/api-reference/v2/members/delete-enterprise-member",
        "/api-reference/v2/members/list-roles",
        "/api-reference/v2/groups/list-enterprise-groups",
        "/api-reference/v2/groups/add-enterprise-groups",
        "/api-reference/v2/groups/get-group-details",
        "/api-reference/v2/api-keys/provision-service-key",
        "/api-reference/v2/api-keys/list-enterprise-api-keys",
        "/api-reference/v2/api-keys/revoke-enterprise-api-key",
        "/api-reference/v2/api-keys/revoke-all-enterprise-api-keys",
        "/api-reference/v2/audit-logs",
        "/api-reference/v2/consumption/consumption-cycles",
        "/api-reference/v2/consumption/daily-consumption",
        "/api-reference/v2/consumption/user-daily-consumption",
        "/api-reference/v2/consumption/pr-metrics",
        "/api-reference/v2/consumption/sessions-metrics",
        "/api-reference/v2/consumption/searches-metrics",
        "/api-reference/v2/consumption/usage-metrics",
        "/api-reference/v2/sessions/list-enterprise-sessions",
        "/api-reference/v2/sessions/list-enterprise-sessions-insights",
        "/api-reference/v2/sessions/get-enterprise-session",
        "/api-reference/v2/playbooks/list-playbooks",
        "/api-reference/v2/playbooks/create-playbook",
        "/api-reference/v2/playbooks/get-playbook",
        "/api-reference/v2/playbooks/update-playbook",
    ],
    "v3": [
        "/api-reference/v3/self/self",
        "/api-reference/v3/organizations/organizations",
        "/api-reference/v3/organizations/post-organizations",
        "/api-reference/v3/organizations/patch-organizations",
        "/api-reference/v3/organizations/delete-organizations",
        "/api-reference/v3/service-users/members-service-users",
        "/api-reference/v3/service-users/post-members-service-users",
        "/api-reference/v3/service-users/patch-members-service-users",
        "/api-reference/v3/service-users/delete-members-service-users",
        "/api-reference/v3/service-users/organizations-members-service-users",
        "/api-reference/v3/service-users/post-organizations-members-service-users",
        "/api-reference/v3/users/members-users",
        "/api-reference/v3/users/post-members-users",
        "/api-reference/v3/users/patch-members-users",
        "/api-reference/v3/users/delete-members-users",
        "/api-reference/v3/users/organizations-members-users",
        "/api-reference/v3/users/post-organizations-members-users",
        "/api-reference/v3/idp-groups/members-idp-groups",
        "/api-reference/v3/idp-groups/post-members-idp-groups",
        "/api-reference/v3/idp-groups/organizations-members-idp-groups",
        "/api-reference/v3/idp-groups/post-organizations-members-idp-groups",
        "/api-reference/v3/roles/roles",
        "/api-reference/v3/audit-logs/enterprise-audit-logs",
        "/api-reference/v3/audit-logs/organizations-audit-logs",
        "/api-reference/v3/consumption/consumption-cycles",
        "/api-reference/v3/consumption/consumption-daily",
        "/api-reference/v3/consumption/consumption-daily-organizations",
        "/api-reference/v3/consumption/consumption-daily-users",
        "/api-reference/v3/consumption/consumption-daily-sessions",
        "/api-reference/v3/playbooks/enterprise-playbooks",
        "/api-reference/v3/playbooks/post-enterprise-playbooks",
        "/api-reference/v3/playbooks/organizations-playbooks",
        "/api-reference/v3/git-permissions/organizations-git-providers-permissions",
        "/api-reference/v3/git-permissions/post-organizations-git-providers-permissions",
        "/api-reference/v3/sessions/organizations-sessions",
        "/api-reference/v3/sessions/post-organizations-sessions",
        "/api-reference/v3/sessions/delete-organizations-sessions",
    ],
}

VERSION_INFO = {
    "v1": {
        "title": "Devin API v1",
        "description": "Devin API v1 - Org-scoped session management, attachments, knowledge, playbooks, and secrets.",
        "version": "1.0.0"
    },
    "v2": {
        "title": "Devin API v2", 
        "description": "Devin API v2 - Enterprise admin APIs for organization management, members, API keys, audit logs, consumption metrics, and sessions.",
        "version": "2.0.0"
    },
    "v3": {
        "title": "Devin API v3beta1",
        "description": "Devin API v3beta1 - Full RBAC support with service user authentication for enterprise and organization management.",
        "version": "3.0.0-beta1"
    }
}


def fetch_md_content(path: str) -> str | None:
    """Fetch the .md content from a documentation path."""
    url = f"{BASE_URL}{path}.md"
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            return response.text
        else:
            print(f"  ⚠️  Failed to fetch {path}: HTTP {response.status_code}")
            return None
    except Exception as e:
        print(f"  ❌ Error fetching {path}: {e}")
        return None


def extract_openapi_from_md(md_content: str) -> dict | None:
    """Extract OpenAPI YAML from markdown content."""
    pattern = r'````yaml[^\n]*\n(openapi:.*?)````'
    match = re.search(pattern, md_content, re.DOTALL)
    
    if not match:
        pattern = r'```yaml[^\n]*\n(openapi:.*?)```'
        match = re.search(pattern, md_content, re.DOTALL)
    
    if match:
        yaml_content = match.group(1)
        try:
            return yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            print(f"  ⚠️  YAML parse error: {e}")
            return None
    return None


def deep_merge(base: dict, update: dict) -> dict:
    """Deep merge two dictionaries."""
    result = base.copy()
    for key, value in update.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def collect_referenced_schemas(paths: dict, all_schemas: dict) -> dict:
    """Collect only schemas that are referenced by the paths."""
    referenced = set()
    
    def find_refs(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key == "$ref" and isinstance(value, str):
                    # Extract schema name from "#/components/schemas/SchemaName"
                    if "/schemas/" in value:
                        schema_name = value.split("/schemas/")[-1]
                        referenced.add(schema_name)
                else:
                    find_refs(value)
        elif isinstance(obj, list):
            for item in obj:
                find_refs(item)
    
    find_refs(paths)
    
    # Recursively find schemas referenced by other schemas
    def find_nested_refs(schema_name: str, visited: set):
        if schema_name in visited or schema_name not in all_schemas:
            return
        visited.add(schema_name)
        find_refs(all_schemas[schema_name])
        for ref in list(referenced - visited):
            find_nested_refs(ref, visited)
    
    initial_refs = list(referenced)
    visited = set()
    for ref in initial_refs:
        find_nested_refs(ref, visited)
    
    # Return only referenced schemas
    return {name: all_schemas[name] for name in referenced if name in all_schemas}


def create_version_spec(version: str, specs: list[dict]) -> dict:
    """Create a single OpenAPI spec for a specific version."""
    info = VERSION_INFO[version]
    
    merged = {
        "openapi": "3.0.3",  # Use 3.0.3 for better APIGEE compatibility
        "info": {
            "title": info["title"],
            "description": info["description"],
            "version": info["version"],
            "contact": {
                "name": "Cognition Labs",
                "url": "https://docs.devin.ai"
            }
        },
        "servers": [
            {
                "url": "https://api.devin.ai",
                "description": "Production API Server"
            }
        ],
        "paths": {},
        "components": {
            "schemas": {},
            "securitySchemes": {
                "BearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "description": "API Key authentication. Use Personal API Key (apk_user_*) or Service API Key (apk_*) for v1/v2. Use Service User credential (cog_*) for v3."
                }
            }
        },
        "security": [{"BearerAuth": []}]
    }
    
    all_schemas = {}
    
    for spec in specs:
        if not spec:
            continue
            
        # Merge paths
        if "paths" in spec:
            for path, methods in spec["paths"].items():
                if path not in merged["paths"]:
                    merged["paths"][path] = {}
                merged["paths"][path] = deep_merge(merged["paths"][path], methods)
        
        # Collect all schemas
        if "components" in spec and "schemas" in spec["components"]:
            all_schemas = deep_merge(all_schemas, spec["components"]["schemas"])
    
    # Convert OAS 3.1 features to OAS 3.0.3 compatible format
    def convert_to_oas30(obj):
        if isinstance(obj, dict):
            result = {}
            for k, v in obj.items():
                # Remove OAS 3.1 only features
                if k in ["propertyNames"]:
                    continue
                # Remove title from properties (causes issues in some validators)
                if k == "title" and isinstance(obj.get("type"), str):
                    continue
                result[k] = convert_to_oas30(v)
            
            # Check for anyOf with null type pattern
            if "anyOf" in result and isinstance(result["anyOf"], list):
                non_null_types = [t for t in result["anyOf"] if not (isinstance(t, dict) and t.get("type") == "null")]
                has_null = any(isinstance(t, dict) and t.get("type") == "null" for t in result["anyOf"])
                
                if has_null and len(non_null_types) == 1:
                    # Convert to nullable format
                    converted = non_null_types[0].copy() if isinstance(non_null_types[0], dict) else {"type": non_null_types[0]}
                    converted["nullable"] = True
                    # Keep other properties except anyOf
                    for key in result:
                        if key not in ["anyOf"]:
                            converted[key] = result[key]
                    return converted
            
            # Handle nullable with array type - OAS 3.0.3 doesn't support nullable on arrays
            # Convert to oneOf pattern or just remove nullable for strict compliance
            if result.get("nullable") == True and result.get("type") == "array":
                # Remove nullable from arrays - APIGEE may not support it
                del result["nullable"]
            
            return result
        elif isinstance(obj, list):
            return [convert_to_oas30(item) for item in obj]
        return obj
    
    # Apply conversion
    merged["paths"] = convert_to_oas30(merged["paths"])
    all_schemas = convert_to_oas30(all_schemas)
    
    # Only include referenced schemas
    referenced_schemas = collect_referenced_schemas(merged["paths"], all_schemas)
    # Apply conversion to schemas too
    merged["components"]["schemas"] = convert_to_oas30(referenced_schemas)
    
    # Ensure all path parameters are defined in operations
    import re as regex
    for path, methods in merged["paths"].items():
        # Find path parameters like {org_id}, {session_id}, etc.
        path_params = regex.findall(r'\{(\w+)\}', path)
        if path_params:
            for method, operation in methods.items():
                if method in ["get", "post", "put", "patch", "delete"]:
                    if "parameters" not in operation:
                        operation["parameters"] = []
                    
                    existing_params = {p.get("name") for p in operation["parameters"] if p.get("in") == "path"}
                    
                    for param in path_params:
                        if param not in existing_params:
                            operation["parameters"].append({
                                "name": param,
                                "in": "path",
                                "required": True,
                                "schema": {"type": "string"},
                                "description": f"The {param.replace('_', ' ')}"
                            })
    
    # Sort paths
    merged["paths"] = dict(sorted(merged["paths"].items()))
    
    return merged


def validate_spec(spec: dict, version: str) -> bool:
    """Validate OpenAPI spec."""
    try:
        from openapi_spec_validator import validate
        from openapi_spec_validator.versions import OPENAPIV30
        validate(spec, cls=OPENAPIV30)
        print(f"  ✅ {version} spec is valid!")
        return True
    except ImportError:
        print(f"  ⚠️  openapi-spec-validator not installed, skipping validation")
        return True
    except Exception as e:
        print(f"  ⚠️  {version} validation issue: {e}")
        return False


def main():
    print("🔍 Fetching official OpenAPI specs from Devin documentation...\n")
    
    version_specs = {}
    
    for version, paths in ENDPOINT_PATHS.items():
        print(f"\n📦 Processing {version.upper()} API ({len(paths)} endpoints)...")
        
        specs = []
        for path in paths:
            md_content = fetch_md_content(path)
            if md_content:
                spec = extract_openapi_from_md(md_content)
                if spec:
                    specs.append(spec)
                    print(f"  ✅ {path}")
                else:
                    print(f"  ⚠️  No OpenAPI spec found in {path}")
        
        version_specs[version] = specs
    
    print("\n" + "="*60)
    print("🔧 Generating separate spec files...\n")
    
    output_dir = Path(__file__).parent
    
    for version, specs in version_specs.items():
        if not specs:
            print(f"  ❌ No specs for {version}")
            continue
            
        merged_spec = create_version_spec(version, specs)
        
        # Save JSON file
        json_file = output_dir / f"devin-api-{version}.json"
        with open(json_file, "w") as f:
            json.dump(merged_spec, f, indent=2)
        
        path_count = len(merged_spec["paths"])
        schema_count = len(merged_spec["components"]["schemas"])
        
        print(f"📄 {version.upper()}: {json_file.name}")
        print(f"   - {path_count} paths, {schema_count} schemas")
        
        # Validate
        validate_spec(merged_spec, version)
        print()
    
    print("="*60)
    print("✅ Done! Generated files:")
    print("   - devin-api-v1.json")
    print("   - devin-api-v2.json")
    print("   - devin-api-v3.json")


if __name__ == "__main__":
    main()
