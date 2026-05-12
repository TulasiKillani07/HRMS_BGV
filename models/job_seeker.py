"""
MongoDB Document Model for Job Seekers Collection
This file documents the structure of job seeker accounts in MongoDB
"""
from typing import Optional, List, Dict, Any
from datetime import datetime


class JobSeekerDocument:
    """
    MongoDB document structure for job_seekers collection
    
    This is a reference model showing what fields exist in the database.
    Not used for validation (Pydantic schemas handle that).
    """
    
    # Required fields
    _id: str                          # MongoDB ObjectId (auto-generated)
    name: str                         # Full name
    email: str                        # Email (unique)
    phone: str                        # Phone number
    passwordHash: str                 # Bcrypt hashed password (NEVER return in responses)
    
    # Profile fields
    resumeUrl: Optional[str] = None   # S3 URL to resume
    profileJson: Dict[str, Any] = {}  # Structured profile data
    # {
    #   "experience": [
    #     {
    #       "company": "TechCorp",
    #       "role": "Software Engineer",
    #       "duration": "2020-2023",
    #       "description": "Built scalable APIs"
    #     }
    #   ],
    #   "education": [
    #     {
    #       "institution": "MIT",
    #       "degree": "B.Tech Computer Science",
    #       "year": "2020"
    #     }
    #   ],
    #   "skills": ["Python", "FastAPI", "React", "AWS"],
    #   "bio": "Passionate software engineer...",
    #   "location": "Hyderabad, India",
    #   "linkedinUrl": "https://linkedin.com/in/...",
    #   "githubUrl": "https://github.com/..."
    # }
    
    # Saved jobs
    savedJobs: List[str] = []         # Array of job IDs (bookmarked jobs)
    
    # Profile completion
    profileCompletion: int = 0        # Percentage (0-100)
    
    # Metadata
    createdAt: datetime
    updatedAt: datetime
    isActive: bool = True             # Account status


class JobSeekerApplicationDocument:
    """
    MongoDB document structure for jobseeker_applications collection
    
    Stores applications made by job seekers to jobs.
    This is separate from the org's internal applications collection.
    """
    
    # Required fields
    _id: str                          # MongoDB ObjectId (auto-generated)
    jobSeekerId: str                  # Reference to job_seekers collection
    jobId: str                        # Reference to jobs collection
    orgId: str                        # Reference to organizations collection
    
    # Snapshot of job seeker data at time of application
    candidateName: str
    candidateEmail: str
    candidatePhone: str
    resumeUrl: str
    
    # Application details
    stage: str                        # Current stage in pipeline
    # Stages: Applied → Screening → HR Round → Tech Round → Manager Round → Offer → Hired / Rejected
    
    # Metadata
    appliedAt: datetime
    updatedAt: datetime


# MongoDB Collection Names
JOB_SEEKERS_COLLECTION = "job_seekers"
JOBSEEKER_APPLICATIONS_COLLECTION = "jobseeker_applications"

# Indexes (for reference - should be created in MongoDB)
JOB_SEEKERS_INDEXES = [
    {"email": 1},                     # Unique index for login
    {"createdAt": -1}                 # Sort by registration date
]

JOBSEEKER_APPLICATIONS_INDEXES = [
    {"jobSeekerId": 1},               # Filter by job seeker
    {"jobId": 1},                     # Filter by job
    {"orgId": 1},                     # Filter by organization
    {"stage": 1},                     # Filter by stage
    {"appliedAt": -1},                # Sort by application date
    {"jobSeekerId": 1, "jobId": 1}    # Prevent duplicate applications (unique)
]

# Valid values
VALID_APPLICATION_STAGES = [
    "Applied",
    "Screening",
    "HR Round",
    "Tech Round",
    "Manager Round",
    "Offer",
    "Hired",
    "Rejected"
]

# Profile completion calculation
# Each filled field contributes to completion percentage:
# - name: 10%
# - email: 10%
# - phone: 10%
# - resumeUrl: 20%
# - at least 1 experience: 20%
# - at least 1 education: 15%
# - at least 3 skills: 15%
# Total: 100%

