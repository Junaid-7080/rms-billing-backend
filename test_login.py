"""
Test login with the updated security.py
"""
import sys
sys.path.insert(0, 'c:/Users/Dell/Desktop/invoice_app_backend-main/invoice_app_backend')

from app.core.security import verify_password
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

email = "junaid.abdur@example.com"
test_password = "SecurePass123!"

print("=" * 60)
print("TESTING UPDATED LOGIN LOGIC")
print("=" * 60)

try:
    with engine.connect() as conn:
        # Get stored hash
        query = text("SELECT password_hash FROM users WHERE email = :email")
        result = conn.execute(query, {"email": email}).fetchone()
        
        if result:
            stored_hash = result[0]
            print(f"\nTesting password verification...")
            print(f"Email: {email}")
            print(f"Password: {test_password}")
            
            # Test with updated verify_password function
            is_valid = verify_password(test_password, stored_hash)
            
            if is_valid:
                print("\nSUCCESS! Password verification working!")
                print("You can now login in Swagger")
            else:
                print("\nFAILED! Password verification still not working")
        else:
            print(f"\nUser not found: {email}")
        
except Exception as e:
    print(f"\nError: {e}")
    import traceback
    traceback.print_exc()

print("=" * 60)
