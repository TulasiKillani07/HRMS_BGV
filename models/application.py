"""
MongoDB Document Model for Applications Collection (ATS)
This file documents the structure of job applications in MongoDB
"""
from typing import Optional, List, Dict, Any
from datetime import datetime


class ApplicationDocument:
    """
    MongoDB document structure for applications collection
    
    This is a reference model showing what fields exist in the database.
    Not used for validation (Pydantic schemas handle that).
    """
    
    # Required fields
    _id: str                          # MongoDB ObjectId (auto-generated)
    jobId: str                        # Reference to jobs collection
    orgId: str                        # Reference to organizations collection (for filtering)
    candidateId: str                  # Reference to candidates collection
    
    # Candidate info (denormalized for quick access)
    candidateName: str
    candidateEmail: str
    candidatePhone: str
    resumeUrl: str                    # S3 URL to resume
    
    # Application details
    stage: str                        # Current stage in pipeline
    source: str                       # How candidate entered: "AI_SCREENING", "JOB_PORTAL", "MANUAL"
    aiScore: Optional[float] = None   # AI screening score (0-100)
    notes: str = ""                   # HR notes about candidate
    
    # Stage history (audit trail)
    stageHistory: List[Dict[str, Any]] = []
    # [
    #   {
    #     "stage": "Applied",
    #     "changedBy": "hr@example.com",
    #     "changedAt": datetime,
    #     "notes": "Initial application"
    #   }
    # ]
    
    # Soft delete
    isDeleted: bool = False           # Soft delete flag
    deletedAt: Optional[datetime] = None
    deletedBy: Optional[str] = None   # Email of who deleted
    
    # Metadata
    appliedAt: datetime               # When application was created
    updatedAt: datetime               # Last update timestamp


# MongoDB Collection Name
COLLECTION_NAME = "applications"

# Indexes (for reference - should be created in MongoDB)
INDEXES = [
    {"jobId": 1},                     # Filter by job
    {"orgId": 1},                     # Filter by organization
    {"candidateId": 1},               # Filter by candidate
    {"stage": 1},                     # Filter by stage
    {"isDeleted": 1},                 # Exclude deleted applications
    {"appliedAt": -1},                # Sort by application date
    {"candidateEmail": 1, "jobId": 1}  # Prevent duplicate applications (unique)
]

# Valid values
VALID_STAGES = [
    "Applied",        # Initial application
    "AI Screened",    # After AI screening
    "Shortlisted",    # Selected for interview
    "Interview",      # Interview scheduled/completed
    "Hired",          # Offer accepted
    "Rejected"        # Not selected
]

VALID_SOURCES = [
    "AI_SCREENING",   # Added via AI resume screening
    "JOB_PORTAL",     # Applied through job portal
    "MANUAL"          # Manually added by HR
]
