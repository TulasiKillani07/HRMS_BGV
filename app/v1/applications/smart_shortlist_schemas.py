"""
Pydantic schemas for Smart Shortlisting
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Literal


class SmartShortlistRequest(BaseModel):
    """Schema for smart shortlist request"""
    jobId: str = Field(..., description="Job ID")
    criteriaType: Literal["percentage", "number"] = Field(
        ..., 
        description="Criteria type: 'percentage' for top X%, 'number' for top N"
    )
    criteriaValue: float = Field(
        ..., 
        ge=1,
        description="Value: percentage (1-100) or number of applications (1+)"
    )
    previewOnly: bool = Field(
        default=False,
        description="If true, only returns preview without updating. If false, updates applications."
    )
    manualAdjustments: Optional[List[str]] = Field(
        default=None,
        description="Optional: List of application IDs to manually include/exclude from shortlist"
    )


class ShortlistPreviewItem(BaseModel):
    """Schema for single application in preview"""
    applicationId: str
    jobSeekerId: str
    jobSeekerName: str
    jobSeekerEmail: str
    aiScore: Optional[float] = None
    profileCompletion: int
    sortScore: float
    currentStage: str
    willBeShortlisted: bool


class SmartShortlistResponse(BaseModel):
    """Schema for smart shortlist response"""
    message: str
    jobId: str
    criteriaType: str
    criteriaValue: float
    totalApplications: int
    applicationsToShortlist: int
    preview: List[ShortlistPreviewItem]
    updated: bool
    updatedCount: Optional[int] = None
