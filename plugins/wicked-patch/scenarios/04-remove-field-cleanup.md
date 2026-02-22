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
/wicked-patch:plan "models/User.java::User" --change remove_field
```

**Expected**: A PROPAGATION PLAN showing User as source with impacts across multiple files. Risk level should be HIGH (remove_field is always HIGH risk, especially with no_internal_refs flag if the graph doesn't link lastLogin references).

### 3. Generate cleanup patches

Create patches to remove the field and all references:

```bash
/wicked-patch:remove "models/User.java::User" --field lastLogin -o /tmp/wicked-patch-cleanup/.patches/patches.json --verbose
```

**Expected**: A GENERATED PATCHES block showing removal operations in User.java (field, getter, setter) and potentially in dependent files (AuthService.java, UserRepository.java, UserTest.java) if the graph linked them.

### 4. Review generated patches

Check what cleanup actions were identified:

```bash
ls -la /tmp/wicked-patch-cleanup/.patches/
cat /tmp/wicked-patch-cleanup/.patches/manifest.json
```

**Expected**: manifest.json with change_type "remove_field", target symbol, files_affected count, and patch_count.

### 5. Apply cleanup patches

Execute all cleanup operations:

```bash
/wicked-patch:apply /tmp/wicked-patch-cleanup/.patches/patches.json --skip-git --force
```

### 6. Verify removal from entity

Confirm the field was removed from the User entity:

```bash
# Check User.java no longer has lastLogin field
! grep "lastLogin" /tmp/wicked-patch-cleanup/models/User.java

# Verify User.java structure is still valid (has remaining fields)
grep "private" /tmp/wicked-patch-cleanup/models/User.java
```

## Expected Outcome

After step 2 (plan removal), you should see:
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
  Risk level: HIGH
  ...
------------------------------------------------------------
Total: N symbols in N files
============================================================
```

After step 3 (remove), you should see:
```
============================================================
GENERATED PATCHES
============================================================

Change: remove_field
Target: ...User.java::User
...

PATCHES:

  User.java
    [...] Remove field 'lastLogin'
    [...] Remove getter for 'lastLogin'
    [...] Remove setter for 'lastLogin'

============================================================
```

After step 5 (apply), User.java should:
- NOT contain `lastLogin` field, getter, or setter
- Still contain id, email, passwordHash fields and their getters/setters
- Be syntactically valid (no trailing commas, broken formatting)

## Success Criteria

- [ ] Plan showed HIGH risk level for remove_field operation
- [ ] Entity field declaration removed from User.java
- [ ] Getter and setter methods removed from User.java
- [ ] Remaining fields (id, email, passwordHash) are intact
- [ ] User.java is syntactically valid after removal (no broken formatting)
- [ ] Patches saved to output file with manifest.json
- [ ] Patches applied without errors

## Value Demonstrated

**Real-world problem**: When removing deprecated fields, developers often forget to clean up related code (getters/setters, service methods, queries, migrations, tests). This leaves orphaned code that confuses future developers and increases maintenance burden.

**wicked-patch solution**: Automatically identifies and removes ALL traces of the field from the entity. The propagation engine can also discover dependent code (services, repositories, tests) through the symbol graph.

**Time saved**: 45-60 minutes per field removal (manual grep, cleanup, migration writing, testing) -> 3 minutes (one command)

**Risk reduced**:
- Prevents orphaned code (methods that reference non-existent fields)
- Ensures entity stays syntactically valid after removal
- Removes obsolete tests that would fail after field removal
