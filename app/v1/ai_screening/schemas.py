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


class AddFromScreeningRequest(BaseModel):
    """Schema for adding candidate/jobseeker from AI screening"""
    firstName: Optional[str] = Field(None, description="First name extracted from resume")
    lastName: Optional[str] = Field(None, description="Last name extracted from resume")
    email: Optional[str] = Field(None, description="Email address from AI screening")
    phone: Optional[str] = Field(None, description="Phone number from AI screening")
    resumeUrl: Optional[str] = Field(None, description="Resume URL from Cloudinary")
    resumeFilename: Optional[str] = Field(None, description="Original resume filename")
    jobId: Optional[str] = Field(None, description="Job ID - required when addAs='jobseeker'")
    organizationId: Optional[str] = Field(None, description="Organization ID - required for SUPER_ADMIN roles")
    addAs: str = Field(..., description="Where to add: 'candidate' (direct BGV) or 'jobseeker' (hiring pipeline)")
    
    # AI Screening Results (optional but recommended)
    finalScore: Optional[float] = Field(None, description="Final AI score (0-100)")
    embeddingScore: Optional[float] = Field(None, description="Embedding similarity score")
    llmScore: Optional[int] = Field(None, description="LLM match score")
    recommendation: Optional[str] = Field(None, description="AI recommendation (STRONG_FIT, GOOD_FIT, etc.)")
    strengths: Optional[List[str]] = Field(None, description="List of candidate strengths")
    weaknesses: Optional[List[str]] = Field(None, description="List of candidate weaknesses")
    summary: Optional[str] = Field(None, description="AI-generated candidate summary")
    explanation: Optional[str] = Field(None, description="AI explanation for ranking")
    meetsCriticalRequirements: Optional[bool] = Field(None, description="Whether candidate meets critical requirements")
    
    class Config:
        json_schema_extra = {
            "example": {
                "firstName": "Arjun",
                "lastName": "Kumar",
                "email": "arjun@example.com",
                "phone": "9876543210",
                "resumeUrl": "https://res.cloudinary.com/...",
                "resumeFilename": "arjun_kumar_resume.pdf",
                "jobId": "6a0028c89d57fa3ca6a76444",
                "addAs": "jobseeker",
                "finalScore": 85.5,
                "embeddingScore": 0.82,
                "llmScore": 87,
                "recommendation": "STRONG_FIT",
                "strengths": ["Strong Python skills", "FastAPI experience"],
                "weaknesses": ["Limited Kubernetes experience"],
                "summary": "Excellent backend developer with strong Python skills",
                "explanation": "Top candidate based on technical skills match",
                "meetsCriticalRequirements": True
            }
        }


class AddFromScreeningResponse(BaseModel):
    """Schema for add from screening response"""
    message: str
    addedAs: str
    id: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    applicationId: Optional[str] = Field(None, description="Application ID if added as jobseeker")
    nextStep: str
