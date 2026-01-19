"""
Simple password reset using bcrypt directly
"""
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os
import bcrypt

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

# Email to reset
email = "junaid.abdur@example.com"
new_password = "SecurePass123!"

# Hash the new password using bcrypt directly
password_bytes = new_password.encode('utf-8')
salt = bcrypt.gensalt()
password_hash = bcrypt.hashpw(password_bytes, salt).decode('utf-8')

print("=" * 60)
print("RESETTING PASSWORD")
print("=" * 60)

try:
    with engine.connect() as conn:
        # Update password
        query = text("""
            UPDATE users 
            SET password_hash = :password_hash
            WHERE email = :email
        """)
        
        result = conn.execute(query, {"password_hash": password_hash, "email": email})
        conn.commit()
        
        if result.rowcount > 0:
            print(f"\nPassword updated successfully for {email}")
            print(f"New password: {new_password}")
            print(f"\nYou can now login with:")
            print(f"Email: {email}")
            print(f"Password: {new_password}")
        else:
            print(f"\nUser not found: {email}")
        
except Exception as e:
    print(f"\nError: {e}")

print("=" * 60)
