# Component Documentation Template - Maintenance

Change log, references, contact info, example auth component, and template usage tips.

## Change Log

### v2.0.0 (2025-01-20)

**Breaking Changes**:
- Changed resource ID from integer to UUID
- Removed `description` field

**Added**:
- Status field with workflow
- Event publishing

**Fixed**:
- Race condition in concurrent updates

### v1.1.0 (2024-12-15)

**Added**:
- Search functionality
- Bulk operations

## References

- [API Documentation](docs/api.md)
- [Database Schema](docs/schema.sql)
- [Architecture Decision Records](docs/adr/)
- [Source Code](https://github.com/example/resource-service)

## Contact

- **Team**: Platform Team
- **Slack**: #platform-team
- **On-call**: platform-oncall@example.com
- **JIRA**: PLAT project
```

## Example: Auth Component

```markdown
# Authentication Component

## Overview

Handles user authentication, authorization, and session management for all services in the platform.

**Type**: Service
**Owner**: Security Team
**Status**: Active

## Responsibilities

- User authentication (login/logout)
- JWT token generation and validation
- Session management
- Password reset flows
- OAuth2 integration (Google, GitHub)

**Not responsible for**:
- User profile management (handled by user-service)
- Authorization policies (policies defined in each service)
- Password storage (delegated to identity provider)

## Public Interface

### API Endpoints

```
POST /auth/login              - Authenticate user
POST /auth/logout             - End user session
POST /auth/refresh            - Refresh access token
POST /auth/forgot-password    - Initiate password reset
GET  /auth/verify             - Verify token validity
```

### Events Published

```
auth.user.logged_in     - User successfully logged in
auth.user.logged_out    - User logged out
auth.password.reset     - Password was reset
auth.token.refreshed    - Access token refreshed
```

## Dependencies

### Required

- **PostgreSQL 14+**: Session storage
- **Redis 7+**: Token blacklist and rate limiting
- **Email Service**: For password reset emails

### Internal Dependencies

- **user-service**: Fetch user credentials

## Data Model

```typescript
interface Session {
  id: string;
  userId: string;
  token: string;
  refreshToken: string;
  expiresAt: Date;
  createdAt: Date;
  userAgent: string;
  ipAddress: string;
}

interface TokenPayload {
  sub: string;        // User ID
  email: string;
  role: string;
  exp: number;        // Expiration
  iat: number;        // Issued at
}
```

## Configuration

```yaml
jwt:
  secret: ${JWT_SECRET}
  accessTokenTTL: 900      # 15 minutes
  refreshTokenTTL: 604800  # 7 days

rateLimit:
  login: 5                  # 5 attempts per minute
  passwordReset: 3          # 3 attempts per hour

oauth:
  google:
    clientId: ${GOOGLE_CLIENT_ID}
    clientSecret: ${GOOGLE_CLIENT_SECRET}
```

## Security

### Authentication Flow

1. Client sends credentials
2. Service validates against user-service
3. Generate JWT access token (15min TTL)
4. Generate refresh token (7day TTL)
5. Store session in database
6. Return tokens to client

### Token Refresh Flow

1. Client sends refresh token
2. Validate refresh token
3. Check if token is blacklisted
4. Generate new access token
5. Return new access token

### Security Measures

- Bcrypt for password hashing (cost factor: 10)
- Rate limiting on login endpoint
- Token blacklist for logout
- HTTPS only
- CORS restrictions

## Performance

**Targets**:
- Login: P95 < 300ms
- Token validation: P95 < 50ms

**Optimization**:
- Redis caching for token validation
- Database connection pooling
- Async email sending

## Monitoring

**Key Metrics**:
- Login success/failure rate
- Token validation rate
- Session duration
- Password reset requests

**Alerts**:
- Login failure rate > 20%
- Token validation errors > 5%
```

## Tips for Using Template

### Do Include

- Clear responsibilities
- All interfaces (APIs, events, etc.)
- Dependencies
- Configuration
- Security considerations
- Monitoring approach

### Don't Include

- Implementation details (that's in code)
- Every single function
- Speculative future features
- Information better suited for ADRs

### Keep Updated

- Review quarterly
- Update on major changes
- Link to current source code
- Mark deprecated features
