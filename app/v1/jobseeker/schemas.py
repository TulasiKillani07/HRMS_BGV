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
    # Required fields
    name: str = Field(..., min_length=2, max_length=100, example="Arjun Kumar")
    email: EmailStr = Field(..., example="arjun@gmail.com")
    phone: str = Field(..., pattern=r"^\d{10}$", description="10-digit phone number", example="9876543210")
    password: str = Field(..., min_length=6, max_length=100, example="SecurePass123")
    
    # Required personal details
    dob: str = Field(..., example="1995-05-15", description="Date of birth (YYYY-MM-DD)")
    gender: str = Field(..., example="Male", description="Male/Female/Other")
    maritalStatus: str = Field(..., example="Single", description="Single/Married/Divorced/Widowed")
    fatherName: str = Field(..., min_length=2, example="Rajesh Kumar")
    
    # Required address
    permanentAddress: str = Field(..., min_length=10, example="123 MG Road, Bangalore, Karnataka - 560001")
    district: str = Field(..., min_length=2, example="Bangalore Urban")
    state: str = Field(..., min_length=2, example="Karnataka")
    pincode: str = Field(..., pattern=r"^\d{6}$", description="6-digit PIN code", example="560001")
    
    # Optional personal details
    nationality: Optional[str] = Field(None, example="Indian")
    motherName: Optional[str] = Field(None, example="Priya Kumar")
    
    # Optional address
    currentAddress: Optional[str] = Field(None, example="456 HSR Layout, Bangalore, Karnataka - 560102")
    
    # Optional identity documents
    panNumber: Optional[str] = Field(None, pattern=r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$", description="PAN format: ABCDE1234F", example="ABCDE1234F")
    aadhaarNumber: Optional[str] = Field(None, pattern=r"^\d{12}$", description="12-digit Aadhaar number", example="123456789012")
    passportNumber: Optional[str] = Field(None, example="A1234567")
    drivingLicense: Optional[str] = Field(None, example="KA01-20230001234")
    
    # Optional profile
    location: Optional[str] = Field(None, example="Bangalore, India")
    linkedinUrl: Optional[str] = Field(None, example="https://linkedin.com/in/arjunkumar")
    githubUrl: Optional[str] = Field(None, example="https://github.com/arjunkumar")
    bio: Optional[str] = Field(None, example="Full-stack developer with 5 years of experience in Python and React")
    skills: List[str] = Field(default=[], example=["Python", "JavaScript", "React", "Node.js", "MongoDB"])
    
    # Optional nested arrays
    education: List[Dict] = Field(
        default=[],
        example=[
            {
                "degree": "B.Tech Computer Science",
                "institution": "IIT Bangalore",
                "year": "2017",
                "grade": "8.5 CGPA",
                "eduType": "Full-time"
            }
        ]
    )
    experience: List[Dict] = Field(
        default=[],
        example=[
            {
                "company": "Tech Corp",
                "role": "Senior Developer",
                "duration": "2020-2024",
                "description": "Led development of microservices architecture"
            }
        ]
    )
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "name": "Minimal Registration",
                    "summary": "Required fields only",
                    "value": {
                        "name": "John Doe",
                        "email": "john@example.com",
                        "phone": "9876543210",
                        "password": "SecurePass123",
                        "dob": "1995-05-15",
                        "gender": "Male",
                        "maritalStatus": "Single",
                        "fatherName": "Robert Doe",
                        "permanentAddress": "123 Main Street, City, State - 560001",
                        "district": "City District",
                        "state": "State Name",
                        "pincode": "560001"
                    }
                },
                {
                    "name": "Full Registration",
                    "summary": "All fields included",
                    "value": {
                        "name": "Arjun Kumar",
                        "email": "arjun@gmail.com",
                        "phone": "9876543210",
                        "password": "SecurePass123",
                        "dob": "1995-05-15",
                        "gender": "Male",
                        "maritalStatus": "Single",
                        "fatherName": "Rajesh Kumar",
                        "permanentAddress": "123 MG Road, Bangalore, Karnataka - 560001",
                        "district": "Bangalore Urban",
                        "state": "Karnataka",
                        "pincode": "560001",
                        "nationality": "Indian",
                        "motherName": "Priya Kumar",
                        "currentAddress": "456 HSR Layout, Bangalore, Karnataka - 560102",
                        "panNumber": "ABCDE1234F",
                        "aadhaarNumber": "123456789012",
                        "passportNumber": "A1234567",
                        "drivingLicense": "KA01-20230001234",
                        "location": "Bangalore, India",
                        "linkedinUrl": "https://linkedin.com/in/arjunkumar",
                        "githubUrl": "https://github.com/arjunkumar",
                        "bio": "Full-stack developer with 5 years of experience",
                        "skills": ["Python", "JavaScript", "React", "Node.js", "MongoDB"],
                        "education": [
                            {
                                "degree": "B.Tech Computer Science",
                                "institution": "IIT Bangalore",
                                "year": "2017",
                                "grade": "8.5 CGPA",
                                "eduType": "Full-time"
                            }
                        ],
                        "experience": [
                            {
                                "company": "Tech Corp",
                                "role": "Senior Developer",
                                "duration": "2020-2024",
                                "description": "Led development of microservices architecture"
                            }
                        ]
                    }
                }
            ]
        }


class JobSeekerLoginRequest(BaseModel):
    """Job seeker login request"""
    email: EmailStr = Field(..., example="arjun@gmail.com")
    password: str = Field(..., example="SecurePass123")


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
    grade: Optional[str] = None
    eduType: Optional[str] = None  # Full-time / Part-time / Distance


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

