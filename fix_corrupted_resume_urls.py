"""
One-time script to fix corrupted resume URLs in the database
Run this once to clean up URLs with newlines and remove fl_attachment
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# MongoDB connection
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "bgv_core")

client = AsyncIOMotorClient(MONGO_URI)
db = client[MONGO_DB_NAME]
jobSeekersCol = db["job_seekers"]


async def fix_resume_urls():
    """
    Fix all corrupted resume URLs in the database:
    1. Remove newlines (\n, \r)
    2. Remove fl_attachment (store clean URLs)
    3. Encode spaces as %20
    4. Strip whitespace
    """
    print("🔍 Searching for job seekers with resume URLs...")
    
    job_seekers = await jobSeekersCol.find({"resumeUrl": {"$exists": True, "$ne": ""}}).to_list(None)
    
    print(f"📊 Found {len(job_seekers)} job seekers with resume URLs")
    
    fixed_count = 0
    
    for js in job_seekers:
        old_url = js.get("resumeUrl", "")
        
        if not old_url:
            continue
        
        # Clean the URL
        clean_url = old_url.strip()
        
        # Remove newlines and carriage returns
        clean_url = clean_url.replace('\n', '').replace('\r', '')
        
        # Remove fl_attachment (we add it dynamically now)
        clean_url = clean_url.replace('/fl_attachment', '')
        
        # Encode spaces
        clean_url = clean_url.replace(' ', '%20')
        
        # Remove any duplicate slashes (except in https://)
        import re
        clean_url = re.sub(r'(?<!:)//+', '/', clean_url)
        
        # Check if URL changed
        if clean_url != old_url:
            print(f"\n🔧 Fixing URL for: {js.get('name', 'Unknown')}")
            print(f"   Old: {repr(old_url)[:100]}...")
            print(f"   New: {clean_url[:100]}...")
            
            # Update in database
            await jobSeekersCol.update_one(
                {"_id": js["_id"]},
                {"$set": {"resumeUrl": clean_url}}
            )
            
            fixed_count += 1
    
    print(f"\n✅ Fixed {fixed_count} corrupted URLs")
    print(f"✅ {len(job_seekers) - fixed_count} URLs were already clean")


async def main():
    try:
        await fix_resume_urls()
        print("\n🎉 Migration completed successfully!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        client.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Resume URL Cleanup Script")
    print("=" * 60)
    asyncio.run(main())
