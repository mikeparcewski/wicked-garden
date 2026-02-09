"""
Authentication module for wicked-workbench.

Provides OAuth2 social login (Google, GitHub) and email/password authentication.
"""

from .config import config
from .database import get_db, init_db
from .middleware import get_current_user, get_current_user_optional
from .models import OAuthAccount, Session, User
from .routes import router

__all__ = [
    "router",
    "config",
    "init_db",
    "get_db",
    "get_current_user",
    "get_current_user_optional",
    "User",
    "OAuthAccount",
    "Session",
]
