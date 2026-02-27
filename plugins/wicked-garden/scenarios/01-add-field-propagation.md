---
name: add-field-propagation
title: Add Field with Multi-Language Propagation
description: Add a field to an entity and propagate changes across Java, Python, and SQL
type: patch
difficulty: basic
estimated_minutes: 8
---

# Add Field with Multi-Language Propagation

This scenario demonstrates wicked-patch's core capability: adding a field to a data model and automatically generating appropriate changes across multiple languages (Java entity, Python ORM, SQL schema).

## Setup

Create a minimal multi-language project with a User entity:

```bash
# Create project structure
mkdir -p /tmp/wicked-patch-test/user-service/{src/main/java/com/example,models,migrations}
cd /tmp/wicked-patch-test/user-service

# Java entity
cat > src/main/java/com/example/User.java << 'EOF'
package com.example;

public class User {
    private Long id;
    private String username;

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public String getUsername() {
        return username;
    }

    public void setUsername(String username) {
        this.username = username;
    }
}
EOF

# Python SQLAlchemy model
cat > models/user.py << 'EOF'
from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    username = Column(String(255), nullable=False)
EOF

# SQL schema
cat > migrations/001_create_users.sql << 'EOF'
CREATE TABLE users (
    id BIGINT PRIMARY KEY,
    username VARCHAR(255) NOT NULL
);
EOF

echo "Test project created at /tmp/wicked-patch-test/user-service"
```

## Steps

### 1. Index the codebase

First, build the symbol graph so wicked-patch can understand your code structure:

```bash
/wicked-search:index /tmp/wicked-patch-test/user-service
```

### 2. Preview the change plan

See what would be affected before making changes:

```bash
/wicked-patch:plan "src/main/java/com/example/User.java::User" --change add_field
```

**Expected output**: A PROPAGATION PLAN showing:
- Source: User entity in User.java
- Direct impacts: entity fields in User.java
- Risk assessment with risk level and confidence

### 3. Generate patches for the email field

Add the email field and generate patches for all languages:

```bash
/wicked-patch:add-field "src/main/java/com/example/User.java::User" --name email --type String --required -o /tmp/wicked-patch-test/user-service/.patches/patches.json --verbose
```

**Expected output**: A GENERATED PATCHES block showing patches grouped by file, including:
- User.java: field declaration + getter + setter
- Possibly user.py: Column definition (if Python model discovered via graph)
- Possibly SQL migration (if SQL schema discovered via graph)

### 4. Review generated patches

Check the patches file:

```bash
ls -la /tmp/wicked-patch-test/user-service/.patches/
cat /tmp/wicked-patch-test/user-service/.patches/manifest.json
```

**Expected**: A manifest.json with metadata (change_type, target, files_affected, patch_count) and the patches JSON file.

### 5. Apply the patches

Apply the generated patches:

```bash
/wicked-patch:apply /tmp/wicked-patch-test/user-service/.patches/patches.json --skip-git --force
```

When prompted with `Apply N patches to N files? [y/N]`, type `y` and press Enter to confirm.

### 6. Verify changes

Check that the Java entity was updated:

```bash
# Check Java entity has email field and getters/setters
grep -n "email" /tmp/wicked-patch-test/user-service/src/main/java/com/example/User.java

# Check if Python model was updated (may or may not be, depending on graph)
grep -n "email" /tmp/wicked-patch-test/user-service/models/user.py || echo "Python model not updated (graph may not have linked it)"
```

## Expected Outcome

After step 2 (plan), you should see a PROPAGATION PLAN block:
```
============================================================
PROPAGATION PLAN
============================================================

Source: User
  Type: entity
  File: .../User.java
  ...

Direct Impacts (N):
  ...

------------------------------------------------------------
Risk Assessment:
  Risk level: LOW
  ...
------------------------------------------------------------
Total: N symbols in N files
============================================================
```

After step 3 (add-field), you should see a GENERATED PATCHES block:
```
============================================================
GENERATED PATCHES
============================================================

Change: add_field
Target: ...User.java::User
...

PATCHES:

  User.java
    [...] Add field 'email' (String)
    [...] Add getter for 'email'
    [...] Add setter for 'email'

============================================================
```

After step 5 (apply), User.java should contain:
```java
private String email;

public String getEmail() {
    return email;
}

public void setEmail(String email) {
    this.email = email;
}
```

## Success Criteria

- [ ] Symbol graph indexed successfully via wicked-search
- [ ] Plan command showed propagation plan without errors
- [ ] Java entity has email field with getter and setter methods
- [ ] Patches were saved to the output file and manifest.json generated
- [ ] All patches applied without errors
- [ ] Changes follow Java naming conventions (camelCase)

## Value Demonstrated

**Real-world problem**: When adding a field to a data model, developers must manually update multiple files across different languages (backend entity, ORM model, database schema). This is error-prone and time-consuming.

**wicked-patch solution**: One command propagates the change across all language layers automatically, ensuring consistency and completeness.

**Time saved**: 10-15 minutes per field (manual search, edit, test) -> 1 minute (one command)

**Risk reduced**: Eliminates forgotten updates (e.g., adding a field to Java but forgetting the SQL migration), which cause runtime errors in production.
