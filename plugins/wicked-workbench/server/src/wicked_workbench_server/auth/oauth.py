"""
OAuth2 handlers for Google and GitHub authentication.
"""

import secrets
from typing import Optional

import httpx
from authlib.integrations.starlette_client import OAuth
from sqlalchemy.orm import Session
from starlette.config import Config

from .config import config
from .models import OAuthAccount, User

# Initialize OAuth
oauth_config = Config(environ={
    "GOOGLE_CLIENT_ID": config.GOOGLE_CLIENT_ID or "",
    "GOOGLE_CLIENT_SECRET": config.GOOGLE_CLIENT_SECRET or "",
    "GITHUB_CLIENT_ID": config.GITHUB_CLIENT_ID or "",
    "GITHUB_CLIENT_SECRET": config.GITHUB_CLIENT_SECRET or "",
})

oauth = OAuth(oauth_config)

# Register Google OAuth
if config.is_google_configured():
    oauth.register(
        name="google",
        client_id=config.GOOGLE_CLIENT_ID,
        client_secret=config.GOOGLE_CLIENT_SECRET,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )

# Register GitHub OAuth
if config.is_github_configured():
    oauth.register(
        name="github",
        client_id=config.GITHUB_CLIENT_ID,
        client_secret=config.GITHUB_CLIENT_SECRET,
        authorize_url="https://github.com/login/oauth/authorize",
        access_token_url="https://github.com/login/oauth/access_token",
        api_base_url="https://api.github.com/",
        client_kwargs={"scope": "user:email"},
    )


def generate_state_token() -> str:
    """Generate a secure random state token for CSRF protection."""
    return secrets.token_urlsafe(32)


async def get_google_user_info(access_token: str) -> Optional[dict]:
    """
    Fetch user info from Google using access token.

    Args:
        access_token: Google OAuth access token

    Returns:
        User info dict with id, email, name, picture
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        if response.status_code == 200:
            return response.json()
    return None


async def get_github_user_info(access_token: str) -> Optional[dict]:
    """
    Fetch user info from GitHub using access token.

    Args:
        access_token: GitHub OAuth access token

    Returns:
        User info dict with id, login, name, avatar_url, email
    """
    async with httpx.AsyncClient() as client:
        # Get user profile
        user_response = await client.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json"
            }
        )
        if user_response.status_code != 200:
            return None

        user_data = user_response.json()

        # Get primary email if not public
        if not user_data.get("email"):
            emails_response = await client.get(
                "https://api.github.com/user/emails",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github.v3+json"
                }
            )
            if emails_response.status_code == 200:
                emails = emails_response.json()
                primary_email = next((e for e in emails if e.get("primary")), None)
                if primary_email:
                    user_data["email"] = primary_email["email"]

        return user_data


def handle_oauth_login(db: Session, provider: str, oauth_profile: dict) -> User:
    """
    Handle OAuth login - create user or link account.

    This implements the profile merging logic:
    1. Check if OAuth account exists -> return linked user
    2. Check if user with same email exists -> link account to existing user
    3. Otherwise, create new user and link account

    Args:
        db: Database session
        provider: 'google' or 'github'
        oauth_profile: OAuth provider user profile

    Returns:
        User (existing or newly created)
    """
    provider_user_id = str(oauth_profile["id"])
    email = oauth_profile.get("email")

    # Check if OAuth account already exists
    existing_oauth = db.query(OAuthAccount).filter(
        OAuthAccount.provider == provider,
        OAuthAccount.provider_user_id == provider_user_id
    ).first()

    if existing_oauth:
        return existing_oauth.user

    # Check if user with same email exists
    if email:
        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            # Link OAuth account to existing user
            link_oauth_account(db, existing_user, provider, oauth_profile)
            return existing_user

    # Create new user
    new_user = create_user_from_oauth(db, provider, oauth_profile)
    link_oauth_account(db, new_user, provider, oauth_profile)
    return new_user


def create_user_from_oauth(db: Session, provider: str, oauth_profile: dict) -> User:
    """
    Create a new user from OAuth profile.

    Args:
        db: Database session
        provider: 'google' or 'github'
        oauth_profile: OAuth provider user profile

    Returns:
        Created User
    """
    if provider == "google":
        email = oauth_profile.get("email")
        display_name = oauth_profile.get("name")
        avatar_url = oauth_profile.get("picture")
        email_verified = oauth_profile.get("email_verified", False)
    elif provider == "github":
        email = oauth_profile.get("email")
        display_name = oauth_profile.get("name") or oauth_profile.get("login")
        avatar_url = oauth_profile.get("avatar_url")
        email_verified = bool(email)  # GitHub emails are verified
    else:
        raise ValueError(f"Unsupported provider: {provider}")

    user = User(
        email=email,
        email_verified=email_verified,
        display_name=display_name,
        avatar_url=avatar_url,
        password_hash=None,  # OAuth-only user
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def link_oauth_account(db: Session, user: User, provider: str, oauth_profile: dict) -> OAuthAccount:
    """
    Link an OAuth account to a user.

    Args:
        db: Database session
        user: User to link account to
        provider: 'google' or 'github'
        oauth_profile: OAuth provider user profile

    Returns:
        Created OAuthAccount
    """
    provider_user_id = str(oauth_profile["id"])
    provider_email = oauth_profile.get("email")

    oauth_account = OAuthAccount(
        user_id=user.id,
        provider=provider,
        provider_user_id=provider_user_id,
        provider_email=provider_email,
    )
    db.add(oauth_account)
    db.commit()
    db.refresh(oauth_account)
    return oauth_account


def unlink_oauth_account(db: Session, user_id: str, provider: str) -> bool:
    """
    Unlink an OAuth account from a user.

    Args:
        db: Database session
        user_id: User ID
        provider: 'google' or 'github'

    Returns:
        True if account was unlinked, False if not found
    """
    oauth_account = db.query(OAuthAccount).filter(
        OAuthAccount.user_id == user_id,
        OAuthAccount.provider == provider
    ).first()

    if oauth_account:
        db.delete(oauth_account)
        db.commit()
        return True
    return False


def get_user_oauth_accounts(db: Session, user_id: str) -> list[OAuthAccount]:
    """
    Get all OAuth accounts linked to a user.

    Args:
        db: Database session
        user_id: User ID

    Returns:
        List of OAuthAccount models
    """
    return db.query(OAuthAccount).filter(OAuthAccount.user_id == user_id).all()
