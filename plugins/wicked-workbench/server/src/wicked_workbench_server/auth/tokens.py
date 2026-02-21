"""
JWT token generation and validation.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from jwt.exceptions import PyJWTError as JWTError
from sqlalchemy.orm import Session

from .config import config
from .models import Session as SessionModel
from .models import User


def create_access_token(user_id: str, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.

    Args:
        user_id: User ID to encode in token
        expires_delta: Custom expiration time (default: 15 minutes)

    Returns:
        Encoded JWT token string
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES)

    expire = datetime.now(timezone.utc) + expires_delta
    to_encode = {
        "sub": user_id,
        "type": "access",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    encoded_jwt = jwt.encode(to_encode, config.JWT_SECRET_KEY, algorithm=config.JWT_ALGORITHM)
    return encoded_jwt


def create_refresh_token() -> str:
    """
    Create a secure random refresh token.

    Returns:
        Random token string (64 characters)
    """
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    """
    Hash a token for secure storage.

    Args:
        token: Token to hash

    Returns:
        SHA256 hash of token
    """
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db: Session, user_id: str, refresh_token: str) -> SessionModel:
    """
    Create a new session for a user.

    Args:
        db: Database session
        user_id: User ID
        refresh_token: Refresh token (will be hashed before storage)

    Returns:
        Created Session model
    """
    expires_at = datetime.now(timezone.utc) + timedelta(days=config.REFRESH_TOKEN_EXPIRE_DAYS)
    session = SessionModel(
        user_id=user_id,
        refresh_token_hash=hash_token(refresh_token),
        expires_at=expires_at,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def verify_access_token(token: str) -> Optional[str]:
    """
    Verify and decode an access token.

    Args:
        token: JWT access token

    Returns:
        User ID if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, config.JWT_SECRET_KEY, algorithms=[config.JWT_ALGORITHM])
        user_id: str = payload.get("sub")
        token_type: str = payload.get("type")

        if user_id is None or token_type != "access":
            return None

        return user_id
    except JWTError:
        return None


def verify_refresh_token(db: Session, refresh_token: str) -> Optional[User]:
    """
    Verify a refresh token and return associated user.

    Args:
        db: Database session
        refresh_token: Refresh token to verify

    Returns:
        User if valid session exists, None otherwise
    """
    token_hash = hash_token(refresh_token)
    session = db.query(SessionModel).filter(
        SessionModel.refresh_token_hash == token_hash
    ).first()

    if not session or session.is_expired():
        return None

    # Update last used timestamp
    session.last_used_at = datetime.now(timezone.utc)
    db.commit()

    return session.user


def revoke_session(db: Session, session_id: str) -> bool:
    """
    Revoke a session by ID.

    Args:
        db: Database session
        session_id: Session ID to revoke

    Returns:
        True if session was revoked, False if not found
    """
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if session:
        db.delete(session)
        db.commit()
        return True
    return False


def revoke_all_user_sessions(db: Session, user_id: str) -> int:
    """
    Revoke all sessions for a user.

    Args:
        db: Database session
        user_id: User ID

    Returns:
        Number of sessions revoked
    """
    count = db.query(SessionModel).filter(SessionModel.user_id == user_id).delete()
    db.commit()
    return count
