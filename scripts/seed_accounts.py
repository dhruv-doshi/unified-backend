#!/usr/bin/env python3
"""
Seed admin and test accounts.
Run: python scripts/seed_accounts.py
Idempotent — skips existing emails.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import uuid
from sqlalchemy.orm import Session, sessionmaker
from src.infrastructure.database import sync_engine
from src.infrastructure.models.user import User
from src.core.security import hash_password

ACCOUNTS = [
    {"name": "Admin",     "email": "admin@shootright.dev", "password": "Admin1234!"},
    {"name": "Test User", "email": "test@shootright.dev",  "password": "Test1234!"},
]

SessionLocal = sessionmaker(bind=sync_engine)


def seed():
    db: Session = SessionLocal()
    try:
        for acc in ACCOUNTS:
            if db.query(User).filter_by(email=acc["email"]).first():
                print(f"[SKIP]   {acc['email']} already exists")
                continue
            user = User(
                id=uuid.uuid4(),
                name=acc["name"],
                email=acc["email"],
                hashed_password=hash_password(acc["password"]),
                is_verified=True,
            )
            db.add(user)
            print(f"[CREATE] {acc['email']}")
        db.commit()
        print("Done.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
