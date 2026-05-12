"""
Pydantic schemas for Interview Management
"""
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
from datetime import datetime


class RoundDetails(BaseModel):
    """Schema for interview round details"""
    roundNumber: int = Field(..., ge=1, le=4)
    roundName: str
    interviewerId: Optional[str] = None
    interviewer: Optional[str] = None
    interviewerEmail: Optional[EmailStr] = None
    scheduledAt: Optional[datetime] = None
    status: str = Field(default="Pending", pattern="^(Pending|Scheduled|Passed|Failed)$")
    rating: Optional[int] = Field(None, ge=1, le=5)
    feedback: str = ""
    completedAt: Optional[datetime] = None
    updatedBy: Optional[str] = None
    updatedAt: Optional[datetime] = None


class InterviewResponse(BaseModel):
    """Schema for interview response"""
    _id: str
    applicationId: str
    jobSeekerId: str
    jobId: str
    orgId: str
    
    # Job seeker details (enriched from job_seekers collection)
    jobSeekerName: Optional[str] = None
    jobSeekerEmail: Optional[str] = None
    jobSeekerPhone: Optional[str] = None
    resumeUrl: Optional[str] = None
    profileCompletion: Optional[int] = None
    
    rounds: List[RoundDetails]
    currentRound: int
    overallStatus: str
    offerExtended: bool
    offerExtendedAt: Optional[datetime] = None
    offerExtendedBy: Optional[str] = None
    rejected: bool
    rejectedAt: Optional[datetime] = None
    rejectedBy: Optional[str] = None
    rejectionReason: str = ""
    rejectedAtRound: Optional[int] = None
    hired: bool
    hiredAt: Optional[datetime] = None
    hiredBy: Optional[str] = None
    bgvInitiated: bool
    bgvInitiatedAt: Optional[datetime] = None
    bgvInitiatedBy: Optional[str] = None
    candidateId: Optional[str] = None
    createdAt: datetime
    createdBy: str
    updatedAt: datetime
    isDeleted: bool


class CreateInterviewRequest(BaseModel):
    """Schema for creating interview"""
    applicationId: str


class ScheduleRoundRequest(BaseModel):
    """Schema for scheduling a round"""
    interviewId: str
    roundNumber: int = Field(..., ge=1, le=4)
    interviewerId: str = Field(..., description="Interviewer ID from interviewers collection")
    scheduledAt: datetime


class UpdateRoundRequest(BaseModel):
    """Schema for updating round status"""
    interviewId: str
    roundNumber: int = Field(..., ge=1, le=4)
    status: str = Field(..., pattern="^(Passed|Failed)$")
    rating: int = Field(..., ge=1, le=5)
    feedback: str = ""


class ExtendOfferRequest(BaseModel):
    """Schema for extending offer"""
    interviewId: str


class RejectCandidateRequest(BaseModel):
    """Schema for rejecting candidate"""
    interviewId: str
    reason: str = Field(..., min_length=1)
    rejectedAtRound: Optional[int] = Field(None, ge=1, le=4)


class MarkAsHiredRequest(BaseModel):
    """Schema for marking as hired"""
    interviewId: str


class InitiateBGVRequest(BaseModel):
    """Schema for initiating BGV"""
    interviewId: str


class InterviewListResponse(BaseModel):
    """Schema for list of interviews"""
    interviews: List[InterviewResponse]
    total: int
