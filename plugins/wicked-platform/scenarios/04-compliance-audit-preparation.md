---
name: compliance-audit-preparation
title: SOC2 Compliance Audit Evidence Collection
description: Prepare for SOC2 audit by systematically collecting control evidence, verifying implementations, and generating audit-ready documentation
type: compliance
difficulty: advanced
estimated_minutes: 15
---

# SOC2 Compliance Audit Evidence Collection

This scenario demonstrates wicked-platform's compliance capabilities, including control verification, evidence collection, and audit-ready documentation generation for SOC2 Trust Service Criteria.

## Setup

Create an application with security controls implemented:

```bash
# Create test project with compliance controls
mkdir -p ~/test-wicked-platform/compliant-app/src/middleware
mkdir -p ~/test-wicked-platform/compliant-app/src/services
mkdir -p ~/test-wicked-platform/compliant-app/logs
mkdir -p ~/test-wicked-platform/compliant-app/config
cd ~/test-wicked-platform/compliant-app

# Create authentication middleware (CC6.1)
cat > src/middleware/auth.ts << 'EOF'
import jwt from 'jsonwebtoken';
import { User } from '../models/User';
import { AuditLog } from '../services/audit';

export async function authenticate(req, res, next) {
  const token = req.headers.authorization?.split(' ')[1];

  if (!token) {
    AuditLog.record('auth.denied', { reason: 'missing_token', ip: req.ip });
    return res.status(401).json({ error: 'Authentication required' });
  }

  try {
    const payload = jwt.verify(token, process.env.JWT_SECRET);
    const user = await User.findById(payload.sub);

    if (!user || !user.active) {
      AuditLog.record('auth.denied', { reason: 'user_inactive', userId: payload.sub });
      return res.status(401).json({ error: 'Account inactive' });
    }

    AuditLog.record('auth.success', { userId: user.id, ip: req.ip });
    req.user = user;
    next();
  } catch (err) {
    AuditLog.record('auth.failed', { reason: err.message, ip: req.ip });
    return res.status(401).json({ error: 'Invalid token' });
  }
}
EOF

# Create authorization middleware (CC6.1)
cat > src/middleware/authorize.ts << 'EOF'
import { AuditLog } from '../services/audit';

export type Role = 'admin' | 'user' | 'readonly';

export function authorize(...allowedRoles: Role[]) {
  return (req, res, next) => {
    const userRole = req.user?.role;

    if (!userRole || !allowedRoles.includes(userRole)) {
      AuditLog.record('authz.denied', {
        userId: req.user?.id,
        requiredRoles: allowedRoles,
        userRole
      });
      return res.status(403).json({ error: 'Insufficient permissions' });
    }

    AuditLog.record('authz.granted', {
      userId: req.user.id,
      role: userRole,
      resource: req.path
    });
    next();
  };
}
EOF

# Create audit logging service (CC7.2)
cat > src/services/audit.ts << 'EOF'
import crypto from 'crypto';

interface AuditEntry {
  timestamp: string;
  eventType: string;
  data: Record<string, unknown>;
  hash: string;
}

class AuditLogger {
  private lastHash: string = '';

  record(eventType: string, data: Record<string, unknown>): void {
    const entry: AuditEntry = {
      timestamp: new Date().toISOString(),
      eventType,
      data,
      hash: this.calculateHash(eventType, data)
    };

    // Tamper-evident chain
    this.lastHash = entry.hash;

    // Write to immutable log storage
    console.log(JSON.stringify(entry));
  }

  private calculateHash(eventType: string, data: Record<string, unknown>): string {
    const content = `${this.lastHash}:${eventType}:${JSON.stringify(data)}`;
    return crypto.createHash('sha256').update(content).digest('hex');
  }
}

export const AuditLog = new AuditLogger();
EOF

# Create encryption service (CC6.7)
cat > src/services/encryption.ts << 'EOF'
import crypto from 'crypto';

const ALGORITHM = 'aes-256-gcm';
const KEY = Buffer.from(process.env.ENCRYPTION_KEY!, 'hex');

export function encrypt(plaintext: string): { ciphertext: string; iv: string; tag: string } {
  const iv = crypto.randomBytes(16);
  const cipher = crypto.createCipheriv(ALGORITHM, KEY, iv);

  let ciphertext = cipher.update(plaintext, 'utf8', 'hex');
  ciphertext += cipher.final('hex');

  return {
    ciphertext,
    iv: iv.toString('hex'),
    tag: cipher.getAuthTag().toString('hex')
  };
}

export function decrypt(ciphertext: string, iv: string, tag: string): string {
  const decipher = crypto.createDecipheriv(ALGORITHM, KEY, Buffer.from(iv, 'hex'));
  decipher.setAuthTag(Buffer.from(tag, 'hex'));

  let plaintext = decipher.update(ciphertext, 'hex', 'utf8');
  plaintext += decipher.final('utf8');

  return plaintext;
}
EOF

# Create security configuration (CC6.6)
cat > config/security.ts << 'EOF'
export const securityConfig = {
  // Password requirements
  password: {
    minLength: 12,
    requireUppercase: true,
    requireLowercase: true,
    requireNumbers: true,
    requireSpecialChars: true,
    maxAge: 90 * 24 * 60 * 60 * 1000, // 90 days
    historyCount: 12 // Prevent reuse of last 12 passwords
  },

  // Session configuration
  session: {
    maxAge: 8 * 60 * 60 * 1000, // 8 hours
    idleTimeout: 30 * 60 * 1000, // 30 minutes
    maxConcurrent: 3
  },

  // Rate limiting
  rateLimit: {
    windowMs: 15 * 60 * 1000, // 15 minutes
    maxRequests: 100,
    loginAttempts: 5
  },

  // Encryption
  encryption: {
    algorithm: 'aes-256-gcm',
    keyRotationDays: 90
  }
};
EOF

# Create sample audit logs
cat > logs/audit.log << 'EOF'
{"timestamp":"2024-01-15T14:00:00Z","eventType":"auth.success","data":{"userId":"usr_123","ip":"192.168.1.1"},"hash":"a1b2c3..."}
{"timestamp":"2024-01-15T14:00:05Z","eventType":"authz.granted","data":{"userId":"usr_123","role":"admin","resource":"/api/users"},"hash":"d4e5f6..."}
{"timestamp":"2024-01-15T14:01:00Z","eventType":"data.access","data":{"userId":"usr_123","resource":"customer_records","action":"read"},"hash":"g7h8i9..."}
{"timestamp":"2024-01-15T14:05:00Z","eventType":"auth.denied","data":{"reason":"invalid_password","ip":"10.0.0.1"},"hash":"j0k1l2..."}
{"timestamp":"2024-01-15T14:05:01Z","eventType":"auth.denied","data":{"reason":"invalid_password","ip":"10.0.0.1"},"hash":"m3n4o5..."}
{"timestamp":"2024-01-15T14:05:02Z","eventType":"security.alert","data":{"type":"brute_force_attempt","ip":"10.0.0.1","attempts":5},"hash":"p6q7r8..."}
EOF

git init
git add -A
git commit -m "Initial commit with security controls"
```

## Steps

### 1. Run Comprehensive Compliance Check

```bash
/wicked-platform:compliance soc2
```

**Expected**:
- Analyzes codebase against SOC2 Trust Service Criteria
- Identifies implemented controls
- Flags gaps or partial implementations
- Generates compliance status report

### 2. Audit Specific Control

```bash
/wicked-platform:audit soc2 CC6.1
```

**Expected** for CC6.1 (Logical Access Controls):

```markdown
## Audit Evidence: SOC2 CC6.1

**Control**: CC6.1 - Logical Access Security
**Status**: PASS
**Evidence Collected**: 4 artifacts

### Control Requirements

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Authentication implemented | PASS | src/middleware/auth.ts |
| Authorization enforced | PASS | src/middleware/authorize.ts |
| Access attempts logged | PASS | src/services/audit.ts |
| Failed attempts tracked | PASS | logs/audit.log |

### Evidence: Authentication

**Location**: `src/middleware/auth.ts:5-30`
**Implementation**: JWT-based token authentication

```typescript
const payload = jwt.verify(token, process.env.JWT_SECRET);
const user = await User.findById(payload.sub);
```

**Verification**:
- [x] Cryptographic token validation
- [x] User status verification
- [x] Unauthorized requests rejected
```

### 3. Collect Evidence for Multiple Controls

```bash
/wicked-platform:audit soc2 --controls CC6.1,CC6.7,CC7.2
```

**Expected**:
Evidence package for:
- **CC6.1**: Logical access controls (auth/authz)
- **CC6.7**: Encryption at rest and in transit
- **CC7.2**: Monitoring and incident detection

### 4. Generate Gap Analysis

The compliance check should identify gaps:

```markdown
### Compliance Gaps

**CC6.6 - System Operations** - PARTIAL

Gap: Password policy documented in config but not enforced in code.

```typescript
// Config exists:
password: { minLength: 12, ... }

// But no validation middleware found
```

**Remediation**:
Implement password validation middleware that enforces policy.

---

**CC7.1 - Change Management** - NEEDS EVIDENCE

Gap: No CI/CD pipeline configuration found.

**Remediation**:
- Add `.github/workflows/` or deployment configuration
- Document change approval process
```

### 5. Export Audit Package

```bash
/wicked-platform:audit soc2 --export
```

**Expected**:
Generates audit-ready documentation package:

```
audit-evidence/
├── CC6.1-logical-access.md
├── CC6.6-system-operations.md
├── CC6.7-encryption.md
├── CC7.1-change-management.md
├── CC7.2-monitoring.md
├── artifacts/
│   ├── auth-middleware.ts
│   ├── encryption-service.ts
│   └── audit-logs-sample.json
└── summary.md
```

## Expected Outcome

Complete SOC2 compliance assessment:

```markdown
## SOC2 Compliance Assessment

**Assessment Date**: 2024-01-15
**Scope**: Application Security Controls
**Overall Status**: NEEDS ATTENTION (85% compliant)

### Trust Service Criteria Summary

| Category | Controls | Passed | Gaps |
|----------|----------|--------|------|
| CC6 - Logical & Physical Access | 7 | 6 | 1 |
| CC7 - System Operations | 4 | 3 | 1 |
| CC8 - Change Management | 3 | 2 | 1 |

### Controls Verified

#### CC6.1 - Logical Access Security
**Status**: PASS
- Authentication: JWT with cryptographic validation
- Authorization: Role-based access control
- Audit: All access attempts logged

#### CC6.7 - Encryption
**Status**: PASS
- Algorithm: AES-256-GCM
- Key management: Environment-based
- Implementation: src/services/encryption.ts

#### CC7.2 - Security Monitoring
**Status**: PASS
- Audit logging: Tamper-evident chain
- Security events: Tracked and alertable
- Log retention: Configured

### Gaps Requiring Remediation

1. **CC6.6 - Password Policy Enforcement**
   - Policy defined but not enforced
   - Priority: HIGH
   - Remediation: Add validation middleware

2. **CC7.1 - Change Management Evidence**
   - No CI/CD configuration found
   - Priority: MEDIUM
   - Remediation: Document deployment process

3. **CC8.1 - Vulnerability Management**
   - No dependency scanning configured
   - Priority: MEDIUM
   - Remediation: Add npm audit to CI

### Auditor Notes

The application demonstrates strong authentication and authorization controls with comprehensive audit logging. Main gaps are in operational areas (change management, vulnerability scanning) rather than technical security controls.

Recommend addressing HIGH priority gaps before audit.
```

## Success Criteria

- [ ] All relevant code files identified as evidence
- [ ] Controls correctly mapped to SOC2 criteria
- [ ] Authentication implementation verified
- [ ] Authorization implementation verified
- [ ] Audit logging implementation verified
- [ ] Encryption implementation verified
- [ ] Gaps accurately identified
- [ ] Remediation guidance provided
- [ ] Evidence exportable for auditors

## Value Demonstrated

**Problem solved**: SOC2 audits require weeks of evidence collection, with engineers scrambling to document controls they built months ago. Control implementations are scattered across the codebase with no mapping to compliance requirements.

**Why this matters**:

1. **Automated evidence collection**: Instead of manually gathering screenshots and code snippets, the auditor agent systematically collects evidence mapped to specific controls.

2. **Continuous compliance**: Running `/compliance soc2` regularly catches drift before audit season. New code changes are validated against compliance requirements.

3. **Gap identification**: Proactively identifies missing controls before auditors find them. Better to fix a gap in January than explain it to auditors in October.

4. **Reduced audit cost**: External audit fees often correlate with audit duration. Well-organized evidence packages reduce auditor hours.

5. **Engineering-friendly**: Developers see exactly which code implements which control, making compliance tangible rather than abstract policy documents.

This replaces the annual compliance scramble where:
- Engineers search through old Slack messages for control decisions
- Compliance team asks for evidence that no one can find
- Audit findings reveal gaps that could have been fixed months earlier
- Documentation is created retroactively and may not match reality

The `/audit` command makes compliance a continuous, automated process rather than a crisis.
