"""
Test password verification
"""
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os
import bcrypt

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

email = "junaid.abdur@example.com"
test_password = "SecurePass123!"

print("=" * 60)
print("TESTING PASSWORD VERIFICATION")
print("=" * 60)

try:
    with engine.connect() as conn:
        # Get stored hash
        query = text("SELECT password_hash FROM users WHERE email = :email")
        result = conn.execute(query, {"email": email}).fetchone()
        
        if result:
            stored_hash = result[0]
            print(f"\nStored hash: {stored_hash[:30]}...")
            print(f"Hash length: {len(stored_hash)}")
            
            # Test with bcrypt directly
            password_bytes = test_password.encode('utf-8')
            stored_hash_bytes = stored_hash.encode('utf-8')
            
            is_valid = bcrypt.checkpw(password_bytes, stored_hash_bytes)
            print(f"\nBcrypt verification: {is_valid}")
            
            # Test with truncated password (like security.py does)
            password_truncated_bytes = password_bytes[:72]
            password_truncated = password_truncated_bytes.decode('utf-8', errors='ignore')
            
            is_valid_truncated = bcrypt.checkpw(password_truncated.encode('utf-8'), stored_hash_bytes)
            print(f"Bcrypt verification (truncated): {is_valid_truncated}")
            
        else:
            print(f"\nUser not found: {email}")
        
except Exception as e:
    print(f"\nError: {e}")
    import traceback
    traceback.print_exc()

print("=" * 60)
