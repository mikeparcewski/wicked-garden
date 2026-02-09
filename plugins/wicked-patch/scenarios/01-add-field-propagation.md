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
/wicked-patch:plan --entity User --add-field email:String --project /tmp/wicked-patch-test/user-service
```

### 3. Generate patches for the email field

Add the email field and generate patches for all languages:

```bash
/wicked-patch:add-field --entity User --name email --type String --required true --project /tmp/wicked-patch-test/user-service
```

### 4. Review generated patches

Check the patches directory:

```bash
ls -la /tmp/wicked-patch-test/user-service/.patches/
cat /tmp/wicked-patch-test/user-service/.patches/add-email-*.json
```

### 5. Apply the patches

Apply all generated patches to your codebase:

```bash
/wicked-patch:apply --patches /tmp/wicked-patch-test/user-service/.patches/ --project /tmp/wicked-patch-test/user-service
```

### 6. Verify changes

Check that all files were updated:

```bash
# Check Java entity has email field and getters/setters
grep -A 3 "private String email" /tmp/wicked-patch-test/user-service/src/main/java/com/example/User.java

# Check Python model has email column
grep "email" /tmp/wicked-patch-test/user-service/models/user.py

# Check SQL migration was generated
cat /tmp/wicked-patch-test/user-service/migrations/002_add_email_to_users.sql
```

## Expected Outcome

After step 2 (plan), you should see:
```
Change Plan: Add field 'email' to User
Affected files: 3
- src/main/java/com/example/User.java (Java entity)
- models/user.py (Python SQLAlchemy)
- migrations/ (new SQL migration)

Risk assessment: LOW
Estimated changes: 15-20 lines across 3 files
```

After step 3 (add-field), you should see:
```
Generated patches:
- add-email-java-entity.json (3 changes: field + getter + setter)
- add-email-python-model.json (1 change: column definition)
- add-email-sql-migration.json (new file: ALTER TABLE statement)

Patches saved to: /tmp/wicked-patch-test/user-service/.patches/
```

After step 5 (apply), all files should be updated:

**Java User.java** - should contain:
```java
private String email;

public String getEmail() {
    return email;
}

public void setEmail(String email) {
    this.email = email;
}
```

**Python user.py** - should contain:
```python
email = Column(String(255), nullable=False)
```

**New SQL migration** - `002_add_email_to_users.sql`:
```sql
ALTER TABLE users ADD COLUMN email VARCHAR(255) NOT NULL;
```

## Success Criteria

- [ ] Symbol graph indexed successfully via wicked-search
- [ ] Plan command showed all 3 affected files correctly
- [ ] Java entity has email field with getter and setter methods
- [ ] Python SQLAlchemy model has email Column definition
- [ ] New SQL migration file created with ALTER TABLE statement
- [ ] All patches applied without conflicts or errors
- [ ] Changes follow language-specific conventions (camelCase in Java, snake_case in SQL)

## Value Demonstrated

**Real-world problem**: When adding a field to a data model, developers must manually update multiple files across different languages (backend entity, ORM model, database schema). This is error-prone and time-consuming.

**wicked-patch solution**: One command propagates the change across all language layers automatically, ensuring consistency and completeness.

**Time saved**: 10-15 minutes per field (manual search, edit, test) → 1 minute (one command)

**Risk reduced**: Eliminates forgotten updates (e.g., adding a field to Java but forgetting the SQL migration), which cause runtime errors in production.
