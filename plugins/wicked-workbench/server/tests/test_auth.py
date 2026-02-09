"""
Basic test for authentication implementation.
"""

import os
import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Create a temporary database file for testing
test_db = tempfile.NamedTemporaryFile(mode='w', suffix='.db', delete=False)
test_db_path = test_db.name
test_db.close()

# Set test database before importing app
os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["SESSION_SECRET_KEY"] = "test-session-secret-key"

from fastapi.testclient import TestClient

from wicked_workbench_server.app import app
from wicked_workbench_server.auth.database import Base, engine


def setup_test_db():
    """Initialize test database schema."""
    # Drop all tables and recreate
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_auth_endpoints_exist():
    """Test that all auth endpoints are registered."""
    setup_test_db()

    client = TestClient(app)

    # Test health endpoint
    response = client.get("/health")
    assert response.status_code == 200

    # Test auth endpoints exist (even if they return errors without proper setup)
    endpoints = [
        "/auth/me",
        "/auth/accounts",
    ]

    for endpoint in endpoints:
        response = client.get(endpoint)
        # Should return 401 or 403, not 404
        assert response.status_code in [401, 403], f"{endpoint} returned {response.status_code}"


def test_register_and_login():
    """Test user registration and login flow."""
    setup_test_db()

    client = TestClient(app)

    # Register a new user
    register_data = {
        "email": "test@example.com",
        "password": "securepassword123",
        "display_name": "Test User"
    }

    response = client.post("/auth/register", json=register_data)
    assert response.status_code == 200

    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "test@example.com"

    # Login with the same credentials
    login_data = {
        "email": "test@example.com",
        "password": "securepassword123"
    }

    response = client.post("/auth/login", json=login_data)
    assert response.status_code == 200

    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


def test_protected_endpoint():
    """Test accessing protected endpoint with token."""
    setup_test_db()

    client = TestClient(app)

    # Register a user
    register_data = {
        "email": "protected@example.com",
        "password": "password123"
    }

    response = client.post("/auth/register", json=register_data)
    assert response.status_code == 200

    access_token = response.json()["access_token"]

    # Access protected endpoint
    headers = {"Authorization": f"Bearer {access_token}"}
    response = client.get("/auth/me", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "protected@example.com"


def test_invalid_credentials():
    """Test login with invalid credentials."""
    setup_test_db()

    client = TestClient(app)

    # Try to login with non-existent user
    login_data = {
        "email": "nonexistent@example.com",
        "password": "wrongpassword"
    }

    response = client.post("/auth/login", json=login_data)
    assert response.status_code == 401


def test_token_refresh():
    """Test refresh token flow."""
    setup_test_db()

    client = TestClient(app)

    # Register a user
    register_data = {
        "email": "refresh@example.com",
        "password": "password123"
    }

    response = client.post("/auth/register", json=register_data)
    assert response.status_code == 200

    refresh_token = response.json()["refresh_token"]

    # Refresh the token
    refresh_data = {"refresh_token": refresh_token}
    response = client.post("/auth/refresh", json=refresh_data)

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    # Should get a new refresh token
    assert data["refresh_token"] != refresh_token


if __name__ == "__main__":
    print("Running authentication tests...")

    try:
        test_auth_endpoints_exist()
        print("✅ Auth endpoints exist")

        test_register_and_login()
        print("✅ Register and login works")

        test_protected_endpoint()
        print("✅ Protected endpoint works")

        test_invalid_credentials()
        print("✅ Invalid credentials rejected")

        test_token_refresh()
        print("✅ Token refresh works")

        print("\n🎉 All tests passed!")
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error running tests: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        # Clean up test database
        if os.path.exists(test_db_path):
            os.unlink(test_db_path)
