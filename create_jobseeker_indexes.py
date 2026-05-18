"""
Script to create indexes for job_seekers collection
Run this once to set up unique indexes on email and phone
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# MongoDB configuration
MONGO_URI = "mongodb+srv://maihoo:akonpopStar%40143@maihoo.ztaytqd.mongodb.net/?appName=maihoo"
MONGO_DB_NAME = "bgv_core"


async def create_indexes():
    """Create unique indexes for job_seekers collection"""
    print("🔗 Connecting to MongoDB...")
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[MONGO_DB_NAME]
    job_seekers_col = db["job_seekers"]
    
    print("📊 Creating indexes...")
    
    try:
        # Create unique index on email
        result1 = await job_seekers_col.create_index("email", unique=True)
        print(f"✅ Created unique index on 'email': {result1}")
        
        # Create unique index on phone
        result2 = await job_seekers_col.create_index("phone", unique=True)
        print(f"✅ Created unique index on 'phone': {result2}")
        
        # List all indexes
        indexes = await job_seekers_col.list_indexes().to_list(length=None)
        print("\n📋 Current indexes on job_seekers collection:")
        for idx in indexes:
            print(f"  - {idx['name']}: {idx['key']}")
        
        print("\n✅ All indexes created successfully!")
        
    except Exception as e:
        print(f"❌ Error creating indexes: {e}")
    
    finally:
        client.close()
        print("\n🔌 Connection closed")


if __name__ == "__main__":
    asyncio.run(create_indexes())
