"""
OAuth2 and authentication configuration.
"""

import os
from typing import Optional


class AuthConfig:
    """Authentication configuration from environment variables."""

    # JWT Configuration
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "change-me-in-production-please")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Google OAuth
    GOOGLE_CLIENT_ID: Optional[str] = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET: Optional[str] = os.getenv("GOOGLE_CLIENT_SECRET")
    GOOGLE_REDIRECT_URI: str = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")

    # GitHub OAuth
    GITHUB_CLIENT_ID: Optional[str] = os.getenv("GITHUB_CLIENT_ID")
    GITHUB_CLIENT_SECRET: Optional[str] = os.getenv("GITHUB_CLIENT_SECRET")
    GITHUB_REDIRECT_URI: str = os.getenv("GITHUB_REDIRECT_URI", "http://localhost:8000/auth/github/callback")

    # Application URLs
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")
    BACKEND_URL: str = os.getenv("BACKEND_URL", "http://localhost:8000")

    @classmethod
    def is_google_configured(cls) -> bool:
        """Check if Google OAuth is configured."""
        return bool(cls.GOOGLE_CLIENT_ID and cls.GOOGLE_CLIENT_SECRET)

    @classmethod
    def is_github_configured(cls) -> bool:
        """Check if GitHub OAuth is configured."""
        return bool(cls.GITHUB_CLIENT_ID and cls.GITHUB_CLIENT_SECRET)

    @classmethod
    def get_oauth_config(cls, provider: str) -> dict:
        """
        Get OAuth configuration for a specific provider.

        Args:
            provider: 'google' or 'github'

        Returns:
            Dict with client_id, client_secret, redirect_uri

        Raises:
            ValueError: If provider is not configured
        """
        if provider == "google":
            if not cls.is_google_configured():
                raise ValueError("Google OAuth is not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.")
            return {
                "client_id": cls.GOOGLE_CLIENT_ID,
                "client_secret": cls.GOOGLE_CLIENT_SECRET,
                "redirect_uri": cls.GOOGLE_REDIRECT_URI,
                "scope": "openid email profile",
                "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
                "access_token_url": "https://oauth2.googleapis.com/token",
                "userinfo_url": "https://www.googleapis.com/oauth2/v2/userinfo",
            }
        elif provider == "github":
            if not cls.is_github_configured():
                raise ValueError("GitHub OAuth is not configured. Set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET.")
            return {
                "client_id": cls.GITHUB_CLIENT_ID,
                "client_secret": cls.GITHUB_CLIENT_SECRET,
                "redirect_uri": cls.GITHUB_REDIRECT_URI,
                "scope": "user:email",
                "authorize_url": "https://github.com/login/oauth/authorize",
                "access_token_url": "https://github.com/login/oauth/access_token",
                "userinfo_url": "https://api.github.com/user",
            }
        else:
            raise ValueError(f"Unsupported OAuth provider: {provider}")


# Export singleton instance
config = AuthConfig()
