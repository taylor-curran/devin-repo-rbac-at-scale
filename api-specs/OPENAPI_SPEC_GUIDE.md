# Devin API OpenAPI Spec Generation Guide

## How It Works

The script `fetch_openapi_spec_split.py` generates OpenAPI 3.0.3 specs by:

1. **Fetching** official specs from Devin's Mintlify docs (adding `.md` to endpoint URLs)
2. **Extracting** embedded OpenAPI YAML from each markdown file
3. **Merging** into separate specs per version (v1, v2, v3)
4. **Converting** OAS 3.1 → 3.0.3 for APIGEE compatibility
5. **Validating** with `openapi-spec-validator`

## Output Files

| File | Description |
|------|-------------|
| `devin-api-v1.json` | Org-scoped: sessions, attachments, knowledge, playbooks, secrets |
| `devin-api-v2.json` | Enterprise admin: orgs, members, API keys, audit logs, consumption |
| `devin-api-v3.json` | Full RBAC: service users, roles, IDP groups, git permissions |

## Regenerate Specs

```bash
cd /Users/taylorcurran/Documents/dev/wf/devin-repo-rbac-at-scale/api-specs
source ../.venv/bin/activate  # or activate your venv
python fetch_openapi_spec_split.py
```

## Adding New Endpoints

1. Edit `fetch_openapi_spec_split.py`
2. Add the new endpoint path to the `ENDPOINT_PATHS` dict:

```python
ENDPOINT_PATHS = {
    "v3": [
        # ... existing endpoints ...
        "/api-reference/v3/new-category/new-endpoint",  # Add here
    ],
}
```

3. Run the script to regenerate

## Dependencies

```bash
uv pip install requests pyyaml openapi-spec-validator
```

## Validation

The script auto-validates each spec. To manually validate:

```bash
python -c "
from openapi_spec_validator import validate_spec
import json
spec = json.load(open('devin-api-v3.json'))
validate_spec(spec)
print('Valid!')
"
```
