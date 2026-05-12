"""
Pydantic schemas for Applications ATS feature
Used for request/response validation
"""
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime


class ApplicationCreate(BaseModel):
    """Schema for creating a new application"""
    jobId: str
    candidateId: str
    source: str = Field(..., pattern="^(AI_SCREENING|JOB_PORTAL|MANUAL)$")
    stage: str = Field(default="Applied")
    aiScore: Optional[float] = Field(None, ge=0, le=100)
    notes: str = ""


class ApplicationUpdateStage(BaseModel):
    """Schema for updating application stage"""
    applicationId: str
    stage: str = Field(..., pattern="^(Applied|Resume Shortlist|Interview)$")
    notes: Optional[str] = ""


class BulkUpdateStage(BaseModel):
    """Schema for bulk updating application stages"""
    applicationIds: List[str]
    stage: str = Field(..., pattern="^(Applied|Resume Shortlist|Interview)$")
    notes: Optional[str] = ""


class ApplicationAddNote(BaseModel):
    """Schema for adding note to application"""
    applicationId: str
    note: str = Field(..., min_length=1)


class ApplicationDelete(BaseModel):
    """Schema for deleting application"""
    applicationId: str


class StageHistoryItem(BaseModel):
    """Schema for stage history entry"""
    stage: str
    changedBy: str
    changedAt: datetime
    notes: str


class ApplicationResponse(BaseModel):
    """Schema for application response"""
    _id: str
    jobId: str
    orgId: str
    candidateId: Optional[str] = None  # For HR-added candidates
    jobSeekerId: Optional[str] = None  # For job portal applications
    candidateName: Optional[str] = None  # Snapshot for HR-added
    candidateEmail: Optional[str] = None  # Snapshot for HR-added
    candidatePhone: Optional[str] = None  # Snapshot for HR-added
    resumeUrl: Optional[str] = None  # Snapshot for HR-added
    candidateProfile: Optional[Dict[str, Any]] = None  # Live profile for job portal
    stage: str
    source: str
    aiScore: Optional[float] = None
    notes: str
    stageHistory: List[StageHistoryItem]
    appliedAt: datetime
    updatedAt: datetime
    isDeleted: bool = False


class ApplicationListResponse(BaseModel):
    """Schema for list of applications"""
    applications: List[ApplicationResponse]
    total: int
    stageCounts: Dict[str, int]  # Count per stage


# Removed: CreateApplicationFromCandidate schema

