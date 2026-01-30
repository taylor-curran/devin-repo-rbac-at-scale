#!/usr/bin/env python3
"""
Fetch official OpenAPI specs from Devin API documentation.
Generates SEPARATE spec files for v1, v2, and v3beta1.

Auto-discovers endpoints by scraping the docs sidebar navigation.
"""

import re
import yaml
import json
import requests
from bs4 import BeautifulSoup
from pathlib import Path

BASE_URL = "https://docs.devin.ai"

# Supplementary endpoints that may not appear in sidebar but exist in docs
# These are checked in addition to auto-discovered endpoints
# NOTE: Only add endpoints here that are confirmed to exist (not 404)
SUPPLEMENTARY_ENDPOINTS = {
    "v1": [],
    "v2": [],
    "v3": [
        # Hypervisors - not always linked in sidebar
        "/api-reference/v3/hypervisors/hypervisors",
        # Git connections - not always linked in sidebar
        "/api-reference/v3/git-connections/git-providers-connections",
        # Service user provisioning - not always linked in sidebar
        "/api-reference/v3/service-users/provision-enterprise-service-users",
        # Secrets endpoints
        "/api-reference/v3/secrets/organizations-secrets",
        "/api-reference/v3/secrets/post-organizations-secrets",
        "/api-reference/v3/secrets/delete-organizations-secrets",
    ],
}

# Fallback hardcoded paths (used only if auto-discovery fails completely)
FALLBACK_ENDPOINT_PATHS = {
    "v1": [
        "/api-reference/v1/sessions/list-sessions",
        "/api-reference/v1/sessions/create-a-new-devin-session",
    ],
    "v2": [
        "/api-reference/v2/organizations/list-organizations",
    ],
    "v3": [
        "/api-reference/v3/self/self",
    ],
}


def discover_endpoints_from_sidebar(version: str) -> list[str]:
    """
    Auto-discover all endpoint documentation pages by scraping the docs sidebar.
    This ensures we never miss new endpoints.
    """
    overview_url = f"{BASE_URL}/api-reference/{version}/overview"
    print(f"  🔍 Discovering {version} endpoints from {overview_url}...")
    
    try:
        response = requests.get(overview_url, timeout=30)
        if response.status_code != 200:
            print(f"  ⚠️  Could not fetch overview page: HTTP {response.status_code}")
            return []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all links in the sidebar that match the API reference pattern
        endpoints = set()
        version_pattern = f"/api-reference/{version}/"
        
        for link in soup.find_all('a', href=True):
            href = link['href']
            # Match links like /api-reference/v3/service-users/provision-enterprise-service-users
            if href.startswith(version_pattern):
                # Skip overview and usage-examples pages
                if '/overview' in href or '/usage-examples' in href or '/structured-output' in href:
                    continue
                # Must have at least category/endpoint structure
                parts = href.replace(version_pattern, '').split('/')
                if len(parts) >= 2:
                    endpoints.add(href)
        
        discovered = sorted(list(endpoints))
        print(f"  ✅ Discovered {len(discovered)} endpoints from sidebar")
        return discovered
        
    except Exception as e:
        print(f"  ❌ Error discovering endpoints: {e}")
        return []

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
            
            # Convert OAS 3.1 exclusiveMinimum/exclusiveMaximum (number) to OAS 3.0 format (boolean)
            # In OAS 3.1: exclusiveMinimum: 0 means value must be > 0
            # In OAS 3.0: minimum: 0, exclusiveMinimum: true
            # Note: isinstance(True, int) is True in Python, so check bool first
            if "exclusiveMinimum" in result and not isinstance(result["exclusiveMinimum"], bool) and isinstance(result["exclusiveMinimum"], (int, float)):
                val = result["exclusiveMinimum"]
                result["minimum"] = val
                result["exclusiveMinimum"] = True
            if "exclusiveMaximum" in result and not isinstance(result["exclusiveMaximum"], bool) and isinstance(result["exclusiveMaximum"], (int, float)):
                val = result["exclusiveMaximum"]
                result["maximum"] = val
                result["exclusiveMaximum"] = True
            
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
    
    # Sort paths and schemas alphabetically for deterministic output
    merged["paths"] = dict(sorted(merged["paths"].items()))
    merged["components"]["schemas"] = dict(sorted(merged["components"]["schemas"].items()))
    
    return merged


def validate_spec(spec: dict, version: str) -> bool:
    """Validate OpenAPI spec."""
    try:
        from openapi_spec_validator import validate_spec as validate_openapi
        validate_openapi(spec)
        print(f"  ✅ {version} spec is valid!")
        return True
    except ImportError:
        print(f"  ⚠️  openapi-spec-validator not installed, skipping validation")
        return True
    except Exception as e:
        print(f"  ⚠️  {version} validation issue: {e}")
        return False


def validate_completeness(spec: dict, discovered_paths: list[str], version: str) -> bool:
    """
    Validate that the spec contains endpoints for all successfully fetched doc pages.
    
    This checks that the number of spec paths roughly matches the number of doc pages
    that had OpenAPI content. Some variance is expected since multiple doc pages 
    can map to the same API path (e.g., GET/POST/DELETE on same path).
    """
    spec_paths = spec.get("paths", {})
    spec_path_count = len(spec_paths)
    doc_count = len(discovered_paths)
    
    # Count HTTP methods in spec (each doc page typically = 1 method)
    method_count = 0
    for path, methods in spec_paths.items():
        for method in methods:
            if method in ["get", "post", "put", "patch", "delete"]:
                method_count += 1
    
    # Check if method count is close to doc count (allow some variance)
    # Doc pages map to methods, not paths
    diff = abs(method_count - doc_count)
    ratio = method_count / doc_count if doc_count > 0 else 0
    
    if ratio >= 0.8:  # At least 80% coverage
        print(f"  ✅ {version} completeness: {method_count} methods from {doc_count} doc pages ({ratio:.0%} coverage)")
        return True
    else:
        print(f"  ⚠️  {version} completeness: only {method_count} methods from {doc_count} doc pages ({ratio:.0%} coverage)")
        print(f"      Some endpoints may be missing - review supplementary list")
        return False


def main():
    print("🔍 Fetching official OpenAPI specs from Devin documentation...")
    print("   Using auto-discovery to find ALL endpoints...\n")
    
    version_specs = {}
    version_discovered_paths = {}  # Track discovered paths for completeness check
    
    for version in ["v1", "v2", "v3"]:
        # Auto-discover endpoints from the docs sidebar
        paths = discover_endpoints_from_sidebar(version)
        
        # Fallback to hardcoded paths if discovery fails
        if not paths:
            print(f"  ⚠️  Auto-discovery failed, using fallback paths")
            paths = FALLBACK_ENDPOINT_PATHS.get(version, [])
        
        # Add supplementary endpoints that may not be in sidebar
        supplementary = SUPPLEMENTARY_ENDPOINTS.get(version, [])
        if supplementary:
            paths_set = set(paths)
            added = 0
            for ep in supplementary:
                if ep not in paths_set:
                    paths.append(ep)
                    added += 1
            if added:
                print(f"  ➕ Added {added} supplementary endpoints")
        
        # Store discovered paths for completeness validation
        version_discovered_paths[version] = paths.copy()
        
        print(f"\n📦 Processing {version.upper()} API ({len(paths)} endpoints)...")
        
        specs = []
        successful_paths = []
        for path in paths:
            md_content = fetch_md_content(path)
            if md_content:
                spec = extract_openapi_from_md(md_content)
                if spec:
                    specs.append(spec)
                    successful_paths.append(path)
                    print(f"  ✅ {path}")
                else:
                    print(f"  ⚠️  No OpenAPI spec found in {path}")
        
        version_specs[version] = specs
        version_discovered_paths[version] = successful_paths  # Only count successful extractions
    
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
        
        # Validate OpenAPI spec structure
        validate_spec(merged_spec, version)
        
        # Validate completeness - check if all discovered docs are in the spec
        discovered = version_discovered_paths.get(version, [])
        validate_completeness(merged_spec, discovered, version)
        print()
    
    print("="*60)
    print("✅ Done! Generated files:")
    print("   - devin-api-v1.json")
    print("   - devin-api-v2.json")
    print("   - devin-api-v3.json")


if __name__ == "__main__":
    main()
