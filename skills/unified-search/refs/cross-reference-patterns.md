# Cross-Reference Patterns

How to effectively use cross-references between code and documentation.

## Understanding Cross-References

Cross-references are automatically detected links between:
- **Document sections** → **Code symbols**

When a document mentions a code symbol name, the indexer creates a "documents" edge.

## Detection Patterns

### 1. CamelCase Names
```
Document: "The AuthService class handles all authentication..."
         ↓
Detected: AuthService
         ↓
Links to: src/auth/service.py::AuthService
```

### 2. snake_case Names
```
Document: "Call authenticate_user() to validate credentials..."
         ↓
Detected: authenticate_user
         ↓
Links to: src/auth/handlers.py::authenticate_user
```

### 3. Backtick Quoted
```
Document: "Use `UserRepository.find_by_id()` to fetch users..."
         ↓
Detected: UserRepository, find_by_id
         ↓
Links to respective code symbols
```

## Querying Cross-References

### Find where code is documented
```
/wicked-garden:search:refs MyClassName
```

Output shows:
- `Documented in:` - Doc sections mentioning this symbol
- `Referenced by:` - Code that uses this symbol
- `References:` - What this symbol uses

### Find code for a doc section
```
/wicked-garden:search:impl "Authentication Flow"
```

Output shows all code symbols mentioned in that doc section.

## Workflow Example

**Goal**: Understand the authentication system

1. Search for auth in docs:
   ```
   /wicked-garden:search:docs authentication
   ```

2. Find a relevant section, e.g., "Authentication Flow"

3. Find implementing code:
   ```
   /wicked-garden:search:impl "Authentication Flow"
   ```

4. For each code symbol, find its documentation:
   ```
   /wicked-garden:search:refs AuthService
   ```

## Limitations

- Only detects explicit symbol names
- No semantic understanding (won't link "user login" to `authenticate()`)
- Requires exact or fuzzy name matches
