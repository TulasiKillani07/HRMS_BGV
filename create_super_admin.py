#!/usr/bin/env python3
"""
Script to create SUPER_ADMIN user in MongoDB
Run this once to bootstrap your application
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "bgv_core")

async def create_super_admin():
    """Create SUPER_ADMIN user"""
    
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[MONGO_DB]
    usersCol = db["users"]
    
    # Check if SUPER_ADMIN already exists
    existing = await usersCol.find_one({"role": "SUPER_ADMIN"})
    if existing:
        print(f"⚠️  SUPER_ADMIN already exists: {existing.get('email')}")
        print(f"   Name: {existing.get('userName')}")
        print(f"   Role: {existing.get('role')}")
        
        update = input("\nCreate another SUPER_ADMIN? (y/n): ").lower()
        if update != 'y':
            print("❌ Cancelled")
            client.close()
            return
    
    # Get user details
    print("\n" + "="*60)
    print("🔐 CREATE SUPER_ADMIN USER")
    print("="*60)
    
    userName = input("Enter name: ").strip()
    email = input("Enter email: ").strip().lower()
    password = input("Enter password (default: Admin@123): ").strip() or "Admin@123"
    phoneNumber = input("Enter phone number (optional): ").strip() or None
    
    # Check if email already exists
    existing_email = await usersCol.find_one({"email": email})
    if existing_email:
        print(f"\n❌ Error: User with email '{email}' already exists!")
        client.close()
        return
    
    # Create SUPER_ADMIN user
    now = datetime.now(timezone.utc).isoformat()
    
    super_admin = {
        "userName": userName,
        "email": email,
        "password": password,  # In production, hash this!
        "role": "SUPER_ADMIN",
        "phoneNumber": phoneNumber,
        "organizationId": None,  # SUPER_ADMIN has no organization
        "permissions": [
            "organization:view",
            "organization:update",
            "organization:create",
            "users:manage",
            "verification:view",
            "verification:assign",
            "candidate:create",
            "dashboard:view"
        ],
        "isActive": True,
        "createdAt": now,
        "createdBy": "system"
    }
    
    # Insert into database
    result = await usersCol.insert_one(super_admin)
    
    print("\n" + "="*60)
    print("✅ SUPER_ADMIN CREATED SUCCESSFULLY!")
    print("="*60)
    print(f"User ID: {result.inserted_id}")
    print(f"Name: {userName}")
    print(f"Email: {email}")
    print(f"Password: {password}")
    print(f"Role: SUPER_ADMIN")
    print(f"Phone: {phoneNumber or 'Not provided'}")
    print("="*60)
    print("\n🔑 Login Credentials:")
    print(f"   Email: {email}")
    print(f"   Password: {password}")
    print("\n📍 Login URL: http://localhost:8000/auth/login")
    print("="*60)
    
    client.close()

if __name__ == "__main__":
    asyncio.run(create_super_admin())
