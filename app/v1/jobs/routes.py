"""
Routes for Jobs ATS feature
"""
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from typing import Optional

# Import from core
from core.dependencies import requireAuth, logActivity

# Import from current module
from .service import JobsService
from .schemas import (
    JobCreate, JobUpdate, JobResponse, JobListResponse,
    JobDeleteRequest, JobActionRequest
)

# Initialize router
router = APIRouter(prefix="/secure", tags=["Jobs ATS"])

# Initialize service
jobs_service = JobsService()


@router.post(
    "/createJob",
    summary="Create New Job Posting",
    description="""
    **Purpose:** Create a new job posting for the organization.
    
    **Role Access:** ORG_HR, SPOC only (HELPER cannot create)
    
    **Request Body Example:**
    ```json
    {
      "title": "Senior Python Backend Developer",
      "department": "Engineering",
      "location": "Hyderabad, India",
      "type": "Full-time",
      "experience": "4-6 years",
      "salary": "₹18,00,000 - ₹24,00,000 per annum",
      "skills": "Python, FastAPI, MongoDB, Docker, AWS, REST APIs",
      "description": "We are looking for an experienced Python Backend Developer to build scalable APIs and microservices using FastAPI and MongoDB. The candidate should have experience with cloud deployment, authentication systems, and database optimization.",
      "status": "open",
      "deadline": "2026-06-30T00:00:00Z"
    }
    ```
    
    **Response Example:**
    ```json
    {
      "message": "Job created successfully",
      "job": {
        "_id": "6a0028c89d57fa3ca6a76444",
        "title": "Senior Python Backend Developer",
        "department": "Engineering",
        "location": "Hyderabad, India",
        "type": "Full-time",
        "experience": "4-6 years",
        "salary": "₹18,00,000 - ₹24,00,000 per annum",
        "skills": [
          "Python",
          "FastAPI",
          "MongoDB",
          "Docker",
          "AWS",
          "REST APIs"
        ],
        "description": "We are looking for an experienced Python Backend Developer...",
        "status": "open",
        "deadline": "2026-06-30T00:00:00Z",
        "applicantCount": 0,
        "shortlistedCount": 0,
        "hiredCount": 0,
        "createdBy": "hr@company.com",
        "createdAt": "2026-05-10T10:30:00Z",
        "updatedAt": "2026-05-10T10:30:00Z"
      }
    }
    ```
    
    **Key Features:**
    - ✅ Organization auto-detected from JWT token
    - ✅ Skills parsed from comma-separated string
    - ✅ Status can be "open", "closed", or "draft"
    - ✅ Optional deadline for auto-closing
    
    **Workflow:**
    1. HR fills job details form
    2. Backend creates job with counts at 0
    3. Job appears in HR's jobs list
    """,
    responses={
        201: {"description": "Job created successfully"},
        400: {"description": "Invalid input"},
        403: {"description": "Unauthorized - HELPER cannot create jobs"}
    }
)
async def create_job(
    job_data: JobCreate,
    user: dict = Depends(requireAuth)
):
    """Create a new job posting"""
    
    role = user.get("role")
    
    # Access control - only ORG_HR and SPOC can create
    if role not in ["ORG_HR", "SPOC"]:
        raise HTTPException(
            status_code=403,
            detail="Only ORG_HR and SPOC can create jobs"
        )
    
    # Get org info
    org_id = user.get("organizationId")
    creator_email = user.get("email")
    
    if not org_id:
        raise HTTPException(
            status_code=400,
            detail="Organization ID missing from user profile"
        )
    
    try:
        # Create job
        job = await jobs_service.create_job(
            title=job_data.title,
            department=job_data.department,
            location=job_data.location,
            job_type=job_data.type,
            experience=job_data.experience,
            salary=job_data.salary,
            skills_string=job_data.skills,
            description=job_data.description,
            status=job_data.status,
            deadline=job_data.deadline,
            org_id=org_id,
            creator_email=creator_email
        )
        
        # Log activity
        await logActivity(
            user,
            "Job Created",
            f"Created job: {job_data.title}",
            "Info"
        )
        
        return {
            "message": "Job created successfully",
            "job": job
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error creating job: {str(e)}"
        )


@router.get(
    "/getJobs",
    summary="Get Jobs List",
    description="""
    **Purpose:** Get list of jobs based on role and filters.
    
    **Role-Based Behavior:**
    - **ORG_HR/SPOC/HELPER:** See only their organization's jobs
    - **SUPER_ADMIN/SUPER_SPOC:** See all jobs across all organizations
    
    **Query Parameters:**
    - `orgId` (optional) - Filter by organization (superadmin only)
    - `status` (optional) - Filter by status (open/closed/draft)
    - `search` (optional) - Search in title and skills
    
    **Response Example:**
    ```json
    {
      "jobs": [
        {
          "_id": "6a0028c89d57fa3ca6a76444",
          "title": "Senior Python Backend Developer",
          "department": "Engineering",
          "location": "Hyderabad, India",
          "type": "Full-time",
          "experience": "4-6 years",
          "salary": "₹18,00,000 - ₹24,00,000 per annum",
          "skills": ["Python", "FastAPI", "MongoDB", "Docker", "AWS"],
          "description": "We are looking for an experienced...",
          "status": "open",
          "deadline": "2026-06-30T00:00:00Z",
          "applicantCount": 15,
          "shortlistedCount": 5,
          "hiredCount": 0,
          "createdBy": "hr@company.com",
          "createdAt": "2026-05-10T10:30:00Z",
          "updatedAt": "2026-05-10T10:30:00Z"
        }
      ],
      "total": 1
    }
    ```
    
    **Note:** `orgId` and `orgName` fields are removed for org users (only shown to superadmin)
    
    **Returns:** List of jobs sorted by creation date (newest first)
    """
)
async def get_jobs(
    orgId: Optional[str] = Query(None, description="Filter by organization (superadmin only)"),
    status: Optional[str] = Query(None, description="Filter by status"),
    search: Optional[str] = Query(None, description="Search in title/skills"),
    user: dict = Depends(requireAuth)
):
    """Get list of jobs"""
    
    role = user.get("role")
    user_org_id = user.get("organizationId")
    
    try:
        jobs = await jobs_service.get_jobs(
            user_role=role,
            user_org_id=user_org_id,
            filter_org_id=orgId,
            filter_status=status,
            search_query=search
        )
        
        # Serialize datetime fields to ISO format strings
        from datetime import datetime
        for job in jobs:
            # IMPORTANT: Ensure _id is string (should already be from service layer)
            if "_id" in job and not isinstance(job["_id"], str):
                job["_id"] = str(job["_id"])
            
            # Serialize datetime fields
            for key, value in list(job.items()):
                if isinstance(value, datetime):
                    job[key] = value.isoformat()
            
            # Remove internal fields not needed by frontend
            # Keep orgId and orgName only for superadmin (they can see multiple orgs)
            if role not in ["SUPER_ADMIN", "SUPER_SPOC", "SUPER_ADMIN_HELPER"]:
                job.pop("orgId", None)
                job.pop("orgName", None)  # Org users don't need to see their own org name
            
            # Remove soft delete fields
            job.pop("isDeleted", None)
            job.pop("deletedAt", None)
            job.pop("deletedBy", None)
        
        # Debug: Log first job to verify _id is present
        if jobs:
            print(f"DEBUG getJobs: First job _id = {jobs[0].get('_id')}, keys = {list(jobs[0].keys())}")
        
        return {
            "jobs": jobs,
            "total": len(jobs)
        }
        
    except Exception as e:
        print(f"ERROR in getJobs: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching jobs: {str(e)}"
        )


@router.get(
    "/getJob",
    summary="Get Single Job Details",
    description="""
    **Purpose:** Get detailed information about a specific job.
    
    **Access Control:**
    - Org roles can only view their own organization's jobs
    - Superadmin can view any job
    """
)
async def get_job(
    jobId: str = Query(..., description="Job ID"),
    user: dict = Depends(requireAuth)
):
    """Get single job details"""
    
    # Validate jobId
    if not jobId or jobId == "undefined" or jobId == "null":
        raise HTTPException(
            status_code=400,
            detail="Invalid job ID provided"
        )
    
    role = user.get("role")
    user_org_id = user.get("organizationId")
    
    try:
        job = await jobs_service.get_job_by_id(
            job_id=jobId,
            user_role=role,
            user_org_id=user_org_id
        )
        
        if not job:
            raise HTTPException(
                status_code=404,
                detail="Job not found or access denied"
            )
        
        # Serialize datetime fields
        from datetime import datetime
        
        # IMPORTANT: Ensure _id is string
        if "_id" in job and not isinstance(job["_id"], str):
            job["_id"] = str(job["_id"])
        
        for key, value in list(job.items()):
            if isinstance(value, datetime):
                job[key] = value.isoformat()
        
        # Remove internal fields not needed by frontend
        if role not in ["SUPER_ADMIN", "SUPER_SPOC", "SUPER_ADMIN_HELPER"]:
            job.pop("orgId", None)
            job.pop("orgName", None)  # Org users don't need to see their own org name
        
        job.pop("isDeleted", None)
        job.pop("deletedAt", None)
        job.pop("deletedBy", None)
        
        print(f"DEBUG getJob: Returning job with _id = {job.get('_id')}")
        
        return job
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching job: {str(e)}"
        )


@router.post(
    "/updateJob",
    summary="Update Job Details",
    description="""
    **Purpose:** Update job posting details.
    
    **Role Access:** ORG_HR, SPOC only (HELPER cannot update)
    
    **Access Control:** Can only update own organization's jobs
    
    **Updatable Fields:** All job fields except counts and metadata
    """,
    responses={
        200: {"description": "Job updated successfully"},
        403: {"description": "Unauthorized"},
        404: {"description": "Job not found"}
    }
)
async def update_job(
    job_data: JobUpdate,
    user: dict = Depends(requireAuth)
):
    """Update job details"""
    
    role = user.get("role")
    
    # Access control
    if role not in ["ORG_HR", "SPOC"]:
        raise HTTPException(
            status_code=403,
            detail="Only ORG_HR and SPOC can update jobs"
        )
    
    user_org_id = user.get("organizationId")
    
    try:
        # Build update fields (exclude None values)
        update_fields = {
            k: v for k, v in job_data.dict(exclude={"jobId"}).items()
            if v is not None
        }
        
        if not update_fields:
            raise HTTPException(
                status_code=400,
                detail="No fields to update"
            )
        
        # Update job
        updated_job = await jobs_service.update_job(
            job_id=job_data.jobId,
            update_fields=update_fields,
            user_org_id=user_org_id
        )
        
        if not updated_job:
            raise HTTPException(
                status_code=404,
                detail="Job not found or access denied"
            )
        
        # Log activity
        await logActivity(
            user,
            "Job Updated",
            f"Updated job: {updated_job['title']}",
            "Info"
        )
        
        return {
            "message": "Job updated successfully",
            "job": updated_job
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error updating job: {str(e)}"
        )


@router.post(
    "/deleteJob",
    summary="Delete Job Posting",
    description="""
    **Purpose:** Soft delete a job posting and all its applications.
    
    **Role Access:** ORG_HR, SPOC only (HELPER cannot delete)
    
    **Important:** This is a soft delete. Job and applications are marked as deleted but not removed from database.
    
    **Cascade:** All applications for this job are also soft deleted.
    """,
    responses={
        200: {"description": "Job deleted successfully"},
        403: {"description": "Unauthorized"},
        404: {"description": "Job not found"}
    }
)
async def delete_job(
    request: JobDeleteRequest,
    user: dict = Depends(requireAuth)
):
    """Delete job posting"""
    
    role = user.get("role")
    
    # Access control
    if role not in ["ORG_HR", "SPOC"]:
        raise HTTPException(
            status_code=403,
            detail="Only ORG_HR and SPOC can delete jobs"
        )
    
    user_org_id = user.get("organizationId")
    user_email = user.get("email")
    
    try:
        success = await jobs_service.delete_job(
            job_id=request.jobId,
            user_org_id=user_org_id,
            user_email=user_email
        )
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail="Job not found or access denied"
            )
        
        # Log activity
        await logActivity(
            user,
            "Job Deleted",
            f"Deleted job ID: {request.jobId}",
            "Warning"
        )
        
        return {"message": "Job deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting job: {str(e)}"
        )


@router.post(
    "/duplicateJob",
    summary="Duplicate Job Posting",
    description="""
    **Purpose:** Create a copy of an existing job posting.
    
    **Role Access:** ORG_HR, SPOC only
    
    **Behavior:**
    - Title gets " (Copy)" appended
    - Status set to "draft"
    - All counts reset to 0
    - Applications NOT copied
    """,
    responses={
        201: {"description": "Job duplicated successfully"},
        403: {"description": "Unauthorized"},
        404: {"description": "Job not found"}
    }
)
async def duplicate_job(
    request: JobActionRequest,
    user: dict = Depends(requireAuth)
):
    """Duplicate job posting"""
    
    role = user.get("role")
    
    # Access control
    if role not in ["ORG_HR", "SPOC"]:
        raise HTTPException(
            status_code=403,
            detail="Only ORG_HR and SPOC can duplicate jobs"
        )
    
    user_org_id = user.get("organizationId")
    user_email = user.get("email")
    
    try:
        new_job = await jobs_service.duplicate_job(
            job_id=request.jobId,
            user_org_id=user_org_id,
            user_email=user_email
        )
        
        if not new_job:
            raise HTTPException(
                status_code=404,
                detail="Job not found or access denied"
            )
        
        # Log activity
        await logActivity(
            user,
            "Job Duplicated",
            f"Duplicated job: {new_job['title']}",
            "Info"
        )
        
        return {
            "message": "Job duplicated successfully",
            "job": new_job
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error duplicating job: {str(e)}"
        )


@router.post(
    "/closeJob",
    summary="Close Job Posting",
    description="""
    **Purpose:** Close a job posting (no new applications accepted).
    
    **Role Access:** ORG_HR, SPOC only
    
    **Behavior:** Changes status from "open" to "closed"
    """,
    responses={
        200: {"description": "Job closed successfully"},
        403: {"description": "Unauthorized"},
        404: {"description": "Job not found"}
    }
)
async def close_job(
    request: JobActionRequest,
    user: dict = Depends(requireAuth)
):
    """Close job posting"""
    
    role = user.get("role")
    
    # Access control
    if role not in ["ORG_HR", "SPOC"]:
        raise HTTPException(
            status_code=403,
            detail="Only ORG_HR and SPOC can close jobs"
        )
    
    user_org_id = user.get("organizationId")
    
    try:
        success = await jobs_service.change_job_status(
            job_id=request.jobId,
            new_status="closed",
            user_org_id=user_org_id
        )
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail="Job not found or access denied"
            )
        
        # Log activity
        await logActivity(
            user,
            "Job Closed",
            f"Closed job ID: {request.jobId}",
            "Info"
        )
        
        return {"message": "Job closed successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error closing job: {str(e)}"
        )


@router.post(
    "/reopenJob",
    summary="Reopen Job Posting",
    description="""
    **Purpose:** Reopen a closed job posting.
    
    **Role Access:** ORG_HR, SPOC only
    
    **Behavior:** Changes status from "closed" to "open"
    """,
    responses={
        200: {"description": "Job reopened successfully"},
        403: {"description": "Unauthorized"},
        404: {"description": "Job not found"}
    }
)
async def reopen_job(
    request: JobActionRequest,
    user: dict = Depends(requireAuth)
):
    """Reopen job posting"""
    
    role = user.get("role")
    
    # Access control
    if role not in ["ORG_HR", "SPOC"]:
        raise HTTPException(
            status_code=403,
            detail="Only ORG_HR and SPOC can reopen jobs"
        )
    
    user_org_id = user.get("organizationId")
    
    try:
        success = await jobs_service.change_job_status(
            job_id=request.jobId,
            new_status="open",
            user_org_id=user_org_id
        )
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail="Job not found or access denied"
            )
        
        # Log activity
        await logActivity(
            user,
            "Job Reopened",
            f"Reopened job ID: {request.jobId}",
            "Info"
        )
        
        return {"message": "Job reopened successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error reopening job: {str(e)}"
        )


@router.post(
    "/parseJobDescription",
    summary="Parse Job Description with AI",
    description="""
    **Purpose:** Extract structured fields from a job description using AI.
    
    **Two Input Methods:**
    1. **Upload File:** PDF, DOCX, or TXT file
    2. **Paste Text:** Direct text input
    
    **Role Access:** ORG_HR, SPOC, HELPER
    
    **How to Use:**
    - **Option A (File Upload):** Send `jd_file` as multipart/form-data
    - **Option B (Text Input):** Send `jd_text` as form field
    
    **Response Example:**
    ```json
    {
      "title": "Senior Python Backend Developer",
      "department": "Engineering",
      "location": "Hyderabad, India",
      "type": "Full-time",
      "experience": "4-6 years",
      "salary": "₹18L - ₹24L per annum",
      "skills": ["Python", "FastAPI", "MongoDB", "Docker", "AWS"],
      "description": "We are looking for an experienced Python Backend Developer...",
      "deadline": "2026-06-30"
    }
    ```
    
    **Next Steps:**
    1. Frontend receives this parsed data
    2. Pre-fills the job creation form
    3. HR reviews/edits the fields
    4. HR clicks "Create Job" → calls `/secure/createJob`
    """,
    responses={
        200: {"description": "JD parsed successfully"},
        400: {"description": "Invalid input or parsing failed"},
        403: {"description": "Unauthorized access"}
    }
)
async def parse_job_description(
    jd_file: Optional[UploadFile] = File(None),
    jd_text: Optional[str] = Form(None),
    user: dict = Depends(requireAuth)
):
    """Parse job description from file or text using AI"""
    from .jd_parser import parse_job_description_with_ai
    from utils.resume_screening import extract_text_from_file
    
    role = user.get("role")
    
    # Access control
    if role not in ["ORG_HR", "SPOC", "HELPER"]:
        raise HTTPException(
            status_code=403,
            detail="Only ORG_HR, SPOC, and HELPER can parse job descriptions"
        )
    
    # Validate input
    if not jd_file and not jd_text:
        raise HTTPException(
            status_code=400,
            detail="Either jd_file or jd_text must be provided"
        )
    
    try:
        # Extract text from file or use provided text
        if jd_file:
            # Read file content
            file_content = await jd_file.read()
            filename = jd_file.filename.lower()
            
            # Validate file type
            if not (filename.endswith('.pdf') or filename.endswith('.docx') or 
                    filename.endswith('.doc') or filename.endswith('.txt')):
                raise HTTPException(
                    status_code=400,
                    detail="Only PDF, DOCX, and TXT files are supported"
                )
            
            # Extract text from file
            jd_text = extract_text_from_file(file_content, jd_file.filename)
            
            if not jd_text or len(jd_text.strip()) < 50:
                raise HTTPException(
                    status_code=400,
                    detail="Could not extract text from file or text is too short"
                )
        
        # Parse JD with AI
        parsed_data = await parse_job_description_with_ai(jd_text)
        
        # Log activity
        await logActivity(
            user,
            "JD Parsed with AI",
            f"Parsed job description for: {parsed_data.get('title', 'Unknown')}",
            "Success"
        )
        
        return parsed_data
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in parseJobDescription: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error parsing job description: {str(e)}"
        )
