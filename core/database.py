"""
Database connection and collections
Centralized MongoDB setup for the application
"""
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()

# MongoDB Configuration
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = "bgv_core"

# Initialize MongoDB Client
client = AsyncIOMotorClient(MONGO_URI)
db = client[MONGO_DB_NAME]

# Collections
usersCol = db["users"]
orgsCol = db["organizations"]
verificationsCol = db["verifications"]
activityLogsCol = db["activity_logs"]
candidatesCol = db["candidates"]
ticketsCol = db["tickets"]
consentTokensCol = db["consent_tokens"]
invoicesCol = db["invoices"]
jobsCol = db["jobs"]                    # Jobs ATS
applicationsCol = db["applications"]    # Job applications
interviewsCol = db["interviews"]        # Interview Management
interviewersCol = db["interviewers"]    # Interviewer Management
jobSeekersCol = db["job_seekers"]       # Job Seeker Portal - user accounts
jobseekerApplicationsCol = db["jobseeker_applications"]  # Job Seeker applications (deprecated)
aiScreeningResultsCol = db["ai_screening_results"]  # AI Screening Results


def get_database():
    """Get database instance"""
    return db


def get_collection(collection_name: str):
    """Get specific collection by name"""
    return db[collection_name]
