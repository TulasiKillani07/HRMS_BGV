"""
MongoDB Document Model for Jobs Collection (ATS)
This file documents the structure of job postings in MongoDB
"""
from typing import Optional, List
from datetime import datetime


class JobDocument:
    """
    MongoDB document structure for jobs collection
    
    This is a reference model showing what fields exist in the database.
    Not used for validation (Pydantic schemas handle that).
    """
    
    # Required fields
    _id: str                          # MongoDB ObjectId (auto-generated)
    orgId: str                        # Reference to organizations collection
    orgName: str                      # Organization name (denormalized)
    title: str                        # "Senior ML Engineer"
    department: str                   # "Engineering"
    location: str                     # "Hyderabad, India"
    type: str                         # "Full-time", "Part-time", "Contract", "Internship"
    experience: str                   # "4-7 years"
    salary: str                       # "$120k-$160k"
    skills: List[str]                 # ["Python", "TensorFlow", "AWS"]
    description: str                  # Full job description (HTML/Markdown)
    status: str                       # "open", "closed", "draft"
    
    # Optional fields
    deadline: Optional[datetime] = None  # Application deadline (auto-close when passed)
    
    # Counts (auto-calculated from applications)
    applicantCount: int = 0           # Total applications
    shortlistedCount: int = 0         # Applications in "Shortlisted" stage
    hiredCount: int = 0               # Applications in "Hired" stage
    
    # Soft delete
    isDeleted: bool = False           # Soft delete flag
    deletedAt: Optional[datetime] = None
    deletedBy: Optional[str] = None   # Email of who deleted
    
    # Metadata
    createdBy: str                    # Email of creator (ORG_HR/SPOC)
    createdAt: datetime
    updatedAt: datetime


# MongoDB Collection Name
COLLECTION_NAME = "jobs"

# Indexes (for reference - should be created in MongoDB)
INDEXES = [
    {"orgId": 1},                     # Filter by organization
    {"status": 1},                    # Filter by status
    {"isDeleted": 1},                 # Exclude deleted jobs
    {"deadline": 1},                  # For auto-close expired jobs
    {"createdAt": -1},                # Sort by creation date
    {"title": "text", "skills": "text"}  # Text search on title and skills
]

# Valid values
VALID_STATUSES = ["open", "closed", "draft"]
VALID_TYPES = ["Full-time", "Part-time", "Contract", "Internship"]
