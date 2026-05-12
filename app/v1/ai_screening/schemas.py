"""
Pydantic schemas for AI Screening
"""
from pydantic import BaseModel, Field
from typing import List, Optional


class AIScreeningRequest(BaseModel):
    """Schema for AI screening request"""
    jobId: str = Field(..., description="Job ID to screen applications for")
    applicationIds: Optional[List[str]] = Field(
        None,
        description="Optional: Specific application IDs to screen. If not provided, screens all applications"
    )
    minScorePercentage: Optional[float] = Field(
        None,
        ge=0,
        le=100,
        description="Optional: Minimum score percentage (0-100). Only returns candidates with this score or higher"
    )
    topN: Optional[int] = Field(
        None,
        ge=1,
        le=100,
        description="Optional: Maximum number of top candidates to return (1-100). If not provided, returns all candidates above minScorePercentage"
    )


class AIScreeningResult(BaseModel):
    """Schema for single candidate AI screening result"""
    applicationId: str
    jobSeekerId: str
    jobSeekerName: str = Field(default="Unknown")
    jobSeekerEmail: str = Field(default="unknown@example.com")
    rank: int
    finalScore: float
    embeddingScore: float
    llmScore: Optional[int] = None
    recommendation: str
    strengths: List[str]
    weaknesses: List[str]
    explanation: str
    summary: str
    meetsCriticalRequirements: bool
    resumeUrl: str


class FailedApplication(BaseModel):
    """Schema for failed application"""
    applicationId: str
    jobSeekerName: Optional[str] = None
    reason: str


class AIScreeningResponse(BaseModel):
    """Schema for AI screening response"""
    message: str
    jobId: str
    jobTitle: str
    totalApplications: int
    totalProcessed: int
    totalFailed: Optional[int] = None
    failedApplications: Optional[List[FailedApplication]] = None
    filteredByScore: Optional[int] = None
    minScorePercentage: Optional[float] = None
    topN: Optional[int] = None
    results: List[AIScreeningResult]
    processingTime: float
