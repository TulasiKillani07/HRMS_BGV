"""
MongoDB Document Model for Candidates Collection
This file documents the structure of documents stored in MongoDB
"""
from typing import Optional, Dict, Any
from datetime import datetime


class CandidateDocument:
    """
    MongoDB document structure for candidates collection
    
    This is a reference model showing what fields exist in the database.
    Not used for validation (Pydantic schemas handle that).
    """
    
    # Required fields
    _id: str                          # MongoDB ObjectId (auto-generated)
    firstName: str
    lastName: str
    phone: str
    email: str
    aadhaarNumber: str
    panNumber: str
    fatherName: str
    dob: str                          # Format: YYYY-MM-DD
    gender: str                       # Male/Female/Other
    address: str
    district: str
    state: str
    pincode: str
    
    # Organization fields
    organizationId: str               # Reference to organizations collection
    organizationName: str
    
    # Status and metadata
    status: str                       # PENDING/IN_PROGRESS/COMPLETED/REJECTED
    createdAt: datetime
    createdBy: str                    # Email of creator
    
    # Optional fields
    middleName: Optional[str] = None
    uanNumber: Optional[str] = None
    resumePath: Optional[str] = None  # S3 path to resume
    
    # Supervisory Check 1
    supervisoryCheck1: Optional[Dict[str, Any]] = None
    # {
    #     "name": str,
    #     "phone": str,
    #     "email": str,
    #     "relationship": str,
    #     "company": str,
    #     "designation": str,
    #     "workingPeriod": str
    # }
    
    # Supervisory Check 2
    supervisoryCheck2: Optional[Dict[str, Any]] = None
    # Same structure as supervisoryCheck1
    
    # Employment History 1
    employmentHistory1: Optional[Dict[str, Any]] = None
    # {
    #     "company": str,
    #     "designation": str,
    #     "joiningDate": str,
    #     "relievingDate": str,
    #     "hrContact": str,
    #     "hrEmail": str,
    #     "hrName": str,
    #     "address": str
    # }
    
    # Employment History 2
    employmentHistory2: Optional[Dict[str, Any]] = None
    # Same structure as employmentHistory1
    
    # Education Check
    educationCheck: Optional[Dict[str, Any]] = None
    # {
    #     "degree": str,
    #     "specialization": str,
    #     "universityName": str,
    #     "collegeName": str,
    #     "yearOfPassing": str,
    #     "cgpa": str,
    #     "universityContact": str,
    #     "universityEmail": str,
    #     "universityAddress": str,
    #     "collegeContact": str,
    #     "collegeEmail": str,
    #     "collegeAddress": str
    # }
    
    # Verification results (added after verification)
    verificationResults: Optional[Dict[str, Any]] = None
    # {
    #     "aadhaar": {"status": "verified/failed", "details": {...}},
    #     "pan": {"status": "verified/failed", "details": {...}},
    #     "address": {"status": "verified/failed", "details": {...}},
    #     ...
    # }


# MongoDB Collection Name
COLLECTION_NAME = "candidates"

# Indexes (for reference - should be created in MongoDB)
INDEXES = [
    {"email": 1},           # Unique index on email
    {"panNumber": 1},       # Unique index on PAN
    {"aadhaarNumber": 1},   # Unique index on Aadhaar
    {"organizationId": 1},  # Index for filtering by organization
    {"status": 1},          # Index for filtering by status
    {"createdAt": -1}       # Index for sorting by creation date
]
