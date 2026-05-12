"""
Pydantic schemas for Job Seeker Portal
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


# ============================================
# Authentication Schemas
# ============================================

class JobSeekerRegisterRequest(BaseModel):
    """Job seeker registration request"""
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    phone: str = Field(..., min_length=10, max_length=15)
    password: str = Field(..., min_length=8, max_length=100)


class JobSeekerLoginRequest(BaseModel):
    """Job seeker login request"""
    email: EmailStr
    password: str


class JobSeekerAuthResponse(BaseModel):
    """Job seeker authentication response"""
    message: str
    token: str
    jobSeeker: Dict[str, Any]


# ============================================
# Profile Schemas
# ============================================

class ExperienceEntry(BaseModel):
    """Work experience entry"""
    company: str
    role: str
    duration: str
    description: Optional[str] = None


class EducationEntry(BaseModel):
    """Education entry"""
    institution: str
    degree: str
    year: str


class ProfileUpdateRequest(BaseModel):
    """Profile update request"""
    name: Optional[str] = None
    phone: Optional[str] = None
    bio: Optional[str] = None
    location: Optional[str] = None
    linkedinUrl: Optional[str] = None
    githubUrl: Optional[str] = None
    experience: Optional[List[ExperienceEntry]] = None
    education: Optional[List[EducationEntry]] = None
    skills: Optional[List[str]] = None


class ProfileResponse(BaseModel):
    """Profile response"""
    _id: str
    name: str
    email: str
    phone: str
    resumeUrl: Optional[str] = None
    profileJson: Dict[str, Any]
    savedJobs: List[str]
    profileCompletion: int
    createdAt: str
    updatedAt: str


# ============================================
# Job Schemas
# ============================================

class JobBrowseQuery(BaseModel):
    """Query parameters for browsing jobs"""
    search: Optional[str] = None
    type: Optional[str] = None
    experience: Optional[str] = None
    location: Optional[str] = None
    salary: Optional[str] = None
    page: int = 1
    limit: int = 20


class SaveJobRequest(BaseModel):
    """Save/unsave job request"""
    jobId: str


class ApplyJobRequest(BaseModel):
    """Apply to job request"""
    jobId: str


class ApplicationResponse(BaseModel):
    """Application response"""
    _id: str
    jobSeekerId: str
    jobId: str
    orgId: str
    candidateName: str
    candidateEmail: str
    candidatePhone: str
    resumeUrl: str
    stage: str
    appliedAt: str
    updatedAt: str
    jobDetails: Optional[Dict[str, Any]] = None

