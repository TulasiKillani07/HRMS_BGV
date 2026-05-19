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
    interviewMode: Optional[str] = Field(None, pattern="^(online|offline)$")
    interviewLink: Optional[str] = None
    interviewAddress: Optional[str] = None
    additionalNotes: Optional[str] = None
    rating: Optional[int] = Field(None, ge=1, le=5)
    feedback: str = ""
    completedAt: Optional[datetime] = None
    updatedBy: Optional[str] = None
    updatedAt: Optional[datetime] = None


class InterviewResponse(BaseModel):
    """Schema for interview response"""
    interviewId: str = Field(..., description="Interview ID (MongoDB _id)")
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
    interviewMode: str = Field(..., pattern="^(online|offline)$", description="Interview mode: online or offline")
    interviewLink: Optional[str] = Field(None, description="Meeting link for online interviews")
    interviewAddress: Optional[str] = Field(None, description="Office address for offline interviews")
    additionalNotes: Optional[str] = Field(None, description="Additional instructions for the interview")


class RescheduleRoundRequest(BaseModel):
    """Schema for rescheduling a round"""
    interviewId: str
    roundNumber: int = Field(..., ge=1, le=4)
    interviewerId: Optional[str] = Field(None, description="New interviewer ID (optional - keeps existing if not provided)")
    scheduledAt: Optional[datetime] = Field(None, description="New scheduled date/time (optional - keeps existing if not provided)")
    interviewMode: Optional[str] = Field(None, pattern="^(online|offline)$", description="New interview mode (optional)")
    interviewLink: Optional[str] = Field(None, description="New meeting link (optional)")
    interviewAddress: Optional[str] = Field(None, description="New office address (optional)")
    additionalNotes: Optional[str] = Field(None, description="New additional instructions (optional)")


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
