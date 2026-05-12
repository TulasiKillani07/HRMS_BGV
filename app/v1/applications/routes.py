"""
Routes for Applications ATS feature
"""
from fastapi import APIRouter, Depends, HTTPException, Query

# Import from main
from main import requireAuth, logActivity

# Import from current module
from .service import ApplicationsService
from .schemas import (
    ApplicationCreate, ApplicationUpdateStage, BulkUpdateStage,
    ApplicationAddNote, ApplicationDelete, ApplicationResponse,
    ApplicationListResponse
)
from .smart_shortlist_schemas import (
    SmartShortlistRequest, SmartShortlistResponse
)

# Initialize router
router = APIRouter(prefix="/secure", tags=["Applications ATS"])

# Initialize service
applications_service = ApplicationsService()


@router.get(
    "/getApplications",
    summary="Get Applications for Job (Pipeline View)",
    description="""
    **Purpose:** Get all applications for a specific job (pipeline view).
    
    **Role Access:** ORG_HR, SPOC, HELPER (view only)
    
    **Query Parameters:**
    - `jobId` (required) - Job ID
    
    **Response Example:**
    ```json
    {
      "applications": [
        {
          "_id": "6a00314a651c6dea3f1acda8",
          "jobId": "6a0028c89d57fa3ca6a76444",
          "jobSeekerId": "69ff264f1bd50eeba0e601f5",
          "jobSeekerName": "Arjun Kumar",
          "jobSeekerEmail": "arjun@example.com",
          "jobSeekerPhone": "+91-9876543210",
          "resumeUrl": "https://res.cloudinary.com/...",
          "jobSeekerProfile": {
            "name": "Arjun Kumar",
            "email": "arjun@example.com",
            "phone": "+91-9876543210",
            "resumeUrl": "https://res.cloudinary.com/...",
            "profileCompletion": 85,
            "experience": [
              {
                "company": "Tech Solutions",
                "position": "Backend Developer",
                "duration": "2 years",
                "description": "Developed REST APIs using FastAPI"
              }
            ],
            "education": [
              {
                "degree": "B.Tech in Computer Science",
                "institution": "IIT Delhi",
                "year": "2020"
              }
            ],
            "skills": ["Python", "FastAPI", "MongoDB", "Docker"]
          },
          "stage": "Applied",
          "source": "JOB_PORTAL",
          "aiScore": null,
          "notes": "",
          "stageHistory": [
            {
              "stage": "Applied",
              "changedBy": "system",
              "changedAt": "2026-05-10T10:30:00Z",
              "notes": "Application created via JOB_PORTAL"
            }
          ],
          "appliedAt": "2026-05-10T10:30:00Z",
          "updatedAt": "2026-05-10T10:30:00Z"
        }
      ],
      "total": 1,
      "stageCounts": {
        "Applied": 10,
        "Resume Shortlist": 5,
        "Interview": 2
      }
    }
    ```
    
    **Important Notes:**
    - **All applications reference `job_seekers` collection** (via `jobSeekerId`)
    - **Live profile data** is fetched from `job_seekers` and shown in `jobSeekerProfile`
    - **Profile updates automatically** when job seeker updates their profile
    - **Only after BGV initiation** is a record created in `candidates` collection
    
    **Response Fields:**
    - `_id`: Application ID (use this for updates/deletes)
    - `jobId`: Job ID
    - `jobSeekerId`: Job seeker ID (reference to job_seekers collection)
    - `jobSeekerName`: Job seeker name (live from job_seekers)
    - `jobSeekerEmail`: Job seeker email (live from job_seekers)
    - `jobSeekerPhone`: Job seeker phone (live from job_seekers)
    - `resumeUrl`: Resume URL from job_seekers
    - `jobSeekerProfile`: Complete live profile with experience, education, skills
    - `stage`: Current stage (Applied, Resume Shortlist, Interview)
    - `source`: JOB_PORTAL, MANUAL, or AI_SCREENING
    - `stageHistory`: Complete audit trail
    
    **Use Case:** HR views job seeker pipeline for a job
    """
)
async def get_applications(
    jobId: str = Query(..., description="Job ID"),
    user: dict = Depends(requireAuth)
):
    """Get applications for a job"""
    
    # Validate jobId
    if not jobId or jobId == "undefined" or jobId == "null":
        raise HTTPException(
            status_code=400,
            detail="Invalid job ID provided"
        )
    
    user_org_id = user.get("organizationId")
    role = user.get("role")
    
    if not user_org_id:
        raise HTTPException(
            status_code=400,
            detail="Organization ID missing from token"
        )
    
    try:
        result = await applications_service.get_applications_for_job(
            job_id=jobId,
            user_org_id=user_org_id
        )
        
        # Serialize datetime fields to ISO format strings
        from datetime import datetime
        for app in result["applications"]:
            # IMPORTANT: Ensure _id is string
            if "_id" in app and not isinstance(app["_id"], str):
                app["_id"] = str(app["_id"])
            
            # Serialize datetime fields
            for key, value in list(app.items()):
                if isinstance(value, datetime):
                    app[key] = value.isoformat()
            
            # Serialize datetime in stageHistory
            if "stageHistory" in app:
                for history_item in app["stageHistory"]:
                    if isinstance(history_item.get("changedAt"), datetime):
                        history_item["changedAt"] = history_item["changedAt"].isoformat()
            
            # Remove internal fields not needed by frontend
            if role not in ["SUPER_ADMIN", "SUPER_SPOC", "SUPER_ADMIN_HELPER"]:
                app.pop("orgId", None)
            
            app.pop("isDeleted", None)
            app.pop("deletedAt", None)
            app.pop("deletedBy", None)
        
        # Debug: Log first application
        if result["applications"]:
            print(f"DEBUG getApplications: First app _id = {result['applications'][0].get('_id')}")
        
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        print(f"ERROR in getApplications: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching applications: {str(e)}"
        )


@router.get(
    "/getApplication",
    summary="Get Single Application Details",
    description="""
    **Purpose:** Get detailed information about a specific application.
    
    **Role Access:** ORG_HR, SPOC, HELPER
    
    **Returns:** Full application details including:
    - `_id`: Application ID
    - `jobId`: Job ID
    - `jobSeekerId`: Job seeker ID (if from job portal)
    - `candidateId`: Candidate ID (if HR-added)
    - Candidate snapshot data (name, email, phone, resume)
    - `stage`: Current stage
    - `source`: JOB_PORTAL, MANUAL, or AI_SCREENING
    - `stageHistory`: Complete audit trail with timestamps
    - `notes`: HR notes about candidate
    - `appliedAt`, `updatedAt`: Timestamps
    """
)
async def get_application(
    applicationId: str = Query(..., description="Application ID"),
    user: dict = Depends(requireAuth)
):
    """Get single application details"""
    
    # Validate applicationId
    if not applicationId or applicationId == "undefined" or applicationId == "null":
        raise HTTPException(
            status_code=400,
            detail="Invalid application ID provided"
        )
    
    user_org_id = user.get("organizationId")
    role = user.get("role")
    
    try:
        application = await applications_service.get_application_by_id(
            application_id=applicationId,
            user_org_id=user_org_id
        )
        
        if not application:
            raise HTTPException(
                status_code=404,
                detail="Application not found or access denied"
            )
        
        # Serialize datetime fields
        from datetime import datetime
        
        # IMPORTANT: Ensure _id is string
        if "_id" in application and not isinstance(application["_id"], str):
            application["_id"] = str(application["_id"])
        
        for key, value in list(application.items()):
            if isinstance(value, datetime):
                application[key] = value.isoformat()
        
        # Serialize datetime in stageHistory
        if "stageHistory" in application:
            for history_item in application["stageHistory"]:
                if isinstance(history_item.get("changedAt"), datetime):
                    history_item["changedAt"] = history_item["changedAt"].isoformat()
        
        # Remove internal fields
        if role not in ["SUPER_ADMIN", "SUPER_SPOC", "SUPER_ADMIN_HELPER"]:
            application.pop("orgId", None)
        
        application.pop("isDeleted", None)
        application.pop("deletedAt", None)
        application.pop("deletedBy", None)
        
        print(f"DEBUG getApplication: Returning app with _id = {application.get('_id')}")
        
        return application
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in getApplication: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching application: {str(e)}"
        )


@router.post(
    "/updateApplicationStage",
    summary="Update Application Stage",
    description="""
    **Purpose:** Move candidate to a new stage in the pipeline.
    
    **Role Access:** ORG_HR, SPOC only (HELPER cannot update)
    
    **Request Body Example:**
    ```json
    {
      "applicationId": "6a00314a651c6dea3f1acda8",
      "stage": "Resume Shortlist",
      "notes": "Strong technical background, good fit for the role"
    }
    ```
    
    **Response Example:**
    ```json
    {
      "message": "Application stage updated successfully",
      "application": {
        "_id": "6a00314a651c6dea3f1acda8",
        "jobId": "6a0028c89d57fa3ca6a76444",
        "jobSeekerId": "69ff264f1bd50eeba0e601f5",
        "candidateName": "Arjun Kumar",
        "stage": "Resume Shortlist",
        "notes": "Strong technical background, good fit for the role",
        "stageHistory": [
          {
            "stage": "Applied",
            "changedBy": "system",
            "changedAt": "2026-05-10T10:30:00Z",
            "notes": "Application created via JOB_PORTAL"
          },
          {
            "stage": "Resume Shortlist",
            "changedBy": "hr@company.com",
            "changedAt": "2026-05-11T14:20:00Z",
            "notes": "Strong technical background, good fit for the role"
          }
        ],
        "updatedAt": "2026-05-11T14:20:00Z"
      }
    }
    ```
    
    **Valid Stages:**
    - `Applied` - Initial application
    - `Resume Shortlist` - Resume reviewed and shortlisted
    - `Interview` - Ready for interview scheduling
    
    **Note:** After "Interview" stage, use Interview Management System to create interview record.
    
    **Behavior:**
    - Adds entry to stage history (audit trail)
    - Updates job counts automatically
    - No restrictions on stage transitions (can move forward or backward)
    - Logs activity for audit
    """,
    responses={
        200: {"description": "Stage updated successfully"},
        403: {"description": "Unauthorized - Only ORG_HR and SPOC can update"},
        404: {"description": "Application not found"}
    }
)
async def update_application_stage(
    request: ApplicationUpdateStage,
    user: dict = Depends(requireAuth)
):
    """Update application stage"""
    
    role = user.get("role")
    
    # Access control
    if role not in ["ORG_HR", "SPOC"]:
        raise HTTPException(
            status_code=403,
            detail="Only ORG_HR and SPOC can update application stages"
        )
    
    user_org_id = user.get("organizationId")
    user_email = user.get("email")
    
    try:
        updated_app = await applications_service.update_application_stage(
            application_id=request.applicationId,
            new_stage=request.stage,
            notes=request.notes or "",
            user_org_id=user_org_id,
            user_email=user_email
        )
        
        if not updated_app:
            raise HTTPException(
                status_code=404,
                detail="Application not found or access denied"
            )
        
        # Serialize datetime fields
        from datetime import datetime
        for key, value in list(updated_app.items()):
            if isinstance(value, datetime):
                updated_app[key] = value.isoformat()
        
        # Serialize datetime in stageHistory
        if "stageHistory" in updated_app:
            for history_item in updated_app["stageHistory"]:
                if isinstance(history_item.get("changedAt"), datetime):
                    history_item["changedAt"] = history_item["changedAt"].isoformat()
        
        # Remove internal fields
        if role not in ["SUPER_ADMIN", "SUPER_SPOC", "SUPER_ADMIN_HELPER"]:
            updated_app.pop("orgId", None)
        
        updated_app.pop("isDeleted", None)
        updated_app.pop("deletedAt", None)
        updated_app.pop("deletedBy", None)
        
        # Log activity
        await logActivity(
            user,
            "Application Stage Updated",
            f"Moved candidate to {request.stage}",
            "Info"
        )
        
        return {
            "message": "Application stage updated successfully",
            "application": updated_app
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in updateApplicationStage: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error updating stage: {str(e)}"
        )


@router.post(
    "/bulkUpdateApplicationStage",
    summary="Bulk Update Application Stages",
    description="""
    **Purpose:** Move multiple candidates to the same stage at once.
    
    **Role Access:** ORG_HR, SPOC only
    
    **Use Case:** HR selects multiple candidates and moves them all to "Shortlisted"
    
    **Returns:** Count of successful and failed updates
    """,
    responses={
        200: {"description": "Bulk update completed"},
        403: {"description": "Unauthorized"}
    }
)
async def bulk_update_application_stage(
    request: BulkUpdateStage,
    user: dict = Depends(requireAuth)
):
    """Bulk update application stages"""
    
    role = user.get("role")
    
    # Access control
    if role not in ["ORG_HR", "SPOC"]:
        raise HTTPException(
            status_code=403,
            detail="Only ORG_HR and SPOC can update application stages"
        )
    
    user_org_id = user.get("organizationId")
    user_email = user.get("email")
    
    try:
        result = await applications_service.bulk_update_stage(
            application_ids=request.applicationIds,
            new_stage=request.stage,
            notes=request.notes or "",
            user_org_id=user_org_id,
            user_email=user_email
        )
        
        # Log activity
        await logActivity(
            user,
            "Bulk Stage Update",
            f"Updated {result['successful']} applications to {request.stage}",
            "Info"
        )
        
        return {
            "message": "Bulk update completed",
            "result": result
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error in bulk update: {str(e)}"
        )


@router.post(
    "/addApplicationNote",
    summary="Add Note to Application",
    description="""
    **Purpose:** Add or update notes for an application.
    
    **Role Access:** ORG_HR, SPOC only
    
    **Use Case:** HR adds interview feedback or observations about candidate
    """,
    responses={
        200: {"description": "Note added successfully"},
        403: {"description": "Unauthorized"},
        404: {"description": "Application not found"}
    }
)
async def add_application_note(
    request: ApplicationAddNote,
    user: dict = Depends(requireAuth)
):
    """Add note to application"""
    
    role = user.get("role")
    
    # Access control
    if role not in ["ORG_HR", "SPOC"]:
        raise HTTPException(
            status_code=403,
            detail="Only ORG_HR and SPOC can add notes"
        )
    
    user_org_id = user.get("organizationId")
    
    try:
        success = await applications_service.add_note(
            application_id=request.applicationId,
            note=request.note,
            user_org_id=user_org_id
        )
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail="Application not found or access denied"
            )
        
        return {"message": "Note added successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error adding note: {str(e)}"
        )


@router.post(
    "/deleteApplication",
    summary="Delete Application",
    description="""
    **Purpose:** Soft delete an application.
    
    **Role Access:** ORG_HR, SPOC only
    
    **Behavior:**
    - Soft delete (marked as deleted, not removed)
    - Updates job counts automatically
    """,
    responses={
        200: {"description": "Application deleted successfully"},
        403: {"description": "Unauthorized"},
        404: {"description": "Application not found"}
    }
)
async def delete_application(
    request: ApplicationDelete,
    user: dict = Depends(requireAuth)
):
    """Delete application"""
    
    role = user.get("role")
    
    # Access control
    if role not in ["ORG_HR", "SPOC"]:
        raise HTTPException(
            status_code=403,
            detail="Only ORG_HR and SPOC can delete applications"
        )
    
    user_org_id = user.get("organizationId")
    user_email = user.get("email")
    
    try:
        success = await applications_service.delete_application(
            application_id=request.applicationId,
            user_org_id=user_org_id,
            user_email=user_email
        )
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail="Application not found or access denied"
            )
        
        # Log activity
        await logActivity(
            user,
            "Application Deleted",
            f"Deleted application ID: {request.applicationId}",
            "Warning"
        )
        
        return {"message": "Application deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting application: {str(e)}"
        )


@router.post(
    "/bulkShortlistApplications",
    summary="Smart Shortlist Applications",
    description="""
    **Purpose:** Intelligently shortlist applications based on AI Score and Profile Completion.
    
    **Role Access:** ORG_HR, SPOC only
    
    **Features:**
    1. **Dynamic Criteria:**
       - By Percentage: Top X% of applications (e.g., top 20%)
       - By Number: Top N applications (e.g., top 10 applications)
    
    2. **Smart Sorting:**
       - Primary: AI Score (if available)
       - Fallback: Profile Completion percentage
       - No application date sorting
    
    3. **Preview Mode:**
       - Set `previewOnly: true` to see which applications will be shortlisted
       - Review the list before committing
    
    4. **Manual Adjustments:**
       - Add/remove specific applications from the shortlist
       - Provide `manualAdjustments` array with application IDs to toggle
    
    **Request Body Example (Percentage):**
    ```json
    {
      "jobId": "6a0028c89d57fa3ca6a76444",
      "criteriaType": "percentage",
      "criteriaValue": 20,
      "previewOnly": true
    }
    ```
    
    **Request Body Example (Number):**
    ```json
    {
      "jobId": "6a0028c89d57fa3ca6a76444",
      "criteriaType": "number",
      "criteriaValue": 10,
      "previewOnly": false,
      "manualAdjustments": ["6a00314a651c6dea3f1acda8"]
    }
    ```
    
    **Response Example (Preview):**
    ```json
    {
      "message": "Preview generated",
      "jobId": "6a0028c89d57fa3ca6a76444",
      "criteriaType": "percentage",
      "criteriaValue": 20,
      "totalApplications": 50,
      "applicationsToShortlist": 10,
      "preview": [
        {
          "applicationId": "6a00314a651c6dea3f1acda8",
          "jobSeekerId": "69ff264f1bd50eeba0e601f5",
          "jobSeekerName": "Arjun Kumar",
          "jobSeekerEmail": "arjun@example.com",
          "aiScore": 85.5,
          "profileCompletion": 90,
          "sortScore": 85.5,
          "currentStage": "Applied",
          "willBeShortlisted": true
        },
        {
          "applicationId": "6a00314a651c6dea3f1acda9",
          "jobSeekerId": "69ff264f1bd50eeba0e601f6",
          "jobSeekerName": "Priya Sharma",
          "jobSeekerEmail": "priya@example.com",
          "aiScore": null,
          "profileCompletion": 85,
          "sortScore": 85,
          "currentStage": "Applied",
          "willBeShortlisted": true
        }
      ],
      "updated": false,
      "updatedCount": null
    }
    ```
    
    **Response Example (Actual Update):**
    ```json
    {
      "message": "Successfully shortlisted 10 applications",
      "jobId": "6a0028c89d57fa3ca6a76444",
      "criteriaType": "number",
      "criteriaValue": 10,
      "totalApplications": 50,
      "applicationsToShortlist": 10,
      "preview": [...],
      "updated": true,
      "updatedCount": 10
    }
    ```
    
    **Workflow:**
    1. HR clicks "Smart Shortlist" button
    2. Selects criteria (percentage or number)
    3. Clicks "Preview" to see results
    4. Optionally adjusts by adding/removing specific applications
    5. Clicks "Apply" to move applications to "Resume Shortlist" stage
    
    **Important Notes:**
    - Only processes applications in "Applied" stage
    - Applications are sorted by AI Score (primary), Profile Completion (fallback)
    - Manual adjustments toggle selection (add if not selected, remove if selected)
    - Updates stage to "Resume Shortlist" when `previewOnly: false`
    - Automatically updates job counts after shortlisting
    - Adds entry to stage history for audit trail
    
    **Error Cases:**
    - Invalid job ID or access denied
    - No applications in "Applied" stage
    - Invalid criteria type or value
    """,
    responses={
        200: {"description": "Smart shortlist completed or preview generated"},
        400: {"description": "Invalid request parameters"},
        403: {"description": "Unauthorized - Only ORG_HR and SPOC can shortlist"},
        404: {"description": "Job not found or no applications to shortlist"}
    }
)
async def bulk_shortlist_applications(
    request: SmartShortlistRequest,
    user: dict = Depends(requireAuth)
):
    """Smart shortlist applications based on criteria"""
    
    role = user.get("role")
    
    # Access control
    if role not in ["ORG_HR", "SPOC"]:
        raise HTTPException(
            status_code=403,
            detail="Only ORG_HR and SPOC can shortlist applications"
        )
    
    user_org_id = user.get("organizationId")
    user_email = user.get("email")
    
    # Validate criteria
    if request.criteriaType not in ["percentage", "number"]:
        raise HTTPException(
            status_code=400,
            detail="criteriaType must be 'percentage' or 'number'"
        )
    
    if request.criteriaType == "percentage":
        if request.criteriaValue < 1 or request.criteriaValue > 100:
            raise HTTPException(
                status_code=400,
                detail="criteriaValue for percentage must be between 1 and 100"
            )
    else:  # number
        if request.criteriaValue < 1:
            raise HTTPException(
                status_code=400,
                detail="criteriaValue for number must be at least 1"
            )
    
    try:
        result = await applications_service.smart_shortlist_applications(
            job_id=request.jobId,
            user_org_id=user_org_id,
            criteria_type=request.criteriaType,
            criteria_value=request.criteriaValue,
            preview_only=request.previewOnly,
            manual_adjustments=request.manualAdjustments,
            user_email=user_email
        )
        
        # Log activity if not preview
        if not request.previewOnly:
            await logActivity(
                user,
                "Smart Shortlist Applied",
                f"Shortlisted {result['updatedCount']} applications using {request.criteriaType}: {request.criteriaValue}",
                "Info"
            )
        
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        print(f"ERROR in bulkShortlistApplications: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error in smart shortlist: {str(e)}"
        )
