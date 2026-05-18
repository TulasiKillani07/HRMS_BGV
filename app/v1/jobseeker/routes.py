"""
API routes for Job Seeker Portal
Uses Cookie authentication (same as organization authentication)
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Request, Response
from fastapi.responses import JSONResponse
from typing import Optional
import os
import json
import hmac
import hashlib
import base64
import time

# Import schemas
from .schemas import (
    JobSeekerRegisterRequest,
    JobSeekerLoginRequest,
    ProfileUpdateRequest,
    SaveJobRequest,
    ApplyJobRequest
)

# Import service
from .service import JobSeekerService

# Import S3 upload utility from main
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

# Import from core
from core.database import jobSeekersCol

# Initialize router
router = APIRouter(
    prefix="/jobseeker",
    tags=["Job Seeker Portal"],
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Access denied"},
        404: {"description": "Resource not found"},
        500: {"description": "Internal server error"}
    }
)

# Initialize service
service = JobSeekerService()

# ============================================
# JWT Configuration for Job Seekers
# ============================================

JOBSEEKER_JWT_SECRET = os.getenv("JOBSEEKER_JWT_SECRET", b"jobseeker-secret-key")
if isinstance(JOBSEEKER_JWT_SECRET, str):
    JOBSEEKER_JWT_SECRET = JOBSEEKER_JWT_SECRET.encode()

COOKIE_NAME = "jobseekerSession"
COOKIE_MAX_AGE = 60 * 60 * 24 * 7  # 7 days

# Environment-based cookie settings
# For localhost: Secure=False, SameSite=lax
# For production: Secure=True, SameSite=none
IS_PRODUCTION = os.getenv("ENVIRONMENT", "development") == "production"
COOKIE_SECURE = IS_PRODUCTION  # True in production, False in development
COOKIE_SAMESITE = "none" if IS_PRODUCTION else "lax"  # "none" in production, "lax" in development


def encode_jobseeker_token(payload: dict) -> str:
    """Encode JWT token for job seeker"""
    body = json.dumps(payload, separators=(",", ":")).encode()
    sig = hmac.new(JOBSEEKER_JWT_SECRET, body, hashlib.sha256).digest()
    return f"{base64.urlsafe_b64encode(body).decode().rstrip('=')}.{base64.urlsafe_b64encode(sig).decode().rstrip('=')}"


def decode_jobseeker_token(token: str) -> dict:
    """Decode JWT token for job seeker"""
    try:
        bodyB64, sigB64 = token.split(".", 1)
        body = base64.urlsafe_b64decode(bodyB64 + "==")
        sig = base64.urlsafe_b64decode(sigB64 + "==")
        expected = hmac.new(JOBSEEKER_JWT_SECRET, body, hashlib.sha256).digest()
        if not hmac.compare_digest(sig, expected):
            raise ValueError("bad signature")
        data = json.loads(body.decode())
        if data.get("exp", 0) < int(time.time()):
            raise ValueError("expired")
        return data
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


async def require_jobseeker_auth(request: Request):
    """
    Middleware to require job seeker authentication
    Uses cookie (with Authorization header fallback for Postman)
    """
    token = request.cookies.get(COOKIE_NAME)
    
    # Fallback for Postman / mobile clients
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split("Bearer ")[1].strip()
    
    if not token:
        raise HTTPException(status_code=401, detail="No session cookie")
    
    # Decode and verify token
    data = decode_jobseeker_token(token)
    
    # Verify role is JOBSEEKER
    if data.get("role") != "JOBSEEKER":
        raise HTTPException(status_code=403, detail="Access denied: Invalid role")
    
    # Get job seeker from database
    from bson import ObjectId
    job_seeker = await jobSeekersCol.find_one({
        "_id": ObjectId(data["jobSeekerId"]),
        "isActive": True
    })
    
    if not job_seeker:
        raise HTTPException(status_code=401, detail="Job seeker not found")
    
    # Convert ObjectId to string
    job_seeker["_id"] = str(job_seeker["_id"])
    
    # Remove password
    if "password" in job_seeker:
        del job_seeker["password"]
    
    return job_seeker


# ============================================
# Authentication Routes (Public)
# ============================================

@router.post(
    "/register",
    status_code=201,
    summary="Register New Job Seeker",
    description="""
    Register a new job seeker with comprehensive profile information.
    
    **Required Fields:**
    - name (min 2 chars)
    - email (valid email, unique)
    - phone (exactly 10 digits, unique)
    - password (min 6 chars)
    - dob (date of birth)
    - gender (Male/Female/Other)
    - maritalStatus (Single/Married/Divorced/Widowed)
    - fatherName (min 2 chars)
    - permanentAddress (min 10 chars)
    - district (min 2 chars)
    - state (min 2 chars)
    - pincode (exactly 6 digits)
    
    **Optional Personal Details:**
    - nationality, motherName
    
    **Optional Address:**
    - currentAddress
    
    **Optional Identity Documents:**
    - panNumber (format: ABCDE1234F)
    - aadhaarNumber (12 digits)
    - passportNumber, drivingLicense
    
    **Optional Profile:**
    - location, linkedinUrl, githubUrl, bio, skills
    - education (array), experience (array)
    
    **Returns:**
    - JWT token (in response body AND cookie)
    - Job seeker profile with profileCompletion percentage
    
    **Profile Completion Calculation:**
    Based on 10 fields (each 10%): name, email, phone, dob, gender, location, bio, skills, education, resumeUrl
    """,
    responses={
        201: {
            "description": "Registration successful",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Registration successful",
                        "token": "eyJqb2JTZWVrZXJJZCI6IjY5MjJhYWVhZGM0Mzk4NjkwMmVkNzE2OSIsImVtYWlsIjoiYXJqdW5AZ21haWwuY29tIiwicm9sZSI6IkpPQlNFRUtFUiIsImlhdCI6MTc3ODg1MzEzNCwiZXhwIjoxNzc5NDU3OTM0fQ",
                        "jobSeeker": {
                            "_id": "6922aaeadc43986902ed7169",
                            "name": "Arjun Kumar",
                            "email": "arjun@gmail.com",
                            "phone": "9876543210",
                            "profileCompletion": 85
                        }
                    }
                }
            }
        },
        409: {
            "description": "Duplicate email or phone",
            "content": {
                "application/json": {
                    "examples": {
                        "duplicate_email": {
                            "summary": "Email already registered",
                            "value": {"detail": "Email already registered"}
                        },
                        "duplicate_phone": {
                            "summary": "Phone already registered",
                            "value": {"detail": "Phone number already registered"}
                        }
                    }
                }
            }
        },
        422: {
            "description": "Validation error",
            "content": {
                "application/json": {
                    "examples": {
                        "invalid_email": {
                            "summary": "Invalid email format",
                            "value": {
                                "detail": [
                                    {
                                        "loc": ["body", "email"],
                                        "msg": "value is not a valid email address",
                                        "type": "value_error.email"
                                    }
                                ]
                            }
                        },
                        "invalid_phone": {
                            "summary": "Invalid phone format",
                            "value": {
                                "detail": [
                                    {
                                        "loc": ["body", "phone"],
                                        "msg": "string does not match regex \"^\\d{10}$\"",
                                        "type": "value_error.str.regex"
                                    }
                                ]
                            }
                        },
                        "invalid_pan": {
                            "summary": "Invalid PAN format",
                            "value": {
                                "detail": [
                                    {
                                        "loc": ["body", "panNumber"],
                                        "msg": "string does not match regex \"^[A-Z]{5}[0-9]{4}[A-Z]{1}$\"",
                                        "type": "value_error.str.regex"
                                    }
                                ]
                            }
                        }
                    }
                }
            }
        }
    }
)
async def register(body: JobSeekerRegisterRequest, response: Response):
    """
    Register a new job seeker
    
    Public endpoint - no authentication required
    Returns JWT token in response body AND sets cookie
    """
    try:
        # Register job seeker with all fields
        job_seeker = await service.register_job_seeker(
            name=body.name,
            email=body.email,
            phone=body.phone,
            password=body.password,
            # Required personal details
            dob=body.dob,
            gender=body.gender,
            marital_status=body.maritalStatus,
            father_name=body.fatherName,
            # Required address
            permanent_address=body.permanentAddress,
            district=body.district,
            state=body.state,
            pincode=body.pincode,
            # Optional personal details
            nationality=body.nationality,
            mother_name=body.motherName,
            # Optional address
            current_address=body.currentAddress,
            # Optional identity documents
            pan_number=body.panNumber,
            aadhaar_number=body.aadhaarNumber,
            passport_number=body.passportNumber,
            driving_license=body.drivingLicense,
            # Optional profile
            location=body.location,
            linkedin_url=body.linkedinUrl,
            github_url=body.githubUrl,
            bio=body.bio,
            skills=body.skills,
            education=body.education,
            experience=body.experience,
            resume_url=None
        )
        
        # Create JWT token
        now = int(time.time())
        payload = {
            "jobSeekerId": job_seeker["_id"],
            "email": job_seeker["email"],
            "role": "JOBSEEKER",
            "iat": now,
            "exp": now + COOKIE_MAX_AGE
        }
        token = encode_jobseeker_token(payload)
        
        # Set cookie
        response.set_cookie(
            key=COOKIE_NAME,
            value=token,
            httponly=True,
            secure=COOKIE_SECURE,
            samesite=COOKIE_SAMESITE,
            max_age=COOKIE_MAX_AGE,
            path="/"
        )
        
        # Return normal dict (NOT JSONResponse)
        return {
            "message": "Registration successful",
            "token": token,
            "jobSeeker": {
                "_id": job_seeker["_id"],
                "name": job_seeker["name"],
                "email": job_seeker["email"],
                "phone": job_seeker["phone"],
                "profileCompletion": job_seeker["profileCompletion"]
            }
        }
        
    except ValueError as e:
        error_msg = str(e)
        if "Email already registered" in error_msg:
            raise HTTPException(status_code=409, detail="Email already registered")
        elif "Phone number already registered" in error_msg:
            raise HTTPException(status_code=409, detail="Phone number already registered")
        else:
            raise HTTPException(status_code=400, detail=error_msg)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")


@router.post(
    "/login",
    summary="Login Job Seeker",
    description="""
    Authenticate job seeker with email and password.
    
    **Returns:**
    - JWT token (in response body AND cookie)
    - Job seeker profile information
    
    **Cookie:**
    - Name: `jobseekerSession`
    - Expiry: 7 days
    - HttpOnly: true
    """,
    responses={
        200: {
            "description": "Login successful",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Login successful",
                        "token": "eyJqb2JTZWVrZXJJZCI6IjY5MjJhYWVhZGM0Mzk4NjkwMmVkNzE2OSIsImVtYWlsIjoiYXJqdW5AZ21haWwuY29tIiwicm9sZSI6IkpPQlNFRUtFUiIsImlhdCI6MTc3ODg1MzEzNCwiZXhwIjoxNzc5NDU3OTM0fQ",
                        "jobSeeker": {
                            "_id": "6922aaeadc43986902ed7169",
                            "name": "Arjun Kumar",
                            "email": "arjun@gmail.com",
                            "phone": "9876543210",
                            "profileCompletion": 85
                        }
                    }
                }
            }
        },
        401: {
            "description": "Invalid credentials",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid email or password"}
                }
            }
        }
    }
)
async def login(body: JobSeekerLoginRequest, response: Response):
    """
    Login job seeker
    
    Public endpoint - no authentication required
    Returns JWT token in response body AND sets cookie
    """
    try:
        # Authenticate
        job_seeker = await service.login_job_seeker(
            email=body.email,
            password=body.password
        )
        
        if not job_seeker:
            raise HTTPException(status_code=401, detail="Invalid email or password")
        
        # Create JWT token
        now = int(time.time())
        payload = {
            "jobSeekerId": job_seeker["_id"],
            "email": job_seeker["email"],
            "role": "JOBSEEKER",
            "iat": now,
            "exp": now + COOKIE_MAX_AGE
        }
        token = encode_jobseeker_token(payload)
        
        # Set cookie
        response.set_cookie(
            key=COOKIE_NAME,
            value=token,
            httponly=True,
            secure=COOKIE_SECURE,
            samesite=COOKIE_SAMESITE,
            max_age=COOKIE_MAX_AGE,
            path="/"
        )
        
        # Return normal dict (NOT JSONResponse)
        return {
            "message": "Login successful",
            "token": token,
            "jobSeeker": {
                "_id": job_seeker["_id"],
                "name": job_seeker["name"],
                "email": job_seeker["email"],
                "phone": job_seeker["phone"],
                "profileCompletion": job_seeker["profileCompletion"]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")


# ============================================
# Profile Routes (Protected)
# ============================================

@router.get(
    "/profile",
    summary="Get Job Seeker Profile",
    description="""
    Get complete profile of authenticated job seeker.
    
    **Authentication:** Required (cookie or Bearer token)
    
    **Returns:**
    - Complete profile with all fields
    - Profile completion percentage
    - Saved jobs list
    """,
    responses={
        200: {
            "description": "Profile retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "profile": {
                            "_id": "6922aaeadc43986902ed7169",
                            "name": "Arjun Kumar",
                            "email": "arjun@gmail.com",
                            "phone": "9876543210",
                            "dob": "1995-05-15",
                            "gender": "Male",
                            "location": "Bangalore, India",
                            "bio": "Full-stack developer with 5 years of experience",
                            "skills": ["Python", "JavaScript", "React"],
                            "resumeUrl": "https://cloudinary.com/...",
                            "education": [
                                {
                                    "degree": "B.Tech Computer Science",
                                    "institution": "IIT Bangalore",
                                    "year": "2017"
                                }
                            ],
                            "experience": [
                                {
                                    "company": "Tech Corp",
                                    "role": "Senior Developer",
                                    "duration": "2020-2024"
                                }
                            ],
                            "savedJobs": ["jobId1", "jobId2"],
                            "profileCompletion": 85,
                            "createdAt": "2024-01-01T00:00:00Z",
                            "updatedAt": "2024-01-15T00:00:00Z"
                        }
                    }
                }
            }
        },
        401: {
            "description": "Not authenticated",
            "content": {
                "application/json": {
                    "example": {"detail": "No session cookie"}
                }
            }
        }
    }
)
async def get_profile(job_seeker: dict = Depends(require_jobseeker_auth)):
    """
    Get job seeker profile
    
    Protected endpoint - requires cookie authentication
    """
    try:
        profile = await service.get_profile(job_seeker["_id"])
        
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        
        # Convert datetime objects to ISO format strings
        if "createdAt" in profile and profile["createdAt"]:
            profile["createdAt"] = profile["createdAt"].isoformat()
        if "updatedAt" in profile and profile["updatedAt"]:
            profile["updatedAt"] = profile["updatedAt"].isoformat()
        
        return JSONResponse(
            status_code=200,
            content={"profile": profile}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch profile: {str(e)}")


@router.patch("/profile")
async def update_profile(
    body: ProfileUpdateRequest,
    job_seeker: dict = Depends(require_jobseeker_auth)
):
    """
    Update job seeker profile
    
    Protected endpoint - requires cookie authentication
    """
    try:
        # Convert Pydantic models to dict
        update_fields = body.dict(exclude_unset=True)
        
        # Convert nested models to dict
        if "experience" in update_fields:
            update_fields["experience"] = [exp.dict() for exp in body.experience] if body.experience else []
        if "education" in update_fields:
            update_fields["education"] = [edu.dict() for edu in body.education] if body.education else []
        
        updated_profile = await service.update_profile(
            job_seeker_id=job_seeker["_id"],
            update_fields=update_fields
        )
        
        if not updated_profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        
        # Convert datetime objects to ISO format strings
        if "createdAt" in updated_profile and updated_profile["createdAt"]:
            updated_profile["createdAt"] = updated_profile["createdAt"].isoformat()
        if "updatedAt" in updated_profile and updated_profile["updatedAt"]:
            updated_profile["updatedAt"] = updated_profile["updatedAt"].isoformat()
        
        return JSONResponse(
            status_code=200,
            content={
                "message": "Profile updated successfully",
                "profile": updated_profile
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update profile: {str(e)}")


@router.post("/uploadResume")
async def upload_resume(
    file: UploadFile = File(...),
    job_seeker: dict = Depends(require_jobseeker_auth)
):
    """
    Upload resume to S3
    
    Protected endpoint - requires cookie authentication
    """
    try:
        # Validate file type
        if not file.filename.endswith(('.pdf', '.doc', '.docx', '.zip')):
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Only PDF, DOC, DOCX, and ZIP are allowed"
            )
        
        # Read file content
        file_content = await file.read()
        
        # Upload to S3
        from main import upload_to_s3
        
        folder_path = f"job_seekers/{job_seeker['_id']}"
        s3_url = await upload_to_s3(
            file_content=file_content,
            file_name=file.filename,
            folder_path=folder_path
        )
        
        # Update job seeker profile
        success = await service.upload_resume(
            job_seeker_id=job_seeker["_id"],
            resume_url=s3_url
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update resume URL")
        
        return JSONResponse(
            status_code=200,
            content={
                "message": "Resume uploaded successfully",
                "resumeUrl": s3_url
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload resume: {str(e)}")


# ============================================
# Job Discovery Routes (Protected)
# ============================================

@router.get("/jobs")
async def browse_jobs(
    search: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    experience: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    salary: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    job_seeker: dict = Depends(require_jobseeker_auth)
):
    """
    Browse open jobs across all organizations
    
    Protected endpoint - requires cookie authentication
    """
    try:
        result = await service.browse_jobs(
            search=search,
            job_type=type,
            experience=experience,
            location=location,
            salary=salary,
            page=page,
            limit=limit
        )
        
        # Convert datetime objects to ISO format strings in jobs list
        for job in result.get("jobs", []):
            if "createdAt" in job and job["createdAt"]:
                job["createdAt"] = job["createdAt"].isoformat() if hasattr(job["createdAt"], 'isoformat') else job["createdAt"]
            if "updatedAt" in job and job["updatedAt"]:
                job["updatedAt"] = job["updatedAt"].isoformat() if hasattr(job["updatedAt"], 'isoformat') else job["updatedAt"]
            if "deadline" in job and job["deadline"]:
                job["deadline"] = job["deadline"].isoformat() if hasattr(job["deadline"], 'isoformat') else job["deadline"]
        
        return JSONResponse(
            status_code=200,
            content=result
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to browse jobs: {str(e)}")


@router.post("/saveJob")
async def save_job(
    body: SaveJobRequest,
    job_seeker: dict = Depends(require_jobseeker_auth)
):
    """
    Save/unsave a job
    
    Protected endpoint - requires cookie authentication
    """
    try:
        result = await service.save_job(
            job_seeker_id=job_seeker["_id"],
            job_id=body.jobId
        )
        
        return JSONResponse(
            status_code=200,
            content={
                "message": f"Job {result['action']} successfully",
                "action": result["action"],
                "savedJobs": result["savedJobs"]
            }
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save job: {str(e)}")


@router.get("/savedJobs")
async def get_saved_jobs(job_seeker: dict = Depends(require_jobseeker_auth)):
    """
    Get all saved jobs
    
    Protected endpoint - requires cookie authentication
    """
    try:
        jobs = await service.get_saved_jobs(job_seeker_id=job_seeker["_id"])
        
        # Convert datetime objects to ISO format strings
        for job in jobs:
            if "createdAt" in job and job["createdAt"]:
                job["createdAt"] = job["createdAt"].isoformat() if hasattr(job["createdAt"], 'isoformat') else job["createdAt"]
            if "updatedAt" in job and job["updatedAt"]:
                job["updatedAt"] = job["updatedAt"].isoformat() if hasattr(job["updatedAt"], 'isoformat') else job["updatedAt"]
            if "deadline" in job and job["deadline"]:
                job["deadline"] = job["deadline"].isoformat() if hasattr(job["deadline"], 'isoformat') else job["deadline"]
        
        return JSONResponse(
            status_code=200,
            content={
                "jobs": jobs,
                "total": len(jobs)
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch saved jobs: {str(e)}")


# ============================================
# Application Routes (Protected)
# ============================================

@router.post("/apply")
async def apply_to_job(
    body: ApplyJobRequest,
    job_seeker: dict = Depends(require_jobseeker_auth)
):
    """
    Apply to a job
    
    Protected endpoint - requires cookie authentication
    """
    try:
        application = await service.apply_to_job(
            job_seeker_id=job_seeker["_id"],
            job_id=body.jobId
        )
        
        # Convert datetime objects to ISO format strings
        if "appliedAt" in application and application["appliedAt"]:
            application["appliedAt"] = application["appliedAt"].isoformat() if hasattr(application["appliedAt"], 'isoformat') else application["appliedAt"]
        if "updatedAt" in application and application["updatedAt"]:
            application["updatedAt"] = application["updatedAt"].isoformat() if hasattr(application["updatedAt"], 'isoformat') else application["updatedAt"]
        if "deletedAt" in application and application["deletedAt"]:
            application["deletedAt"] = application["deletedAt"].isoformat() if hasattr(application["deletedAt"], 'isoformat') else application["deletedAt"]
        # Convert datetime in stageHistory
        if "stageHistory" in application:
            for history in application["stageHistory"]:
                if "changedAt" in history and history["changedAt"]:
                    history["changedAt"] = history["changedAt"].isoformat() if hasattr(history["changedAt"], 'isoformat') else history["changedAt"]
        
        return JSONResponse(
            status_code=201,
            content={
                "message": "Application submitted successfully",
                "application": application
            }
        )
        
    except ValueError as e:
        if "already applied" in str(e):
            raise HTTPException(status_code=409, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to apply: {str(e)}")


@router.get("/applications")
async def get_my_applications(job_seeker: dict = Depends(require_jobseeker_auth)):
    """
    Get all applications for the logged-in job seeker
    
    Protected endpoint - requires cookie authentication
    Returns applications with LIVE profile data and job details
    """
    try:
        applications = await service.get_my_applications(job_seeker_id=job_seeker["_id"])
        
        # Convert datetime objects to ISO format strings
        for app in applications:
            if "appliedAt" in app and app["appliedAt"]:
                app["appliedAt"] = app["appliedAt"].isoformat() if hasattr(app["appliedAt"], 'isoformat') else app["appliedAt"]
            if "updatedAt" in app and app["updatedAt"]:
                app["updatedAt"] = app["updatedAt"].isoformat() if hasattr(app["updatedAt"], 'isoformat') else app["updatedAt"]
            # Also convert datetime in stageHistory if present
            if "stageHistory" in app:
                for history in app["stageHistory"]:
                    if "changedAt" in history and history["changedAt"]:
                        history["changedAt"] = history["changedAt"].isoformat() if hasattr(history["changedAt"], 'isoformat') else history["changedAt"]
        
        return JSONResponse(
            status_code=200,
            content={
                "applications": applications,
                "total": len(applications)
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch applications: {str(e)}")


@router.delete("/applications/{applicationId}")
async def withdraw_application(
    applicationId: str,
    job_seeker: dict = Depends(require_jobseeker_auth)
):
    """
    Withdraw an application (soft delete)
    
    Protected endpoint - requires cookie authentication
    Job seeker can only withdraw their own applications
    """
    try:
        success = await service.withdraw_application(
            job_seeker_id=job_seeker["_id"],
            application_id=applicationId
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Application not found or already withdrawn")
        
        return JSONResponse(
            status_code=200,
            content={
                "message": "Application withdrawn successfully",
                "applicationId": applicationId
            }
        )
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to withdraw application: {str(e)}")


# ============================================
# Resume Download
# ============================================

@router.get("/downloadResume/{jobSeekerId}")
async def download_resume(
    jobSeekerId: str,
    user: dict = Depends(require_jobseeker_auth)
):
    """
    Download resume directly
    
    Protected endpoint - job seeker can only download their own resume
    """
    import requests
    from fastapi.responses import StreamingResponse
    from bson import ObjectId
    
    try:
        # Verify job seeker can only download their own resume
        if user["_id"] != jobSeekerId:
            raise HTTPException(status_code=403, detail="You can only download your own resume")
        
        # Get job seeker profile
        job_seeker = await jobSeekersCol.find_one({
            "_id": ObjectId(jobSeekerId),
            "isActive": True
        })
        
        if not job_seeker:
            raise HTTPException(status_code=404, detail="Job seeker not found")
        
        resume_url = job_seeker.get("resumeUrl")
        if not resume_url:
            raise HTTPException(status_code=404, detail="No resume uploaded")
        
        # Download file from Cloudinary
        response = requests.get(resume_url, timeout=30)
        response.raise_for_status()
        
        # Determine content type
        content_type = "application/pdf"
        if resume_url.lower().endswith('.docx'):
            content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        elif resume_url.lower().endswith('.doc'):
            content_type = "application/msword"
        
        # Extract filename from URL or use default
        filename = job_seeker.get("resumeFilename") or f"{job_seeker.get('name', 'resume')}.pdf"
        
        # Return file as streaming response with download headers
        return StreamingResponse(
            iter([response.content]),
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(response.content))
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to download resume: {str(e)}")
