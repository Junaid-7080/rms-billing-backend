"""
Check existing admin users
"""
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

print("=" * 60)
print("CHECKING ADMIN USERS")
print("=" * 60)

try:
    with engine.connect() as conn:
        # Check all admin users
        query = text("""
            SELECT 
                email,
                first_name,
                last_name,
                role,
                email_verified,
                is_active,
                created_at
            FROM users 
            WHERE role = 'admin'
            ORDER BY created_at ASC
        """)
        
        result = conn.execute(query)
        admins = result.fetchall()
        
        if admins:
            print(f"\nFound {len(admins)} admin user(s):\n")
            for idx, admin in enumerate(admins, 1):
                print(f"{idx}. Email: {admin.email}")
                print(f"   Name: {admin.first_name} {admin.last_name}")
                print(f"   Role: {admin.role}")
                print(f"   Email Verified: {admin.email_verified}")
                print(f"   Active: {admin.is_active}")
                print(f"   Created: {admin.created_at}")
                print(f"   Password: [HASHED - cannot retrieve]")
                print()
        else:
            print("\nNo admin users found!")
            print("\nTo create admin, register first user:")
            print("POST /api/v1/auth/register")
            print("First user automatically gets admin role")
        
        # Check total users
        count_query = text("SELECT COUNT(*) FROM users")
        total = conn.execute(count_query).scalar()
        print(f"Total users in database: {total}")
        
except Exception as e:
    print(f"\nError: {e}")

print("=" * 60)