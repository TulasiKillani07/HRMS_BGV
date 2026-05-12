"""
Pydantic schemas for Interviewer Management
"""
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional


class InterviewerCreate(BaseModel):
    """Schema for creating interviewer"""
    name: str = Field(..., min_length=1, max_length=100, description="Interviewer full name")
    email: EmailStr = Field(..., description="Interviewer email address")
    phone: str = Field(..., min_length=10, max_length=15, description="Interviewer phone number")
    designation: str = Field(..., min_length=1, max_length=100, description="Job designation/title")
    department: str = Field(..., min_length=1, max_length=100, description="Department")
    expertise: List[str] = Field(default=[], description="List of technical expertise/skills")
    roundPreferences: List[int] = Field(
        default=[],
        description="Preferred interview rounds (1-4)"
    )
    availabilityNotes: Optional[str] = Field(
        None,
        max_length=500,
        description="Availability notes (e.g., 'Available Mon-Fri, 10 AM - 5 PM')"
    )


class InterviewerUpdate(BaseModel):
    """Schema for updating interviewer"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone: Optional[str] = Field(None, min_length=10, max_length=15)
    designation: Optional[str] = Field(None, min_length=1, max_length=100)
    department: Optional[str] = Field(None, min_length=1, max_length=100)
    expertise: Optional[List[str]] = None
    roundPreferences: Optional[List[int]] = None
    isAvailable: Optional[bool] = Field(None, description="Is interviewer currently available")
    availabilityNotes: Optional[str] = Field(None, max_length=500)


class InterviewerStats(BaseModel):
    """Schema for interviewer statistics"""
    totalInterviewsConducted: int = 0
    upcomingInterviews: int = 0
    averageRating: Optional[float] = None
    passRate: Optional[float] = None


class InterviewerResponse(BaseModel):
    """Schema for interviewer response"""
    interviewerId: str
    name: str
    email: str
    phone: str
    designation: str
    department: str
    organizationId: str
    organizationName: str
    expertise: List[str]
    roundPreferences: List[int]
    isActive: bool
    isAvailable: bool
    availabilityNotes: Optional[str]
    stats: InterviewerStats
    createdAt: str
    updatedAt: str


class InterviewerListResponse(BaseModel):
    """Schema for list of interviewers"""
    interviewers: List[InterviewerResponse]
    total: int


class InterviewerDelete(BaseModel):
    """Schema for deleting interviewer"""
    interviewerId: str = Field(..., description="Interviewer ID to delete")
