"""
Routes for Interviewer Management
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

# Import from core
from core.dependencies import requireAuth, logActivity

# Import from current module
from .service import InterviewerService
from .schemas import (
    InterviewerCreate,
    InterviewerUpdate,
    InterviewerDelete,
    InterviewerResponse,
    InterviewerListResponse
)

# Initialize router
router = APIRouter(prefix="/secure", tags=["Interviewer Management"])

# Initialize service
interviewer_service = InterviewerService()


def serialize_interviewer_datetime(interviewer: dict) -> dict:
    """
    Serialize datetime fields in interviewer object to ISO format strings
    
    Args:
        interviewer: Interviewer dictionary
        
    Returns:
        Interviewer with serialized datetime fields
    """
    from datetime import datetime
    
    for key, value in list(interviewer.items()):
        if isinstance(value, datetime):
            interviewer[key] = value.isoformat()
    
    return interviewer


@router.post(
    "/createInterviewer",
    summary="Create Interviewer",
    description="""
    **Purpose:** Create a new interviewer profile.
    
    **Role Access:** ORG_HR, SPOC only
    
    **Request Body Example:**
    ```json
    {
      "name": "Priya Sharma",
      "email": "priya@company.com",
      "phone": "+91-9876543210",
      "designation": "Senior Technical Lead",
      "department": "Engineering",
      "expertise": ["Python", "FastAPI", "System Design", "Microservices"],
      "roundPreferences": [1, 2],
      "availabilityNotes": "Available Mon-Fri, 10 AM - 5 PM"
    }
    ```
    
    **Response Example:**
    ```json
    {
      "message": "Interviewer created successfully",
      "interviewerId": "6a0032bf651c6dea3f1acdaa",
      "interviewer": {
        "interviewerId": "6a0032bf651c6dea3f1acdaa",
        "_id": "6a0032bf651c6dea3f1acdaa",
        "name": "Priya Sharma",
        "email": "priya@company.com",
        "phone": "+91-9876543210",
        "designation": "Senior Technical Lead",
        "department": "Engineering",
        "organizationId": "6922aaeadc43986902ed7169",
        "organizationName": "TechCorp",
        "expertise": ["Python", "FastAPI", "System Design", "Microservices"],
        "roundPreferences": [1, 2],
        "isActive": true,
        "isAvailable": true,
        "availabilityNotes": "Available Mon-Fri, 10 AM - 5 PM",
        "stats": {
          "totalInterviewsConducted": 0,
          "upcomingInterviews": 0,
          "averageRating": null,
          "passRate": null
        },
        "createdAt": "2026-05-10T10:00:00Z",
        "updatedAt": "2026-05-10T10:00:00Z"
      }
    }
    ```
    
    **Validation:**
    - Email must be unique within organization
    - Phone number must be 10-15 digits
    - Round preferences must be 1-4
    
    **Use Case:** HR adds interviewer to the system for scheduling interviews
    """,
    responses={
        201: {"description": "Interviewer created successfully"},
        400: {"description": "Validation error or duplicate email"},
        403: {"description": "Unauthorized"}
    }
)
async def create_interviewer(
    request: InterviewerCreate,
    user: dict = Depends(requireAuth)
):
    """Create interviewer"""
    
    role = user.get("role")
    
    # Access control
    if role not in ["ORG_HR", "SPOC"]:
        raise HTTPException(
            status_code=403,
            detail="Only ORG_HR and SPOC can create interviewers"
        )
    
    user_org_id = user.get("organizationId")
    user_email = user.get("email")
    
    try:
        interviewer = await interviewer_service.create_interviewer(
            name=request.name,
            email=request.email,
            phone=request.phone,
            designation=request.designation,
            department=request.department,
            expertise=request.expertise,
            round_preferences=request.roundPreferences,
            availability_notes=request.availabilityNotes,
            org_id=user_org_id,
            user_email=user_email
        )
        
        # Serialize datetime fields
        interviewer = serialize_interviewer_datetime(interviewer)
        
        # Log activity
        await logActivity(
            user,
            "Interviewer Created",
            f"Created interviewer {request.name} ({request.email})",
            "Info"
        )
        
        return {
            "message": "Interviewer created successfully",
            "interviewerId": interviewer.get("interviewerId"),
            "interviewer": interviewer
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error creating interviewer: {str(e)}"
        )


@router.get(
    "/getInterviewers",
    summary="Get All Interviewers",
    description="""
    **Purpose:** Get all interviewers for the organization with optional filters.
    
    **Role Access:** ORG_HR, SPOC, HELPER (read-only)
    
    **Query Parameters:**
    - `isActive` (optional) - Filter by active status (true/false)
    - `isAvailable` (optional) - Filter by availability (true/false)
    - `department` (optional) - Filter by department name
    
    **Response Example:**
    ```json
    {
      "interviewers": [
        {
          "interviewerId": "6a0032bf651c6dea3f1acdaa",
          "_id": "6a0032bf651c6dea3f1acdaa",
          "name": "Priya Sharma",
          "email": "priya@company.com",
          "phone": "+91-9876543210",
          "designation": "Senior Technical Lead",
          "department": "Engineering",
          "expertise": ["Python", "FastAPI", "System Design"],
          "roundPreferences": [1, 2],
          "isActive": true,
          "isAvailable": true,
          "availabilityNotes": "Available Mon-Fri, 10 AM - 5 PM",
          "stats": {
            "totalInterviewsConducted": 45,
            "upcomingInterviews": 3,
            "averageRating": 4.2,
            "passRate": 0.65
          }
        }
      ],
      "total": 1
    }
    ```
    
    **Use Cases:**
    - Display all interviewers in dashboard
    - Filter available interviewers for scheduling
    - Filter by department for specific roles
    """,
    response_model=InterviewerListResponse
)
async def get_interviewers(
    isActive: Optional[bool] = Query(None, description="Filter by active status"),
    isAvailable: Optional[bool] = Query(None, description="Filter by availability"),
    department: Optional[str] = Query(None, description="Filter by department"),
    user: dict = Depends(requireAuth)
):
    """Get all interviewers"""
    
    user_org_id = user.get("organizationId")
    
    try:
        interviewers = await interviewer_service.get_interviewers(
            org_id=user_org_id,
            is_active=isActive,
            is_available=isAvailable,
            department=department
        )
        
        # Serialize datetime fields for all interviewers
        for interviewer in interviewers:
            serialize_interviewer_datetime(interviewer)
        
        return {
            "interviewers": interviewers,
            "total": len(interviewers)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching interviewers: {str(e)}"
        )


@router.get(
    "/getInterviewer/{interviewerId}",
    summary="Get Interviewer Details",
    description="""
    **Purpose:** Get detailed information about a specific interviewer.
    
    **Role Access:** ORG_HR, SPOC, HELPER (read-only)
    
    **Response Example:**
    ```json
    {
      "interviewerId": "6a0032bf651c6dea3f1acdaa",
      "_id": "6a0032bf651c6dea3f1acdaa",
      "name": "Priya Sharma",
      "email": "priya@company.com",
      "phone": "+91-9876543210",
      "designation": "Senior Technical Lead",
      "department": "Engineering",
      "organizationId": "6922aaeadc43986902ed7169",
      "organizationName": "TechCorp",
      "expertise": ["Python", "FastAPI", "System Design", "Microservices"],
      "roundPreferences": [1, 2],
      "isActive": true,
      "isAvailable": true,
      "availabilityNotes": "Available Mon-Fri, 10 AM - 5 PM",
      "stats": {
        "totalInterviewsConducted": 45,
        "upcomingInterviews": 3,
        "averageRating": 4.2,
        "passRate": 0.65
      },
      "createdAt": "2026-05-10T10:00:00Z",
      "updatedAt": "2026-05-10T10:00:00Z"
    }
    ```
    
    **Statistics Explained:**
    - `totalInterviewsConducted`: Total completed interview rounds
    - `upcomingInterviews`: Scheduled or pending rounds
    - `averageRating`: Average rating given by this interviewer
    - `passRate`: Percentage of candidates passed by this interviewer
    
    **Use Case:** View interviewer profile and performance metrics
    """,
    response_model=InterviewerResponse
)
async def get_interviewer(
    interviewerId: str,
    user: dict = Depends(requireAuth)
):
    """Get interviewer details"""
    
    user_org_id = user.get("organizationId")
    
    try:
        interviewer = await interviewer_service.get_interviewer_by_id(
            interviewer_id=interviewerId,
            org_id=user_org_id
        )
        
        if not interviewer:
            raise HTTPException(
                status_code=404,
                detail="Interviewer not found or access denied"
            )
        
        # Serialize datetime fields
        interviewer = serialize_interviewer_datetime(interviewer)
        
        return interviewer
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching interviewer: {str(e)}"
        )


@router.put(
    "/updateInterviewer/{interviewerId}",
    summary="Update Interviewer",
    description="""
    **Purpose:** Update interviewer details.
    
    **Role Access:** ORG_HR, SPOC only
    
    **Request Body Example:**
    ```json
    {
      "name": "Priya Sharma",
      "phone": "+91-9876543210",
      "designation": "Principal Engineer",
      "department": "Engineering",
      "expertise": ["Python", "FastAPI", "System Design", "Microservices", "AWS"],
      "roundPreferences": [1, 2, 4],
      "isAvailable": false,
      "availabilityNotes": "On leave until May 20"
    }
    ```
    
    **Response Example:**
    ```json
    {
      "message": "Interviewer updated successfully",
      "interviewer": {
        "interviewerId": "6a0032bf651c6dea3f1acdaa",
        "name": "Priya Sharma",
        "designation": "Principal Engineer",
        "isAvailable": false,
        "availabilityNotes": "On leave until May 20",
        "updatedAt": "2026-05-10T15:30:00Z"
      }
    }
    ```
    
    **Note:** Email cannot be updated (use delete and create new if needed)
    
    **Use Cases:**
    - Update interviewer availability
    - Update expertise/skills
    - Update contact information
    - Mark as unavailable during leave
    """,
    responses={
        200: {"description": "Interviewer updated successfully"},
        403: {"description": "Unauthorized"},
        404: {"description": "Interviewer not found"}
    }
)
async def update_interviewer(
    interviewerId: str,
    request: InterviewerUpdate,
    user: dict = Depends(requireAuth)
):
    """Update interviewer"""
    
    role = user.get("role")
    
    # Access control
    if role not in ["ORG_HR", "SPOC"]:
        raise HTTPException(
            status_code=403,
            detail="Only ORG_HR and SPOC can update interviewers"
        )
    
    user_org_id = user.get("organizationId")
    user_email = user.get("email")
    
    try:
        # Build update data
        update_data = request.dict(exclude_unset=True)
        
        interviewer = await interviewer_service.update_interviewer(
            interviewer_id=interviewerId,
            org_id=user_org_id,
            update_data=update_data,
            user_email=user_email
        )
        
        if not interviewer:
            raise HTTPException(
                status_code=404,
                detail="Interviewer not found or access denied"
            )
        
        # Serialize datetime fields
        interviewer = serialize_interviewer_datetime(interviewer)
        
        # Log activity
        await logActivity(
            user,
            "Interviewer Updated",
            f"Updated interviewer {interviewerId}",
            "Info"
        )
        
        return {
            "message": "Interviewer updated successfully",
            "interviewer": interviewer
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error updating interviewer: {str(e)}"
        )


@router.delete(
    "/deleteInterviewer/{interviewerId}",
    summary="Delete Interviewer",
    description="""
    **Purpose:** Soft delete an interviewer.
    
    **Role Access:** ORG_HR, SPOC only
    
    **Response Example:**
    ```json
    {
      "message": "Interviewer deleted successfully"
    }
    ```
    
    **Validation:**
    - Cannot delete interviewer with upcoming interviews
    - Soft delete (marked as deleted, not removed from database)
    
    **Use Case:** Remove interviewer who left the company
    """,
    responses={
        200: {"description": "Interviewer deleted successfully"},
        400: {"description": "Cannot delete - has upcoming interviews"},
        403: {"description": "Unauthorized"},
        404: {"description": "Interviewer not found"}
    }
)
async def delete_interviewer(
    interviewerId: str,
    user: dict = Depends(requireAuth)
):
    """Delete interviewer"""
    
    role = user.get("role")
    
    # Access control
    if role not in ["ORG_HR", "SPOC"]:
        raise HTTPException(
            status_code=403,
            detail="Only ORG_HR and SPOC can delete interviewers"
        )
    
    user_org_id = user.get("organizationId")
    user_email = user.get("email")
    
    try:
        success = await interviewer_service.delete_interviewer(
            interviewer_id=interviewerId,
            org_id=user_org_id,
            user_email=user_email
        )
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail="Interviewer not found or access denied"
            )
        
        # Log activity
        await logActivity(
            user,
            "Interviewer Deleted",
            f"Deleted interviewer {interviewerId}",
            "Warning"
        )
        
        return {"message": "Interviewer deleted successfully"}
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting interviewer: {str(e)}"
        )
