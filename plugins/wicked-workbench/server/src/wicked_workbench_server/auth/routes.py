"""
FastAPI routes for authentication.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from .config import config
from .database import get_db
from .middleware import get_current_user
from .models import User
from .oauth import (
    generate_state_token,
    get_github_user_info,
    get_google_user_info,
    get_user_oauth_accounts,
    handle_oauth_login,
    oauth,
    unlink_oauth_account,
)
from .password import hash_password, verify_password
from .tokens import (
    create_access_token,
    create_refresh_token,
    create_session,
    revoke_all_user_sessions,
    verify_refresh_token,
)

router = APIRouter(prefix="/auth", tags=["authentication"])


# ===== Request/Response Models =====

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict


class UserResponse(BaseModel):
    id: str
    email: str
    email_verified: bool
    display_name: Optional[str]
    avatar_url: Optional[str]


class OAuthAccountResponse(BaseModel):
    id: str
    provider: str
    provider_email: Optional[str]
    created_at: str


# ===== Email/Password Authentication =====

@router.post("/register", response_model=TokenResponse)
async def register(request: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new user with email and password."""
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Create new user
    user = User(
        email=request.email,
        password_hash=hash_password(request.password),
        display_name=request.display_name,
        email_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Create tokens
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token()
    create_session(db, user.id, refresh_token)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=user.to_dict(),
    )


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Login with email and password."""
    # Find user
    user = db.query(User).filter(User.email == request.email).first()
    if not user or not user.password_hash:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Verify password
    if not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Create tokens
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token()
    create_session(db, user.id, refresh_token)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=user.to_dict(),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(request: RefreshRequest, db: Session = Depends(get_db)):
    """Refresh access token using refresh token."""
    user = verify_refresh_token(db, request.refresh_token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    # Create new tokens (refresh token rotation)
    access_token = create_access_token(user.id)
    new_refresh_token = create_refresh_token()
    create_session(db, user.id, new_refresh_token)

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        user=user.to_dict(),
    )


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Logout - revoke all sessions."""
    count = revoke_all_user_sessions(db, current_user.id)
    return {"message": f"Logged out successfully. {count} sessions revoked."}


# ===== Google OAuth =====

@router.get("/google")
async def google_login(request: Request):
    """Start Google OAuth flow."""
    if not config.is_google_configured():
        raise HTTPException(status_code=503, detail="Google OAuth is not configured")

    # Generate state token for CSRF protection
    state = generate_state_token()
    request.session["oauth_state"] = state

    redirect_uri = config.GOOGLE_REDIRECT_URI
    return await oauth.google.authorize_redirect(request, redirect_uri, state=state)


@router.get("/google/callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    """Handle Google OAuth callback."""
    if not config.is_google_configured():
        raise HTTPException(status_code=503, detail="Google OAuth is not configured")

    # Verify state token
    state = request.session.get("oauth_state")
    if not state or state != request.query_params.get("state"):
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    # Exchange code for token
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"OAuth failed: {str(e)}")

    # Get user info
    user_info = await get_google_user_info(token["access_token"])
    if not user_info:
        raise HTTPException(status_code=400, detail="Failed to fetch user info from Google")

    # Handle login/registration
    user = handle_oauth_login(db, "google", user_info)

    # Create tokens
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token()
    create_session(db, user.id, refresh_token)

    # Redirect to frontend with tokens
    redirect_url = f"{config.FRONTEND_URL}/auth/callback?access_token={access_token}&refresh_token={refresh_token}"
    return RedirectResponse(url=redirect_url)


# ===== GitHub OAuth =====

@router.get("/github")
async def github_login(request: Request):
    """Start GitHub OAuth flow."""
    if not config.is_github_configured():
        raise HTTPException(status_code=503, detail="GitHub OAuth is not configured")

    # Generate state token for CSRF protection
    state = generate_state_token()
    request.session["oauth_state"] = state

    redirect_uri = config.GITHUB_REDIRECT_URI
    return await oauth.github.authorize_redirect(request, redirect_uri, state=state)


@router.get("/github/callback")
async def github_callback(request: Request, db: Session = Depends(get_db)):
    """Handle GitHub OAuth callback."""
    if not config.is_github_configured():
        raise HTTPException(status_code=503, detail="GitHub OAuth is not configured")

    # Verify state token
    state = request.session.get("oauth_state")
    if not state or state != request.query_params.get("state"):
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    # Exchange code for token
    try:
        token = await oauth.github.authorize_access_token(request)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"OAuth failed: {str(e)}")

    # Get user info
    user_info = await get_github_user_info(token["access_token"])
    if not user_info:
        raise HTTPException(status_code=400, detail="Failed to fetch user info from GitHub")

    # Handle login/registration
    user = handle_oauth_login(db, "github", user_info)

    # Create tokens
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token()
    create_session(db, user.id, refresh_token)

    # Redirect to frontend with tokens
    redirect_url = f"{config.FRONTEND_URL}/auth/callback?access_token={access_token}&refresh_token={refresh_token}"
    return RedirectResponse(url=redirect_url)


# ===== User Profile =====

@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """Get current user profile."""
    return UserResponse(**current_user.to_dict())


# ===== OAuth Account Management =====

@router.get("/accounts", response_model=list[OAuthAccountResponse])
async def list_oauth_accounts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all OAuth accounts linked to current user."""
    accounts = get_user_oauth_accounts(db, current_user.id)
    return [OAuthAccountResponse(**account.to_dict()) for account in accounts]


@router.delete("/accounts/{provider}")
async def unlink_account(
    provider: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Unlink an OAuth account."""
    if provider not in ["google", "github"]:
        raise HTTPException(status_code=400, detail="Invalid provider")

    success = unlink_oauth_account(db, current_user.id, provider)
    if not success:
        raise HTTPException(status_code=404, detail=f"No {provider} account linked")

    return {"message": f"{provider.capitalize()} account unlinked successfully"}
