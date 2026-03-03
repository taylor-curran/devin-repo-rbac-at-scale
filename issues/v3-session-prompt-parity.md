# V3 API: Session Prompt Not Returned (Parity Issue with V1/V2)

## Summary

While testing V3 APIs for enterprise session management, we identified a gap: the V3 session GET endpoint does not return the session prompt/initial user message.

## V3 Context

The V3 API supports getting session details:

```
GET /v3beta1/enterprise/sessions/{session_id}
GET /v3beta1/organizations/{org_id}/sessions/{session_id}
```

https://docs.devin.ai/api-reference/v3/sessions/get-enterprise-session

However, the response does not include the `prompt`, `initial_user_message`, or `messages` fields that are available in V1/V2.

**V3 Response Fields:**
- `session_id`, `url`, `status`, `title`, `tags`
- `user_id`, `org_id`, `created_at`, `updated_at`
- `acus_consumed`, `pull_requests`, `structured_output`
- `is_advanced`, `is_archived`, `parent_session_id`, `child_session_ids`

**Missing:** `prompt`, `initial_user_message`, `messages`

## V1/V2 Context

**V1** (`GET /v1/sessions/{session_id}`) returns:
```json
{
  "messages": [
    {
      "type": "initial_user_message",
      "message": "...",
      ...
    }
  ]
}
```

**V2** (`GET /v2/enterprise/sessions/{session_id}`) returns:
```json
{
  "initial_user_message": "...",
  "session_analysis": {
    "suggested_prompt": {
      "original_prompt": "..."
    }
  }
}
```

## Impact

- Wells Fargo requires this for their audit/analytics workflows
  
## Ask

Add session prompt/initial user message to V3 session GET response for parity with V1/V2:

1. Include `initial_user_message` field in `GET /v3beta1/enterprise/sessions/{session_id}` response
2. Include `initial_user_message` field in `GET /v3beta1/organizations/{org_id}/sessions/{session_id}` response
3. Optionally include `messages` array for full conversation history (matching V1 behavior)
