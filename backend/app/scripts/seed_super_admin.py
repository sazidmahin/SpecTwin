from app.db.session import SessionLocal
from app.services.admin_service import seed_super_admin_from_settings


def main() -> None:
    db = SessionLocal()
    try:
        user = seed_super_admin_from_settings(db)
        if user is None:
            print("No super admin created. Check env vars or existing super admin.")
            return
        print(f"Super admin ready: {user.email}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
