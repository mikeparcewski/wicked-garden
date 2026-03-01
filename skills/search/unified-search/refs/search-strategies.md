# Search Strategies

Effective strategies for finding information across code and documents.

## Strategy 1: Start Broad, Then Narrow

```
# 1. Broad search across everything
/wicked-garden:search:search authentication

# 2. Narrow to docs if looking for specs
/wicked-garden:search:docs "authentication requirements"

# 3. Narrow to code if looking for implementation
/wicked-garden:search:code AuthService
```

## Strategy 2: Doc-First for Understanding

When understanding a feature:

```
# 1. Find documentation
/wicked-garden:search:docs "user registration"

# 2. Read the relevant doc section
cat {SM_LOCAL_ROOT}/wicked-search/extracted/requirements_docx.txt

# 3. Find implementing code
/wicked-garden:search:impl "User Registration"

# 4. Read the code
Read src/auth/registration.py
```

## Strategy 3: Code-First for Impact Analysis

When changing code:

```
# 1. Find the code symbol
/wicked-garden:search:code UserService

# 2. Find all references
/wicked-garden:search:refs UserService

# 3. Check documentation that might need updating
# (Look at "Documented in" section)

# 4. Find dependent code
# (Look at "Referenced by" section)
```

## Strategy 4: Tracing Requirements

```
# 1. Search for requirement
/wicked-garden:search:docs "REQ-AUTH-001"

# 2. Find implementing code
/wicked-garden:search:impl "REQ-AUTH-001"

# 3. Verify coverage
/wicked-garden:search:refs <each implementing symbol>
```

## Query Tips

### Use Specific Terms
- Bad: "login"
- Good: "authenticate_user" or "LoginHandler"

### Use Quotes for Phrases
- `/wicked-garden:search:docs "rate limiting"` (exact phrase)
- `/wicked-garden:search:docs rate limiting` (both words separately)

### Combine Searches
```
# Search docs for feature name
/wicked-garden:search:docs "OAuth integration"

# Then search code for mentioned symbols
/wicked-garden:search:code OAuthClient
```

## When Search Doesn't Find Results

1. **Check if indexed**: `/wicked-garden:search:stats`
2. **Re-index**: `/wicked-garden:search:index . --force`
3. **Try alternate terms**: synonyms, abbreviations
4. **Use ripgrep for exact text**: `rg "exact phrase" docs/`
