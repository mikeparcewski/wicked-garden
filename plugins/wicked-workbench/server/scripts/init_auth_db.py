#!/usr/bin/env python3
"""
Initialize the authentication database.

This script creates all necessary tables for the auth system.
Run this before starting the server for the first time.

Usage:
    python scripts/init_auth_db.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from wicked_workbench_server.auth import init_db


def main():
    """Initialize the database."""
    print("Initializing authentication database...")

    try:
        init_db()
        print("✅ Database initialized successfully!")
        print("Tables created: users, oauth_accounts, sessions")
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
