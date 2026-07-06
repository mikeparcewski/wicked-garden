# Daemon HTTP API

The wicked-garden daemon exposes a local HTTP API (default port 7333) for reading garden state and issuing commands.

## State endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/state` | Current garden state snapshot |
| POST | `/council` | Run a synchronous council session |
| GET | `/council/{session_id}` | Council session status |

## Hook management

| Method | Path | Description |
|--------|------|-------------|
| POST | `/hooks` | Register a bus event hook |
| GET | `/hooks` | List all registered hooks |
| DELETE | `/hooks/{id}` | Deregister a hook by id |

### POST /hooks

Body:
```json
{
  "event_pattern": "wicked.signals.*",
  "command": "python3 /path/to/handler.py",
  "description": "Handle signal events"
}
```

Response 201:
```json
{"id": "uuid", "event_pattern": "wicked.signals.*", "command": "...", "created_at": "..."}
```

### DELETE /hooks/{id}

Response 200: `{"ok": true, "id": "uuid"}`
Response 404: `{"error": {"code": "NOT_FOUND", "message": "Hook not found"}}`

## Council voting

| Method | Path | Description |
|--------|------|-------------|
| POST | `/council/vote` | Cast a vote on a council session |

### POST /council/vote

Body:
```json
{
  "session_id": "sess-uuid",
  "voter_id": "agent-1",
  "vote": "approve",
  "rationale": "Evidence is sufficient"
}
```

Response 200: `{"ok": true, "session_id": "...", "voter_id": "..."}`
Response 404: `{"error": {"code": "NOT_FOUND", "message": "Session not found"}}`

## Error format

All error responses use the nested format:
```json
{"error": {"code": "NOT_FOUND", "message": "Human-readable description"}}
```

Codes: `INVALID_REQUEST` (400), `NOT_FOUND` (404), `METHOD_NOT_ALLOWED` (405), `INTERNAL_ERROR` (500).
