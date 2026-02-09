---
name: remove-field-cleanup
title: Complete Field Removal and Cleanup
description: Remove a deprecated field and clean up all references, migrations, and related code
type: propagation
difficulty: intermediate
estimated_minutes: 10
---

# Complete Field Removal and Cleanup

This scenario demonstrates safe field deprecation: removing a field from an entity and automatically cleaning up ALL related code (entity definition, getters/setters, references, database schema, tests). Proves wicked-patch prevents orphaned code.

## Setup

Create a user system with a deprecated "lastLogin" field that needs removal:

```bash
# Create project structure
mkdir -p /tmp/wicked-patch-cleanup/{models,services,repositories,migrations,tests}
cd /tmp/wicked-patch-cleanup

# User entity with deprecated field
cat > models/User.java << 'EOF'
package com.app.models;

import java.time.LocalDateTime;

public class User {
    private Long id;
    private String email;
    private String passwordHash;

    // DEPRECATED: Use loginHistory table instead
    private LocalDateTime lastLogin;

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public String getEmail() {
        return email;
    }

    public void setEmail(String email) {
        this.email = email;
    }

    public LocalDateTime getLastLogin() {
        return lastLogin;
    }

    public void setLastLogin(LocalDateTime lastLogin) {
        this.lastLogin = lastLogin;
    }

    public String getPasswordHash() {
        return passwordHash;
    }

    public void setPasswordHash(String passwordHash) {
        this.passwordHash = passwordHash;
    }
}
EOF

# Service using the deprecated field
cat > services/AuthService.java << 'EOF'
package com.app.services;

import com.app.models.User;
import java.time.LocalDateTime;

public class AuthService {
    public void recordLogin(User user) {
        // DEPRECATED: Should use LoginHistoryService instead
        user.setLastLogin(LocalDateTime.now());
    }

    public boolean isRecentLogin(User user) {
        if (user.getLastLogin() == null) {
            return false;
        }
        return user.getLastLogin().isAfter(
            LocalDateTime.now().minusHours(24)
        );
    }
}
EOF

# Repository query using the field
cat > repositories/UserRepository.java << 'EOF'
package com.app.repositories;

import com.app.models.User;
import java.time.LocalDateTime;

public class UserRepository {
    public void updateLastLogin(Long userId, LocalDateTime timestamp) {
        // DEPRECATED: Remove when lastLogin field is removed
        String sql = "UPDATE users SET last_login = ? WHERE id = ?";
        // Execute SQL...
    }

    public List<User> findRecentlyActive() {
        String sql = "SELECT * FROM users WHERE last_login > ?";
        // Execute SQL...
    }
}
EOF

# Original migration
cat > migrations/001_create_users.sql << 'EOF'
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    last_login TIMESTAMP
);

CREATE INDEX idx_users_last_login ON users(last_login);
EOF

# Tests referencing the field
cat > tests/UserTest.java << 'EOF'
package com.app.tests;

import com.app.models.User;
import java.time.LocalDateTime;

public class UserTest {
    public void testLastLoginTracking() {
        User user = new User();
        LocalDateTime now = LocalDateTime.now();
        user.setLastLogin(now);

        assertEquals(now, user.getLastLogin());
    }

    public void testRecentLoginCheck() {
        User user = new User();
        user.setLastLogin(LocalDateTime.now().minusHours(12));
        assertTrue(user.getLastLogin() != null);
    }
}
EOF

echo "Project with deprecated field created at /tmp/wicked-patch-cleanup"
```

## Steps

### 1. Index the codebase

Build the symbol graph to find all references:

```bash
/wicked-search:index /tmp/wicked-patch-cleanup
```

### 2. Plan the removal

Preview what will be cleaned up:

```bash
/wicked-patch:plan --entity User --remove-field lastLogin --project /tmp/wicked-patch-cleanup
```

### 3. Generate cleanup patches

Create patches to remove the field and all references:

```bash
/wicked-patch:remove --entity User --field lastLogin --project /tmp/wicked-patch-cleanup
```

### 4. Review generated patches

Check what cleanup actions were identified:

```bash
ls -la /tmp/wicked-patch-cleanup/.patches/
cat /tmp/wicked-patch-cleanup/.patches/remove-lastLogin-summary.json
```

### 5. Apply cleanup patches

Execute all cleanup operations:

```bash
/wicked-patch:apply --patches /tmp/wicked-patch-cleanup/.patches/ --project /tmp/wicked-patch-cleanup
```

### 6. Verify complete removal

Confirm no traces of the field remain:

```bash
# Should find NO occurrences of lastLogin
! grep -r "lastLogin\|last_login" /tmp/wicked-patch-cleanup/ \
  --include="*.java" --include="*.sql" \
  --exclude-dir=.patches

# Check migration was generated
cat /tmp/wicked-patch-cleanup/migrations/002_remove_last_login.sql

# Verify User.java no longer has the field
cat /tmp/wicked-patch-cleanup/models/User.java | grep -A 5 -B 5 "class User"
```

## Expected Outcome

After step 2 (plan removal), you should see:
```
Removal Plan: Delete field 'lastLogin' from User

Impact Analysis:
├─ Entity changes:
│  └─ models/User.java (4 deletions)
│     - Remove field: private LocalDateTime lastLogin;
│     - Remove getter: getLastLogin()
│     - Remove setter: setLastLogin(LocalDateTime lastLogin)
│     - Remove import: java.time.LocalDateTime (if no other usages)
│
├─ Service layer (8 references):
│  └─ services/AuthService.java
│     - Remove recordLogin() method (deprecated)
│     - Remove isRecentLogin() method (uses lastLogin)
│
├─ Repository layer (3 references):
│  └─ repositories/UserRepository.java
│     - Remove updateLastLogin() method
│     - Remove findRecentlyActive() SQL query
│
├─ Database schema:
│  └─ migrations/ (new migration file)
│     - Generate: 002_remove_last_login.sql
│     - ALTER TABLE users DROP COLUMN last_login;
│     - DROP INDEX idx_users_last_login;
│
└─ Test cleanup (4 references):
   └─ tests/UserTest.java
      - Remove testLastLoginTracking()
      - Remove testRecentLoginCheck()

Total impact: 4 files, 19 references
Risk level: MEDIUM (removes functionality)
Orphaned code prevented: 2 methods, 1 index, 2 tests
```

After step 3 (remove), you should see:
```
Generated cleanup patches:
- remove-lastLogin-entity.json (4 changes in User.java)
- remove-lastLogin-service.json (2 methods in AuthService.java)
- remove-lastLogin-repository.json (2 methods in UserRepository.java)
- remove-lastLogin-migration.sql (new migration file)
- remove-lastLogin-tests.json (2 test methods removed)

⚠️  WARNING: Deprecated functionality will be removed:
   - AuthService.recordLogin() - used in 3 places
   - AuthService.isRecentLogin() - used in 2 places

Replacement required:
   → Use LoginHistoryService for login tracking
   → Update callers before applying patches

Patches saved to: /tmp/wicked-patch-cleanup/.patches/
```

After step 5 (apply), files should show:

**models/User.java** - no lastLogin field:
```java
public class User {
    private Long id;
    private String email;
    private String passwordHash;

    // Only getters/setters for id, email, passwordHash remain
    // lastLogin field and methods REMOVED
}
```

**services/AuthService.java** - deprecated methods removed:
```java
package com.app.services;

import com.app.models.User;

public class AuthService {
    // recordLogin() and isRecentLogin() REMOVED
    // File may be empty or contain only other methods
}
```

**migrations/002_remove_last_login.sql** - new migration created:
```sql
-- Remove deprecated last_login field
-- Replaced by login_history table

DROP INDEX IF EXISTS idx_users_last_login;
ALTER TABLE users DROP COLUMN last_login;
```

**tests/UserTest.java** - tests for removed field deleted:
```java
package com.app.tests;

import com.app.models.User;

public class UserTest {
    // testLastLoginTracking() REMOVED
    // testRecentLoginCheck() REMOVED
}
```

## Success Criteria

- [ ] Plan identified all 19 references across 4 files
- [ ] Entity field declaration removed from User.java
- [ ] Getter and setter methods removed from User.java
- [ ] Deprecated service methods removed from AuthService.java
- [ ] Repository methods using the field removed
- [ ] SQL migration generated with DROP COLUMN statement
- [ ] Database index removal included in migration
- [ ] Tests for removed field deleted from UserTest.java
- [ ] No grep matches for "lastLogin" or "last_login" in codebase
- [ ] Warning issued about deprecated functionality removal

## Value Demonstrated

**Real-world problem**: When removing deprecated fields, developers often forget to clean up related code (getters/setters, service methods, queries, migrations, tests). This leaves orphaned code that confuses future developers and increases maintenance burden.

**wicked-patch solution**: Automatically identifies and removes ALL traces of the field across entity, service, repository, database, and test layers. Generates complete SQL migrations.

**Time saved**: 45-60 minutes per field removal (manual grep, cleanup, migration writing, testing) → 3 minutes (one command)

**Risk reduced**:
- Prevents orphaned code (methods that reference non-existent fields)
- Ensures database schema stays in sync with code
- Removes obsolete tests that would fail after field removal
- Prevents confusion from DEPRECATED comments with no removal plan

**Real-world use cases**:
- Tech debt cleanup sprints (removing old feature flags)
- GDPR compliance (removing PII fields from legacy tables)
- API versioning (deprecating old fields in favor of new structures)
- Database normalization (moving fields to separate tables)
