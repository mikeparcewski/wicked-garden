---
name: implementation-planning
title: Implementation Planning with Risk Assessment
description: Create a detailed implementation plan for a feature with risk analysis
type: review
difficulty: advanced
estimated_minutes: 15
---

# Implementation Planning with Risk Assessment

This scenario demonstrates using wicked-engineering to analyze a change request, explore the codebase, and create a detailed implementation plan with risk assessment.

## Setup

Create a project with existing code that needs a new feature:

```bash
# Create test project
mkdir -p ~/test-wicked-engineering/plan-test
cd ~/test-wicked-engineering/plan-test

# Create existing notification system
mkdir -p src/notifications src/users src/config tests
cat > src/notifications/service.ts << 'EOF'
import { EmailProvider } from './providers/email';
import { User } from '../users/types';

export interface Notification {
  id: string;
  userId: string;
  type: 'email';  // Currently only email
  subject: string;
  body: string;
  sentAt?: Date;
  status: 'pending' | 'sent' | 'failed';
}

export class NotificationService {
  private emailProvider: EmailProvider;

  constructor(emailProvider: EmailProvider) {
    this.emailProvider = emailProvider;
  }

  async send(userId: string, subject: string, body: string): Promise<Notification> {
    const notification: Notification = {
      id: crypto.randomUUID(),
      userId,
      type: 'email',
      subject,
      body,
      status: 'pending'
    };

    try {
      await this.emailProvider.send(userId, subject, body);
      notification.status = 'sent';
      notification.sentAt = new Date();
    } catch (error) {
      notification.status = 'failed';
      console.error('Failed to send notification:', error);
    }

    await this.saveNotification(notification);
    return notification;
  }

  async getHistory(userId: string): Promise<Notification[]> {
    // Returns notification history for user
    return db.notifications.findMany({ where: { userId } });
  }

  private async saveNotification(notification: Notification): Promise<void> {
    await db.notifications.create({ data: notification });
  }
}
EOF

cat > src/notifications/providers/email.ts << 'EOF'
export interface EmailProvider {
  send(to: string, subject: string, body: string): Promise<void>;
}

export class SMTPEmailProvider implements EmailProvider {
  constructor(private config: { host: string; port: number; user: string; pass: string }) {}

  async send(to: string, subject: string, body: string): Promise<void> {
    // SMTP implementation
    const transporter = createTransport(this.config);
    await transporter.sendMail({ to, subject, html: body });
  }
}
EOF

cat > src/users/types.ts << 'EOF'
export interface User {
  id: string;
  email: string;
  phone?: string;
  preferences: {
    emailNotifications: boolean;
    smsNotifications: boolean;  // Not implemented yet
  };
}
EOF

cat > src/config/index.ts << 'EOF'
export const config = {
  smtp: {
    host: process.env.SMTP_HOST,
    port: parseInt(process.env.SMTP_PORT || '587'),
    user: process.env.SMTP_USER,
    pass: process.env.SMTP_PASS
  }
};
EOF

# Create existing tests
cat > tests/notification.test.ts << 'EOF'
import { NotificationService } from '../src/notifications/service';

describe('NotificationService', () => {
  it('sends email notification', async () => {
    const mockEmail = { send: jest.fn() };
    const service = new NotificationService(mockEmail);

    const result = await service.send('user1', 'Test', 'Body');

    expect(mockEmail.send).toHaveBeenCalled();
    expect(result.status).toBe('sent');
  });

  it('handles send failure', async () => {
    const mockEmail = { send: jest.fn().mockRejectedValue(new Error('SMTP error')) };
    const service = new NotificationService(mockEmail);

    const result = await service.send('user1', 'Test', 'Body');

    expect(result.status).toBe('failed');
  });
});
EOF
```

## Steps

### 1. Request Implementation Plan

```bash
/wicked-engineering:plan Add SMS notifications using Twilio, with user preference support and fallback to email
```

**Expected**: The plan command should:
1. Parse the request to understand scope
2. Explore existing notification code
3. Identify patterns and dependencies
4. Spawn senior engineer for approach analysis
5. Spawn risk assessor for risk evaluation
6. Produce detailed implementation plan

### 2. Review Generated Plan

The plan should include:
- Files to modify and create
- Specific changes with line numbers
- Risk assessment table
- Test plan
- Rollout considerations

### 3. Request Clarification if Needed

If the request is ambiguous, the planner should ask:
- Should SMS be primary or just backup?
- What happens if both SMS and email fail?
- Is there a priority order for notification types?

## Expected Outcome

```markdown
## Implementation Plan: SMS Notifications with Twilio

### Summary
Add SMS notification capability via Twilio, with user preference support and automatic fallback to email if SMS fails or user prefers email.

### Approach Analysis

**Chosen approach**: Strategy pattern with multiple providers
- Add `SmsProvider` interface matching existing `EmailProvider` pattern
- Create `TwilioSmsProvider` implementation
- Extend `NotificationService` to support multiple channels
- Use user preferences to determine channel, with configurable fallback

**Alternatives considered**:
1. Separate SmsNotificationService - Rejected: Code duplication, harder to orchestrate fallback
2. Generic NotificationProvider - Rejected: Over-engineering for two channels
3. Queue-based async - Deferred: Could add later, not needed for initial implementation

### Changes Required

#### 1. src/notifications/providers/sms.ts (NEW)
**Purpose**: SMS provider interface and Twilio implementation

```typescript
export interface SmsProvider {
  send(phoneNumber: string, message: string): Promise<void>;
}

export class TwilioSmsProvider implements SmsProvider {
  constructor(private config: { accountSid: string; authToken: string; fromNumber: string }) {}

  async send(phoneNumber: string, message: string): Promise<void> {
    const client = require('twilio')(this.config.accountSid, this.config.authToken);
    await client.messages.create({
      body: message,
      from: this.config.fromNumber,
      to: phoneNumber
    });
  }
}
```

#### 2. src/notifications/types.ts (NEW)
**Purpose**: Shared notification types

```typescript
export type NotificationChannel = 'email' | 'sms';

export interface Notification {
  id: string;
  userId: string;
  channel: NotificationChannel;  // Changed from 'type'
  subject?: string;  // Optional for SMS
  body: string;
  sentAt?: Date;
  status: 'pending' | 'sent' | 'failed';
  failedChannels?: NotificationChannel[];  // Track fallback attempts
}
```

#### 3. src/notifications/service.ts
**Purpose**: Support multiple channels with fallback

**Changes**:
- Line 1-3: Update imports
- Line 8-12: Add SmsProvider dependency
- Line 15: Add channel selection logic
- Line 25-45: Implement fallback mechanism

```typescript
// Constructor changes
constructor(
  private emailProvider: EmailProvider,
  private smsProvider?: SmsProvider,  // Optional - graceful degradation
  private userService: UserService
) {}

// New method
async sendWithFallback(
  userId: string,
  subject: string,
  body: string,
  preferredChannel?: NotificationChannel
): Promise<Notification> {
  const user = await this.userService.findById(userId);
  const channel = this.determineChannel(user, preferredChannel);

  const notification = await this.send(userId, channel, subject, body);

  // Fallback on failure
  if (notification.status === 'failed' && channel === 'sms') {
    notification.failedChannels = ['sms'];
    return this.send(userId, 'email', subject, body, notification);
  }

  return notification;
}
```

#### 4. src/config/index.ts
**Purpose**: Add Twilio configuration

**Changes**:
- Line 8-13: Add Twilio config

```typescript
twilio: {
  accountSid: process.env.TWILIO_ACCOUNT_SID,
  authToken: process.env.TWILIO_AUTH_TOKEN,
  fromNumber: process.env.TWILIO_FROM_NUMBER
}
```

#### 5. tests/notification.test.ts
**Purpose**: Test SMS and fallback behavior

**Changes**:
- Add new test suite for SMS
- Add fallback behavior tests

### Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Twilio API failure | Medium | High | Fallback to email, retry logic |
| Invalid phone numbers | Medium | Low | Validate format before sending |
| SMS cost overrun | Low | Medium | Rate limiting, alerting on usage |
| Breaking existing email flow | Low | High | Feature flag, extensive testing |
| Missing user phone numbers | High | Low | Graceful fallback to email |

### Test Plan

#### Unit Tests
- [ ] `TwilioSmsProvider.send()` - calls Twilio API correctly
- [ ] `NotificationService.determineChannel()` - respects user preferences
- [ ] `NotificationService.sendWithFallback()` - falls back on SMS failure
- [ ] `NotificationService.send()` - handles missing phone number

#### Integration Tests
- [ ] Full notification flow with mocked providers
- [ ] Fallback chain: SMS fail -> Email succeed
- [ ] User preference: SMS preferred, phone missing -> Email

#### Manual Testing
- [ ] Send real SMS via Twilio sandbox
- [ ] Verify fallback with invalid phone number
- [ ] Check notification history shows channel used

### Rollout Considerations

1. **Environment Variables**: Add to deployment config:
   ```
   TWILIO_ACCOUNT_SID=xxx
   TWILIO_AUTH_TOKEN=xxx
   TWILIO_FROM_NUMBER=+1234567890
   SMS_ENABLED=false  # Feature flag
   ```

2. **Feature Flag**: Start with `SMS_ENABLED=false`
   - Deploy code
   - Enable for internal users
   - Gradual rollout to 5%, 25%, 100%

3. **Monitoring**:
   - Alert: SMS failure rate > 5%
   - Dashboard: SMS vs Email usage, fallback rate
   - Cost tracking: Daily Twilio spend

4. **Rollback**: If SMS causes issues:
   - Set `SMS_ENABLED=false`
   - All notifications fall back to email
   - No code rollback needed

### Dependencies

- `twilio` npm package (add to package.json)
- Twilio account with verified phone number
- User phone number field in database (already exists)

### Estimated Effort

| Task | Effort |
|------|--------|
| SMS provider implementation | 2 hours |
| Service refactoring | 3 hours |
| Tests | 2 hours |
| Config and documentation | 1 hour |
| **Total** | **8 hours** |

---

Ready to proceed with implementation, or would you like to adjust the approach?
```

## Success Criteria

- [ ] Planner explores existing codebase patterns
- [ ] Existing EmailProvider pattern is recognized and matched
- [ ] New files and modified files clearly listed
- [ ] Specific line numbers for modifications
- [ ] Risk assessment includes likelihood and impact
- [ ] Mitigation strategies are actionable
- [ ] Test plan covers unit, integration, and manual
- [ ] Rollout includes feature flag strategy
- [ ] Rollback plan is simple and clear
- [ ] Effort estimate is provided
- [ ] Dependencies are identified

## Value Demonstrated

**Problem solved**: Developers often start coding without understanding the full scope, leading to refactoring mid-implementation and missed edge cases.

**Real-world value**:
- **Reduced rework**: Understand full scope before writing code
- **Risk awareness**: Identify potential issues upfront
- **Pattern consistency**: Match existing codebase patterns
- **Safe deployment**: Feature flags enable gradual rollout
- **Clear communication**: Plan can be shared with team for review

This replaces:
1. "Let me just start coding"
2. Discover complexity mid-implementation
3. Refactor approach
4. Miss edge cases
5. Deploy all at once
6. Hotfix issues

With implementation planning:
1. Understand scope and patterns
2. Identify risks early
3. Plan for testing and rollout
4. Execute with confidence
5. Deploy safely with feature flags
