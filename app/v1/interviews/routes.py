"""
Routes for Interview Management
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from datetime import datetime
from typing import Optional

# Import from core
from core.dependencies import requireAuth, logActivity

# Import from current module
from .service import InterviewService
from .schemas import (
    CreateInterviewRequest,
    ScheduleRoundRequest,
    UpdateRoundRequest,
    ExtendOfferRequest,
    RejectCandidateRequest,
    MarkAsHiredRequest,
    InitiateBGVRequest,
    InterviewResponse,
    InterviewListResponse
)

# Initialize router
router = APIRouter(prefix="/secure", tags=["Interview Management"])

# Initialize service
interview_service = InterviewService()


def serialize_interview_datetime(interview: dict) -> dict:
    """
    Serialize datetime fields in interview object to ISO format strings
    
    Args:
        interview: Interview dictionary
        
    Returns:
        Interview with serialized datetime fields
    """
    # Serialize top-level datetime fields
    for key, value in list(interview.items()):
        if isinstance(value, datetime):
            interview[key] = value.isoformat()
    
    # Serialize datetime in rounds
    if "rounds" in interview:
        for round_item in interview["rounds"]:
            for key, value in list(round_item.items()):
                if isinstance(value, datetime):
                    round_item[key] = value.isoformat()
    
    return interview


@router.post(
    "/createInterview",
    summary="Create Interview Record",
    description="""
    **Purpose:** Create interview record with 4 pending rounds.
    
    **Role Access:** ORG_HR, SPOC only
    
    **Request Body:**
    ```json
    {
      "applicationId": "6a00314a651c6dea3f1acda8"
    }
    ```
    
    **Response Example:**
    ```json
    {
      "message": "Interview created successfully",
      "interviewId": "6a0031bf651c6dea3f1acda9",
      "interview": {
        "interviewId": "6a0031bf651c6dea3f1acda9",
        "applicationId": "6a00314a651c6dea3f1acda8",
        "jobSeekerId": "69ff264f1bd50eeba0e601f5",
        "jobId": "6a0028c89d57fa3ca6a76444",
        "orgId": "6922aaeadc43986902ed7169",
        "rounds": [
          {
            "roundNumber": 1,
            "roundName": "Tech Round",
            "interviewer": null,
            "interviewerEmail": null,
            "scheduledAt": null,
            "status": "Pending",
            "rating": null,
            "feedback": "",
            "completedAt": null,
            "updatedBy": null,
            "updatedAt": null
          },
          {
            "roundNumber": 2,
            "roundName": "Manager Round",
            "interviewer": null,
            "interviewerEmail": null,
            "scheduledAt": null,
            "status": "Pending",
            "rating": null,
            "feedback": "",
            "completedAt": null,
            "updatedBy": null,
            "updatedAt": null
          },
          {
            "roundNumber": 3,
            "roundName": "HR Round",
            "interviewer": null,
            "interviewerEmail": null,
            "scheduledAt": null,
            "status": "Pending",
            "rating": null,
            "feedback": "",
            "completedAt": null,
            "updatedBy": null,
            "updatedAt": null
          },
          {
            "roundNumber": 4,
            "roundName": "Final Round",
            "interviewer": null,
            "interviewerEmail": null,
            "scheduledAt": null,
            "status": "Pending",
            "rating": null,
            "feedback": "",
            "completedAt": null,
            "updatedBy": null,
            "updatedAt": null
          }
        ],
        "currentRound": 1,
        "overallStatus": "In Progress",
        "offerExtended": false,
        "offerExtendedAt": null,
        "offerExtendedBy": null,
        "rejected": false,
        "rejectedAt": null,
        "rejectedBy": null,
        "rejectionReason": "",
        "rejectedAtRound": null,
        "hired": false,
        "hiredAt": null,
        "hiredBy": null,
        "bgvInitiated": false,
        "bgvInitiatedAt": null,
        "bgvInitiatedBy": null,
        "candidateId": null,
        "createdAt": "2026-05-10T07:20:31.320683Z",
        "createdBy": "hr@company.com",
        "updatedAt": "2026-05-10T07:20:31.320683Z",
        "isDeleted": false
      }
    }
    ```
    
    **Behavior:**
    - Creates interview with 4 rounds (Tech, Manager, HR, Final)
    - All rounds initialized as "Pending"
    - Updates application stage to "Interview"
    
    **Validation:** Prevents duplicate interviews for same application
    """,
    responses={
        201: {"description": "Interview created successfully"},
        400: {"description": "Interview already exists"},
        403: {"description": "Unauthorized"},
        404: {"description": "Application not found"}
    }
)
async def create_interview(
    request: CreateInterviewRequest,
    user: dict = Depends(requireAuth)
):
    """Create interview record"""
    
    role = user.get("role")
    
    # Access control
    if role not in ["ORG_HR", "SPOC"]:
        raise HTTPException(
            status_code=403,
            detail="Only ORG_HR and SPOC can create interviews"
        )
    
    user_org_id = user.get("organizationId")
    user_email = user.get("email")
    
    try:
        interview = await interview_service.create_interview(
            application_id=request.applicationId,
            user_org_id=user_org_id,
            user_email=user_email
        )
        
        # Serialize datetime fields
        interview = serialize_interview_datetime(interview)
        
        # Log activity
        await logActivity(
            user,
            "Interview Created",
            f"Created interview for application {request.applicationId}",
            "Info"
        )
        
        return {
            "message": "Interview created successfully",
            "interviewId": interview.get("_id"),
            "interview": interview
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error creating interview: {str(e)}"
        )


@router.get(
    "/getInterview/{interviewId}",
    summary="Get Interview Details",
    description="""
    **Purpose:** Get complete interview details with all rounds.
    
    **Role Access:** ORG_HR, SPOC, HELPER (read-only)
    
    **Returns:** Full interview details including round status, ratings, feedback
    """,
    response_model=InterviewResponse
)
async def get_interview(
    interviewId: str,
    user: dict = Depends(requireAuth)
):
    """Get interview details"""
    
    user_org_id = user.get("organizationId")
    
    try:
        interview = await interview_service.get_interview(
            interview_id=interviewId,
            user_org_id=user_org_id
        )
        
        if not interview:
            raise HTTPException(
                status_code=404,
                detail="Interview not found or access denied"
            )
        
        # Serialize datetime fields
        interview = serialize_interview_datetime(interview)
        
        return interview
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching interview: {str(e)}"
        )


@router.post(
    "/scheduleRound",
    summary="Schedule Interview Round",
    description="""
    **Purpose:** Schedule a specific interview round.
    
    **Role Access:** ORG_HR, SPOC only
    
    **Request Body:**
    ```json
    {
      "interviewId": "6a0031bf651c6dea3f1acda9",
      "roundNumber": 1,
      "interviewerId": "6a0032bf651c6dea3f1acdaa",
      "scheduledAt": "2026-05-12T10:00:00Z"
    }
    ```
    
    **Response Example:**
    ```json
    {
      "message": "Round scheduled successfully",
      "interviewId": "6a0031bf651c6dea3f1acda9",
      "interview": {
        "interviewId": "6a0031bf651c6dea3f1acda9",
        "rounds": [
          {
            "roundNumber": 1,
            "roundName": "Tech Round",
            "interviewerId": "6a0032bf651c6dea3f1acdaa",
            "interviewer": "Priya Sharma",
            "interviewerEmail": "priya@company.com",
            "scheduledAt": "2026-05-12T10:00:00Z",
            "status": "Scheduled",
            "rating": null,
            "feedback": "",
            "completedAt": null,
            "updatedBy": "hr@company.com",
            "updatedAt": "2026-05-10T08:00:00Z"
          }
        ],
        "currentRound": 1,
        "overallStatus": "In Progress"
      }
    }
    ```
    
    **Validation:**
    - Cannot schedule Round N if Round N-1 is not "Passed"
    - Cannot schedule for rejected or hired candidates
    - Interviewer must exist and be active
    - Interviewer must be available
    
    **Behavior:**
    - Updates round status to "Scheduled"
    - Auto-fills interviewer name and email from interviewers collection
    - Stores interviewerId for reference
    
    **How to Get Interviewers:**
    Use `GET /secure/getInterviewers?isActive=true&isAvailable=true` to get available interviewers
    """,
    responses={
        200: {"description": "Round scheduled successfully"},
        400: {"description": "Validation error"},
        403: {"description": "Unauthorized"},
        404: {"description": "Interview or interviewer not found"}
    }
)
async def schedule_round(
    request: ScheduleRoundRequest,
    user: dict = Depends(requireAuth)
):
    """Schedule interview round"""
    
    role = user.get("role")
    
    # Access control
    if role not in ["ORG_HR", "SPOC"]:
        raise HTTPException(
            status_code=403,
            detail="Only ORG_HR and SPOC can schedule rounds"
        )
    
    user_org_id = user.get("organizationId")
    user_email = user.get("email")
    
    try:
        interview = await interview_service.schedule_round(
            interview_id=request.interviewId,
            round_number=request.roundNumber,
            interviewer_id=request.interviewerId,
            scheduled_at=request.scheduledAt,
            user_org_id=user_org_id,
            user_email=user_email
        )
        
        # Serialize datetime fields
        interview = serialize_interview_datetime(interview)
        
        # Log activity
        await logActivity(
            user,
            "Round Scheduled",
            f"Scheduled Round {request.roundNumber} with interviewer {request.interviewerId}",
            "Info"
        )
        
        return {
            "message": "Round scheduled successfully",
            "interviewId": interview.get("_id"),
            "interview": interview
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error scheduling round: {str(e)}"
        )


@router.post(
    "/updateRound",
    summary="Update Round Status",
    description="""
    **Purpose:** Update round status to Passed or Failed.
    
    **Role Access:** ORG_HR, SPOC only
    
    **Request Body:**
    ```json
    {
      "interviewId": "6a0031bf651c6dea3f1acda9",
      "roundNumber": 1,
      "status": "Passed",
      "rating": 4,
      "feedback": "Excellent technical skills. Strong problem-solving ability."
    }
    ```
    
    **Response Example (Passed):**
    ```json
    {
      "message": "Round updated successfully",
      "interviewId": "6a0031bf651c6dea3f1acda9",
      "interview": {
        "interviewId": "6a0031bf651c6dea3f1acda9",
        "rounds": [
          {
            "roundNumber": 1,
            "roundName": "Tech Round",
            "interviewer": "Priya Sharma",
            "interviewerEmail": "priya@company.com",
            "scheduledAt": "2026-05-12T10:00:00Z",
            "status": "Passed",
            "rating": 4,
            "feedback": "Excellent technical skills. Strong problem-solving ability.",
            "completedAt": "2026-05-12T11:30:00Z",
            "updatedBy": "hr@company.com",
            "updatedAt": "2026-05-12T11:30:00Z"
          },
          {
            "roundNumber": 2,
            "roundName": "Manager Round",
            "status": "Pending"
          }
        ],
        "currentRound": 2,
        "overallStatus": "In Progress"
      }
    }
    ```
    
    **Response Example (Failed):**
    ```json
    {
      "message": "Round updated successfully",
      "interviewId": "6a0031bf651c6dea3f1acda9",
      "interview": {
        "interviewId": "6a0031bf651c6dea3f1acda9",
        "rounds": [
          {
            "roundNumber": 1,
            "status": "Failed",
            "rating": 2,
            "feedback": "Lacks required technical depth"
          }
        ],
        "rejected": true,
        "rejectedAt": "2026-05-12T11:30:00Z",
        "rejectedBy": "hr@company.com",
        "rejectionReason": "Failed Round 1",
        "rejectedAtRound": 1,
        "overallStatus": "Rejected"
      }
    }
    ```
    
    **Validation:**
    - Round must be "Scheduled" before updating
    - Cannot update for rejected or hired candidates
    - Rating must be 1-5
    
    **Behavior:**
    - If Passed: Unlocks next round, increments currentRound
    - If Failed: Marks interview as rejected, sets overallStatus to "Rejected"
    - Stores rating and feedback
    """,
    responses={
        200: {"description": "Round updated successfully"},
        400: {"description": "Validation error"},
        403: {"description": "Unauthorized"},
        404: {"description": "Interview not found"}
    }
)
async def update_round(
    request: UpdateRoundRequest,
    user: dict = Depends(requireAuth)
):
    """Update round status"""
    
    role = user.get("role")
    
    # Access control
    if role not in ["ORG_HR", "SPOC"]:
        raise HTTPException(
            status_code=403,
            detail="Only ORG_HR and SPOC can update rounds"
        )
    
    user_org_id = user.get("organizationId")
    user_email = user.get("email")
    
    try:
        interview = await interview_service.update_round(
            interview_id=request.interviewId,
            round_number=request.roundNumber,
            status=request.status,
            rating=request.rating,
            feedback=request.feedback,
            user_org_id=user_org_id,
            user_email=user_email
        )
        
        # Serialize datetime fields
        interview = serialize_interview_datetime(interview)
        
        # Log activity
        await logActivity(
            user,
            "Round Updated",
            f"Round {request.roundNumber} marked as {request.status}",
            "Info"
        )
        
        return {
            "message": "Round updated successfully",
            "interviewId": interview.get("_id"),
            "interview": interview
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error updating round: {str(e)}"
        )


@router.post(
    "/extendOffer",
    summary="Extend Offer to Candidate",
    description="""
    **Purpose:** Extend job offer to candidate.
    
    **Role Access:** ORG_HR, SPOC only
    
    **Request Body:**
    ```json
    {
      "interviewId": "6a0031bf651c6dea3f1acda9"
    }
    ```
    
    **Response Example:**
    ```json
    {
      "message": "Offer extended successfully",
      "interviewId": "6a0031bf651c6dea3f1acda9",
      "interview": {
        "interviewId": "6a0031bf651c6dea3f1acda9",
        "rounds": [
          {
            "roundNumber": 1,
            "status": "Passed",
            "rating": 5
          },
          {
            "roundNumber": 2,
            "status": "Passed",
            "rating": 5
          },
          {
            "roundNumber": 3,
            "status": "Pending"
          },
          {
            "roundNumber": 4,
            "status": "Pending"
          }
        ],
        "currentRound": 3,
        "overallStatus": "Offer Extended",
        "offerExtended": true,
        "offerExtendedAt": "2026-05-15T10:00:00Z",
        "offerExtendedBy": "hr@company.com"
      }
    }
    ```
    
    **Validation:**
    - At least 1 round must be passed (can hire after any round)
    - Cannot extend to rejected candidates
    
    **Behavior:**
    - Updates status to "Offer Extended"
    - Flexible hiring: Can extend offer after 1, 2, 3, or 4 rounds
    - Just status change (no email for now)
    """,
    responses={
        200: {"description": "Offer extended successfully"},
        400: {"description": "Validation error"},
        403: {"description": "Unauthorized"},
        404: {"description": "Interview not found"}
    }
)
async def extend_offer(
    request: ExtendOfferRequest,
    user: dict = Depends(requireAuth)
):
    """Extend offer"""
    
    role = user.get("role")
    
    # Access control
    if role not in ["ORG_HR", "SPOC"]:
        raise HTTPException(
            status_code=403,
            detail="Only ORG_HR and SPOC can extend offers"
        )
    
    user_org_id = user.get("organizationId")
    user_email = user.get("email")
    
    try:
        interview = await interview_service.extend_offer(
            interview_id=request.interviewId,
            user_org_id=user_org_id,
            user_email=user_email
        )
        
        # Serialize datetime fields
        interview = serialize_interview_datetime(interview)
        
        # Log activity
        await logActivity(
            user,
            "Offer Extended",
            f"Extended offer for interview {request.interviewId}",
            "Success"
        )
        
        return {
            "message": "Offer extended successfully",
            "interviewId": interview.get("_id"),
            "interview": interview
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error extending offer: {str(e)}"
        )


@router.post(
    "/rejectCandidate",
    summary="Reject Candidate",
    description="""
    **Purpose:** Reject candidate at any stage.
    
    **Role Access:** ORG_HR, SPOC only
    
    **Request Body:**
    ```json
    {
      "interviewId": "6a0031bf651c6dea3f1acda9",
      "reason": "Not a good cultural fit",
      "rejectedAtRound": 2
    }
    ```
    
    **Response Example:**
    ```json
    {
      "message": "Candidate rejected successfully",
      "interviewId": "6a0031bf651c6dea3f1acda9",
      "interview": {
        "interviewId": "6a0031bf651c6dea3f1acda9",
        "overallStatus": "Rejected",
        "rejected": true,
        "rejectedAt": "2026-05-13T14:30:00Z",
        "rejectedBy": "hr@company.com",
        "rejectionReason": "Not a good cultural fit",
        "rejectedAtRound": 2
      }
    }
    ```
    
    **Behavior:**
    - Marks interview as rejected
    - Stores rejection reason
    - Records which round candidate was rejected at
    - Email notifications: Later
    """,
    responses={
        200: {"description": "Candidate rejected successfully"},
        400: {"description": "Validation error"},
        403: {"description": "Unauthorized"},
        404: {"description": "Interview not found"}
    }
)
async def reject_candidate(
    request: RejectCandidateRequest,
    user: dict = Depends(requireAuth)
):
    """Reject candidate"""
    
    role = user.get("role")
    
    # Access control
    if role not in ["ORG_HR", "SPOC"]:
        raise HTTPException(
            status_code=403,
            detail="Only ORG_HR and SPOC can reject candidates"
        )
    
    user_org_id = user.get("organizationId")
    user_email = user.get("email")
    
    try:
        interview = await interview_service.reject_candidate(
            interview_id=request.interviewId,
            reason=request.reason,
            rejected_at_round=request.rejectedAtRound,
            user_org_id=user_org_id,
            user_email=user_email
        )
        
        # Serialize datetime fields
        interview = serialize_interview_datetime(interview)
        
        # Log activity
        await logActivity(
            user,
            "Candidate Rejected",
            f"Rejected candidate: {request.reason}",
            "Warning"
        )
        
        return {
            "message": "Candidate rejected successfully",
            "interviewId": interview.get("_id"),
            "interview": interview
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error rejecting candidate: {str(e)}"
        )


@router.post(
    "/markAsHired",
    summary="Mark Candidate as Hired",
    description="""
    **Purpose:** Mark candidate as hired after offer acceptance.
    
    **Role Access:** ORG_HR, SPOC only
    
    **Request Body:**
    ```json
    {
      "interviewId": "6a0031bf651c6dea3f1acda9"
    }
    ```
    
    **Response Example:**
    ```json
    {
      "message": "Candidate marked as hired successfully",
      "interviewId": "6a0031bf651c6dea3f1acda9",
      "interview": {
        "interviewId": "6a0031bf651c6dea3f1acda9",
        "overallStatus": "Hired",
        "offerExtended": true,
        "hired": true,
        "hiredAt": "2026-05-16T09:00:00Z",
        "hiredBy": "hr@company.com"
      }
    }
    ```
    
    **Validation:**
    - Offer must be extended first
    - Cannot hire rejected candidates
    
    **Behavior:**
    - Updates status to "Hired"
    - Enables BGV initiation
    """,
    responses={
        200: {"description": "Candidate marked as hired"},
        400: {"description": "Validation error"},
        403: {"description": "Unauthorized"},
        404: {"description": "Interview not found"}
    }
)
async def mark_as_hired(
    request: MarkAsHiredRequest,
    user: dict = Depends(requireAuth)
):
    """Mark as hired"""
    
    role = user.get("role")
    
    # Access control
    if role not in ["ORG_HR", "SPOC"]:
        raise HTTPException(
            status_code=403,
            detail="Only ORG_HR and SPOC can mark as hired"
        )
    
    user_org_id = user.get("organizationId")
    user_email = user.get("email")
    
    try:
        interview = await interview_service.mark_as_hired(
            interview_id=request.interviewId,
            user_org_id=user_org_id,
            user_email=user_email
        )
        
        # Serialize datetime fields
        interview = serialize_interview_datetime(interview)
        
        # Log activity
        await logActivity(
            user,
            "Candidate Hired",
            f"Marked candidate as hired for interview {request.interviewId}",
            "Success"
        )
        
        return {
            "message": "Candidate marked as hired successfully",
            "interviewId": interview.get("_id"),
            "interview": interview
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error marking as hired: {str(e)}"
        )


@router.post(
    "/initiateBGV",
    summary="Initiate Background Verification",
    description="""
    **Purpose:** Create candidate entry in candidates collection for BGV with auto-filled data.
    
    **Role Access:** ORG_HR, SPOC only
    
    **Request Body:**
    ```json
    {
      "interviewId": "6a0031bf651c6dea3f1acda9"
    }
    ```
    
    **Response Example:**
    ```json
    {
      "message": "BGV initiated successfully",
      "candidateId": "6a0032bf651c6dea3f1acdaa"
    }
    ```
    
    **Auto-Fill Feature:**
    The system automatically pre-fills candidate data from job seeker profile:
    
    **Always Auto-Filled (18 fields):**
    - ✅ Name → firstName, lastName (auto-split)
    - ✅ Email
    - ✅ Phone
    - ✅ **DOB** (Date of Birth)
    - ✅ **Gender** (Male/Female/Other)
    - ✅ **Father's Name**
    - ✅ **Permanent Address** → address
    - ✅ **District**
    - ✅ **State**
    - ✅ **Pincode**
    - ✅ **Marital Status**
    - ✅ Nationality (if provided)
    - ✅ Mother's Name (if provided)
    - ✅ PAN Number (if provided)
    - ✅ Aadhaar Number (if provided)
    - ✅ Passport Number (if provided)
    - ✅ Driving License (if provided)
    - ✅ Resume URL
    
    **Still Requires Manual Entry:**
    - UAN Number only
    
    **What Happens:**
    1. Validates candidate is hired
    2. Checks for duplicate email in organization
    3. Fetches job seeker profile data
    4. Creates candidate entry with **auto-filled fields**
    5. Links to interview, application, job
    6. Returns candidateId for BGV form
    
    **Benefits:**
    - ⚡ Saves 5-10 minutes per candidate
    - ✅ No manual data entry for pre-filled fields
    - ✅ Reduces errors
    - ✅ Faster onboarding
    
    **Validation:**
    - Candidate must be hired first
    - Cannot initiate BGV twice for same candidate
    - Email must be unique within organization
    
    **Behavior:**
    - Creates entry in existing `candidates` collection
    - Pre-fills 15+ fields from job seeker profile
    - Returns candidateId for further processing
    """,
    responses={
        200: {
            "description": "BGV initiated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "message": "BGV initiated successfully",
                        "candidateId": "6a0032bf651c6dea3f1acdaa"
                    }
                }
            }
        },
        400: {
            "description": "Validation error",
            "content": {
                "application/json": {
                    "examples": {
                        "not_hired": {
                            "summary": "Candidate not hired",
                            "value": {"detail": "Candidate must be hired before initiating BGV"}
                        },
                        "already_initiated": {
                            "summary": "BGV already initiated",
                            "value": {"detail": "BGV already initiated for this candidate"}
                        },
                        "duplicate_email": {
                            "summary": "Duplicate email",
                            "value": {"detail": "A candidate with email arjun@gmail.com already exists in your organization's BGV system"}
                        }
                    }
                }
            }
        },
        403: {"description": "Unauthorized - Only ORG_HR and SPOC can initiate BGV"},
        404: {"description": "Interview not found"}
    }
)
async def initiate_bgv(
    request: InitiateBGVRequest,
    user: dict = Depends(requireAuth)
):
    """Initiate BGV"""
    
    role = user.get("role")
    
    # Access control
    if role not in ["ORG_HR", "SPOC"]:
        raise HTTPException(
            status_code=403,
            detail="Only ORG_HR and SPOC can initiate BGV"
        )
    
    user_org_id = user.get("organizationId")
    user_email = user.get("email")
    
    try:
        result = await interview_service.initiate_bgv(
            interview_id=request.interviewId,
            user_org_id=user_org_id,
            user_email=user_email
        )
        
        # Log activity
        await logActivity(
            user,
            "BGV Initiated",
            f"Initiated BGV for interview {request.interviewId}, Candidate ID: {result['candidateId']}",
            "Success"
        )
        
        return {
            "message": result["message"],
            "candidateId": result["candidateId"]
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error initiating BGV: {str(e)}"
        )


@router.get(
    "/getInterviews",
    summary="Get All Interviews for Job",
    description="""
    **Purpose:** Get all interviews for a specific job.
    
    **Role Access:** ORG_HR, SPOC, HELPER (read-only)
    
    **Query Parameters:**
    - `jobId` (required) - Job ID
    
    **Response Example:**
    ```json
    {
      "interviews": [
        {
          "interviewId": "6a0031bf651c6dea3f1acda9",
          "applicationId": "6a00314a651c6dea3f1acda8",
          "jobSeekerId": "69ff264f1bd50eeba0e601f5",
          "jobId": "6a0028c89d57fa3ca6a76444",
          "orgId": "6922aaeadc43986902ed7169",
          "jobSeekerName": "Vamsi Vakada",
          "jobSeekerEmail": "vamsivakada163@gmail.com",
          "jobSeekerPhone": "8331086719",
          "resumeUrl": "https://res.cloudinary.com/dxbjp7jno/raw/upload/...",
          "profileCompletion": 85,
          "rounds": [
            {
              "roundNumber": 1,
              "roundName": "Tech Round",
              "interviewerId": null,
              "interviewer": null,
              "interviewerEmail": null,
              "scheduledAt": null,
              "status": "Passed",
              "rating": 4,
              "feedback": "Strong technical skills",
              "completedAt": "2026-05-12T11:30:00Z",
              "updatedBy": "hr@company.com",
              "updatedAt": "2026-05-12T11:30:00Z"
            },
            {
              "roundNumber": 2,
              "roundName": "Manager Round",
              "interviewerId": "6a0032bf651c6dea3f1acdaa",
              "interviewer": "Priya Sharma",
              "interviewerEmail": "priya@company.com",
              "scheduledAt": "2026-05-12T10:00:00Z",
              "status": "Scheduled",
              "rating": null,
              "feedback": "",
              "completedAt": null,
              "updatedBy": "hr@company.com",
              "updatedAt": "2026-05-12T09:00:00Z"
            },
            {
              "roundNumber": 3,
              "roundName": "HR Round",
              "interviewerId": null,
              "interviewer": null,
              "interviewerEmail": null,
              "scheduledAt": null,
              "status": "Pending",
              "rating": null,
              "feedback": "",
              "completedAt": null,
              "updatedBy": null,
              "updatedAt": null
            },
            {
              "roundNumber": 4,
              "roundName": "Final Round",
              "interviewerId": null,
              "interviewer": null,
              "interviewerEmail": null,
              "scheduledAt": null,
              "status": "Pending",
              "rating": null,
              "feedback": "",
              "completedAt": null,
              "updatedBy": null,
              "updatedAt": null
            }
          ],
          "currentRound": 2,
          "overallStatus": "In Progress",
          "offerExtended": false,
          "offerExtendedAt": null,
          "offerExtendedBy": null,
          "rejected": false,
          "rejectedAt": null,
          "rejectedBy": null,
          "rejectionReason": "",
          "rejectedAtRound": null,
          "hired": false,
          "hiredAt": null,
          "hiredBy": null,
          "bgvInitiated": false,
          "bgvInitiatedAt": null,
          "bgvInitiatedBy": null,
          "candidateId": null,
          "createdAt": "2026-05-10T07:20:31Z",
          "createdBy": "hr@company.com",
          "updatedAt": "2026-05-11T14:30:00Z",
          "isDeleted": false
        },
        {
          "interviewId": "6a0031bf651c6dea3f1acdab",
          "applicationId": "6a00314a651c6dea3f1acda9",
          "jobSeekerId": "69ff264f1bd50eeba0e601f6",
          "jobId": "6a0028c89d57fa3ca6a76444",
          "orgId": "6922aaeadc43986902ed7169",
          "jobSeekerName": "Tulasi Killani",
          "jobSeekerEmail": "tulasikillani07@gmail.com",
          "jobSeekerPhone": "9515714566",
          "resumeUrl": "https://res.cloudinary.com/dxbjp7jno/raw/upload/...",
          "profileCompletion": 50,
          "rounds": [
            {
              "roundNumber": 1,
              "roundName": "Tech Round",
              "status": "Pending"
            }
          ],
          "currentRound": 1,
          "overallStatus": "In Progress",
          "offerExtended": false,
          "rejected": false,
          "hired": false,
          "bgvInitiated": false,
          "createdAt": "2026-05-10T08:15:22Z",
          "updatedAt": "2026-05-10T08:15:22Z",
          "isDeleted": false
        }
      ],
      "total": 2
    }
    ```
    
    **Important Notes:**
    - Each interview has `interviewId` field (MongoDB `_id` renamed for clarity)
    - No redundant `_id` field in response
    - Includes job seeker details: name, email, phone, resume URL, profile completion
    - Returns all interviews for the specified job
    - Sorted by creation date (newest first)
    - Includes complete round details and status
    
    **Use Case:** HR views all interviews for a job to track progress
    """,
    response_model=InterviewListResponse
)
async def get_interviews(
    jobId: str = Query(..., description="Job ID"),
    user: dict = Depends(requireAuth)
):
    """Get interviews for job"""
    
    user_org_id = user.get("organizationId")
    
    try:
        interviews = await interview_service.get_interviews_for_job(
            job_id=jobId,
            user_org_id=user_org_id
        )
        
        # Serialize datetime fields and rename _id to interviewId
        for interview in interviews:
            serialize_interview_datetime(interview)
            # Rename _id to interviewId for clarity (remove redundant _id)
            interview["interviewId"] = interview.pop("_id")
        
        return {
            "interviews": interviews,
            "total": len(interviews)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching interviews: {str(e)}"
        )


@router.get(
    "/getAllInterviews",
    summary="Get All Interviews (All Jobs)",
    description="""
    **Purpose:** Get all interviews across all jobs with optional filters.
    
    **Role Access:** ORG_HR, SPOC, HELPER (read-only)
    
    **Query Parameters:**
    - `status` (optional) - Filter by overall status
      - "In Progress" - Interview ongoing
      - "Completed" - All rounds completed
      - "Offer Extended" - Offer extended to candidate
      - "Rejected" - Candidate rejected
      - "Hired" - Candidate hired
    - `jobId` (optional) - Filter by specific job ID
    
    **Response Example:**
    ```json
    {
      "interviews": [
        {
          "interviewId": "6a0031bf651c6dea3f1acda9",
          "applicationId": "6a00314a651c6dea3f1acda8",
          "jobSeekerId": "69ff264f1bd50eeba0e601f5",
          "jobId": "6a0028c89d57fa3ca6a76444",
          "orgId": "6922aaeadc43986902ed7169",
          "jobSeekerName": "Arjun Kumar",
          "jobSeekerEmail": "arjun@example.com",
          "jobSeekerPhone": "9876543210",
          "resumeUrl": "https://res.cloudinary.com/dxbjp7jno/raw/upload/...",
          "profileCompletion": 90,
          "rounds": [
            {
              "roundNumber": 1,
              "roundName": "Tech Round",
              "interviewerId": "6a0032bf651c6dea3f1acdaa",
              "interviewer": "Priya Sharma",
              "interviewerEmail": "priya@company.com",
              "scheduledAt": "2026-05-12T10:00:00Z",
              "status": "Scheduled",
              "rating": null,
              "feedback": "",
              "completedAt": null,
              "updatedBy": "hr@company.com",
              "updatedAt": "2026-05-12T09:00:00Z"
            }
          ],
          "currentRound": 1,
          "overallStatus": "In Progress",
          "offerExtended": false,
          "offerExtendedAt": null,
          "offerExtendedBy": null,
          "rejected": false,
          "rejectedAt": null,
          "rejectedBy": null,
          "rejectionReason": "",
          "rejectedAtRound": null,
          "hired": false,
          "hiredAt": null,
          "hiredBy": null,
          "bgvInitiated": false,
          "bgvInitiatedAt": null,
          "bgvInitiatedBy": null,
          "candidateId": null,
          "createdAt": "2026-05-10T07:20:31Z",
          "createdBy": "hr@company.com",
          "updatedAt": "2026-05-11T14:30:00Z",
          "isDeleted": false
        }
      ],
      "total": 1,
      "statusCounts": {
        "In Progress": 15,
        "Completed": 5,
        "Offer Extended": 3,
        "Rejected": 8,
        "Hired": 2
      }
    }
    ```
    
    **Important Notes:**
    - Each interview has `interviewId` field (MongoDB `_id` renamed for clarity)
    - Includes job seeker details: name, email, phone, resume URL, profile completion
    - Returns `statusCounts` for dashboard visualization
    - Supports filtering by status and jobId
    - Sorted by creation date (newest first)
    
    **Use Cases:**
    - Dashboard: View all ongoing interviews
    - Filter scheduled interviews for today
    - View all rejected candidates
    - Track hiring pipeline across all jobs
    - Monitor interview progress
    
    **Filters:**
    - No filters: Returns all interviews
    - `status=In Progress`: Only ongoing interviews
    - `status=Rejected`: Only rejected candidates
    - `jobId=XXX`: Only interviews for specific job
    - Combine filters: `status=In Progress&jobId=XXX`
    """,
    response_model=InterviewListResponse
)
async def get_all_interviews(
    status: Optional[str] = Query(None, description="Filter by overall status"),
    jobId: Optional[str] = Query(None, description="Filter by job ID"),
    user: dict = Depends(requireAuth)
):
    """Get all interviews across all jobs"""
    
    user_org_id = user.get("organizationId")
    
    try:
        interviews = await interview_service.get_all_interviews(
            user_org_id=user_org_id,
            status=status,
            job_id=jobId
        )
        
        # Serialize datetime fields and rename _id to interviewId
        for interview in interviews:
            serialize_interview_datetime(interview)
            # Rename _id to interviewId for clarity (remove redundant _id)
            interview["interviewId"] = interview.pop("_id")
        
        # Calculate status counts
        status_counts = {}
        for interview in interviews:
            interview_status = interview.get("overallStatus", "Unknown")
            status_counts[interview_status] = status_counts.get(interview_status, 0) + 1
        
        return {
            "interviews": interviews,
            "total": len(interviews),
            "statusCounts": status_counts
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching interviews: {str(e)}"
        )
