# Authentication Module

OAuth2 social login (Google and GitHub) and email/password authentication for wicked-workbench.

## Features

- Email/password authentication with bcrypt
- OAuth2 social login (Google, GitHub)
- JWT access tokens (15 min expiry)
- Refresh tokens (7 day expiry, rotation)
- CSRF protection via state parameter
- Profile merging (link multiple OAuth accounts to one user)
- Session management

## Quick Start

### 1. Install Dependencies

```bash
cd plugins/wicked-workbench/server
pip install -e .
# or
uv pip install -e .
```

### 2. Configure Environment

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

**Required settings:**
- `JWT_SECRET_KEY` - Long random string for JWT signing
- `SESSION_SECRET_KEY` - Secret for OAuth state management

**Optional OAuth providers:**
- Google: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
- GitHub: `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`

### 3. Initialize Database

```bash
python scripts/init_auth_db.py
```

This creates the following tables:
- `users` - User accounts
- `oauth_accounts` - OAuth provider linkings
- `sessions` - Refresh token sessions

### 4. Start Server

```bash
uvicorn wicked_workbench_server.app:app --reload
```

## API Endpoints

### Email/Password Authentication

#### POST /auth/register
Register a new user.

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "secure123", "display_name": "John Doe"}'
```

Response:
```json
{
  "access_token": "eyJ...",
  "refresh_token": "xyz...",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "email_verified": false,
    "display_name": "John Doe"
  }
}
```

#### POST /auth/login
Login with email and password.

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "secure123"}'
```

#### POST /auth/refresh
Refresh access token.

```bash
curl -X POST http://localhost:8000/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "xyz..."}'
```

#### POST /auth/logout
Logout (revokes all sessions).

```bash
curl -X POST http://localhost:8000/auth/logout \
  -H "Authorization: Bearer eyJ..."
```

### OAuth2 Social Login

#### GET /auth/google
Start Google OAuth flow.

```bash
# Visit in browser
http://localhost:8000/auth/google
```

#### GET /auth/google/callback
Google OAuth callback (automatic redirect).

#### GET /auth/github
Start GitHub OAuth flow.

```bash
# Visit in browser
http://localhost:8000/auth/github
```

#### GET /auth/github/callback
GitHub OAuth callback (automatic redirect).

### User Profile

#### GET /auth/me
Get current user profile.

```bash
curl http://localhost:8000/auth/me \
  -H "Authorization: Bearer eyJ..."
```

### OAuth Account Management

#### GET /auth/accounts
List linked OAuth accounts.

```bash
curl http://localhost:8000/auth/accounts \
  -H "Authorization: Bearer eyJ..."
```

#### DELETE /auth/accounts/{provider}
Unlink OAuth account (google or github).

```bash
curl -X DELETE http://localhost:8000/auth/accounts/google \
  -H "Authorization: Bearer eyJ..."
```

## Using Protected Endpoints

To protect an endpoint, use the `get_current_user` dependency:

```python
from fastapi import Depends
from wicked_workbench_server.auth import get_current_user, User

@app.get("/protected")
async def protected_route(current_user: User = Depends(get_current_user)):
    return {"message": f"Hello {current_user.email}"}
```

For optional authentication:

```python
from wicked_workbench_server.auth import get_current_user_optional

@app.get("/optional")
async def optional_route(current_user: User | None = Depends(get_current_user_optional)):
    if current_user:
        return {"message": f"Hello {current_user.email}"}
    return {"message": "Hello anonymous"}
```

## OAuth Provider Setup

### Google OAuth

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable Google+ API
4. Create OAuth 2.0 credentials:
   - Application type: Web application
   - Authorized redirect URIs: `http://localhost:8000/auth/google/callback`
5. Copy Client ID and Client Secret to `.env`

### GitHub OAuth

1. Go to [GitHub Developer Settings](https://github.com/settings/developers)
2. Create a new OAuth App:
   - Homepage URL: `http://localhost:8000`
   - Authorization callback URL: `http://localhost:8000/auth/github/callback`
3. Copy Client ID and Client Secret to `.env`

## Security Best Practices

1. **Never commit secrets** - Use `.env` for local development, environment variables in production
2. **Use HTTPS in production** - Set redirect URIs to `https://` in production
3. **Rotate secrets regularly** - Especially `JWT_SECRET_KEY` and `SESSION_SECRET_KEY`
4. **Use strong passwords** - Minimum 8 characters recommended
5. **Implement rate limiting** - Prevent brute force attacks (not included in this implementation)
6. **Enable email verification** - For production use (implementation provided but not enforced)

## Database Schema

### users
```sql
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    email_verified BOOLEAN DEFAULT FALSE,
    password_hash TEXT,
    display_name TEXT,
    avatar_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### oauth_accounts
```sql
CREATE TABLE oauth_accounts (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    provider TEXT NOT NULL,
    provider_user_id TEXT NOT NULL,
    provider_email TEXT,
    access_token TEXT,
    refresh_token TEXT,
    token_expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(provider, provider_user_id)
);
```

### sessions
```sql
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    refresh_token_hash TEXT NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP
);
```

## Testing

Run the test suite:

```bash
python tests/test_auth.py
```

Or with pytest:

```bash
pytest tests/test_auth.py -v
```

## Profile Merging

The OAuth system automatically merges profiles:

1. **First login with Google** → Creates new user with Google account linked
2. **Later login with GitHub (same email)** → Links GitHub to existing user
3. **Later login with email/password** → Can set password on OAuth-created account

This allows users to:
- Link multiple OAuth providers to one account
- Add email/password to OAuth-only accounts
- Access their account via any linked method

## Token Flow

```
1. Login/Register
   ↓
2. Server returns: access_token (15 min) + refresh_token (7 days)
   ↓
3. Client stores tokens
   ↓
4. For API calls: send access_token in Authorization header
   ↓
5. When access_token expires:
   - Send refresh_token to /auth/refresh
   - Get new access_token + new refresh_token
   - Old refresh_token is invalidated (rotation)
```

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | No | `sqlite:///./wicked_workbench.db` | Database connection string |
| `JWT_SECRET_KEY` | Yes | - | Secret for JWT signing |
| `SESSION_SECRET_KEY` | Yes | - | Secret for OAuth state |
| `GOOGLE_CLIENT_ID` | For Google | - | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | For Google | - | Google OAuth client secret |
| `GOOGLE_REDIRECT_URI` | No | `http://localhost:8000/auth/google/callback` | Google OAuth redirect |
| `GITHUB_CLIENT_ID` | For GitHub | - | GitHub OAuth client ID |
| `GITHUB_CLIENT_SECRET` | For GitHub | - | GitHub OAuth client secret |
| `GITHUB_REDIRECT_URI` | No | `http://localhost:8000/auth/github/callback` | GitHub OAuth redirect |
| `FRONTEND_URL` | No | `http://localhost:3000` | Frontend URL for redirects |
| `BACKEND_URL` | No | `http://localhost:8000` | Backend URL |
| `SQL_ECHO` | No | `false` | Enable SQL query logging |
