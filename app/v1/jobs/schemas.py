"""
Pydantic schemas for Jobs ATS feature
Used for request/response validation
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class JobCreate(BaseModel):
    """Schema for creating a new job"""
    title: str = Field(..., min_length=1, max_length=200)
    department: str = Field(..., min_length=1, max_length=100)
    location: str = Field(..., min_length=1, max_length=200)
    type: str = Field(..., pattern="^(Full-time|Part-time|Contract|Internship)$")
    experience: str = Field(..., min_length=1, max_length=100)
    salary: str = Field(..., min_length=1, max_length=100, description="Salary range in INR (e.g., ₹18,00,000 - ₹24,00,000 per annum)")
    skills: str = Field(..., description="Comma-separated skills")
    description: str = Field(..., min_length=1)
    status: str = Field(default="open", pattern="^(open|closed|draft)$")
    deadline: Optional[str] = None  # ISO date string


class JobUpdate(BaseModel):
    """Schema for updating a job"""
    jobId: str
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    department: Optional[str] = Field(None, min_length=1, max_length=100)
    location: Optional[str] = Field(None, min_length=1, max_length=200)
    type: Optional[str] = Field(None, pattern="^(Full-time|Part-time|Contract|Internship)$")
    experience: Optional[str] = Field(None, min_length=1, max_length=100)
    salary: Optional[str] = Field(None, min_length=1, max_length=100, description="Salary range in INR (e.g., ₹18,00,000 - ₹24,00,000 per annum)")
    skills: Optional[str] = Field(None, description="Comma-separated skills")
    description: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(open|closed|draft)$")
    deadline: Optional[str] = None


class JobResponse(BaseModel):
    """Schema for job response"""
    _id: str
    orgId: str
    orgName: str
    title: str
    department: str
    location: str
    type: str
    experience: str
    salary: str
    skills: List[str]
    description: str
    status: str
    deadline: Optional[datetime] = None
    applicantCount: int
    shortlistedCount: int
    hiredCount: int
    createdBy: str
    createdAt: datetime
    updatedAt: datetime
    isDeleted: bool = False


class JobListResponse(BaseModel):
    """Schema for list of jobs"""
    jobs: List[JobResponse]
    total: int


class JobDeleteRequest(BaseModel):
    """Schema for deleting a job"""
    jobId: str


class JobActionRequest(BaseModel):
    """Schema for job actions (close, reopen, duplicate)"""
    jobId: str


class ParseJDResponse(BaseModel):
    """Schema for parsed job description response"""
    title: str
    department: str
    location: str
    type: str
    experience: str
    salary: str
    skills: List[str]
    description: str
    deadline: Optional[str] = None
    error: Optional[str] = None
