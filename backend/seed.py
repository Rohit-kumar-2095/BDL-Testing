"""
Seeds the database with default BDL procurement team accounts
if the users table is empty on startup.
"""

from sqlalchemy.orm import Session

from .auth import hash_password
from .models import User

_DEFAULT_USERS = [
    {
        "username": "bdl.admin",
        "password": "BDL@2024",
        "full_name": "BDL Admin",
    },
    {
        "username": "procurement1",
        "password": "Tender@123",
        "full_name": "Procurement Officer 1",
    },
    {
        "username": "procurement2",
        "password": "Tender@123",
        "full_name": "Procurement Officer 2",
    },
]


def seed_users(db: Session) -> None:
    """Insert default users if the table is empty."""
    count = db.query(User).count()
    if count > 0:
        return  # already seeded

    print("[seed] Seeding default BDL users …")
    for u in _DEFAULT_USERS:
        user = User(
            username=u["username"],
            hashed_password=hash_password(u["password"]),
            full_name=u["full_name"],
        )
        db.add(user)
    db.commit()
    print(f"[seed] Created {len(_DEFAULT_USERS)} users.")
