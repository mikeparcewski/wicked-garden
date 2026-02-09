"""
Authentication middleware for protected endpoints.
"""

from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import get_db
from .models import User
from .tokens import verify_access_token

# HTTP Bearer token scheme
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency to get the current authenticated user.

    Usage:
        @app.get("/protected")
        def protected_route(user: User = Depends(get_current_user)):
            return {"user_id": user.id}

    Args:
        credentials: HTTP Bearer token from Authorization header
        db: Database session

    Returns:
        Authenticated User

    Raises:
        HTTPException: If token is invalid or user not found
    """
    token = credentials.credentials

    # Verify token
    user_id = verify_access_token(token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get user from database
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Dependency to get the current user if authenticated, otherwise None.

    Usage for optional authentication:
        @app.get("/optional-auth")
        def optional_auth_route(user: Optional[User] = Depends(get_current_user_optional)):
            if user:
                return {"message": f"Hello {user.email}"}
            return {"message": "Hello anonymous"}

    Args:
        credentials: HTTP Bearer token from Authorization header (optional)
        db: Database session

    Returns:
        Authenticated User or None
    """
    if not credentials:
        return None

    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None
