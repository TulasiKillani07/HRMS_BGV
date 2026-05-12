"""
Routes for AI Screening
"""
from fastapi import APIRouter, Depends, HTTPException

# Import from main
from main import requireAuth, logActivity

# Import from current module
from .service import AIScreeningService
from .schemas import AIScreeningRequest, AIScreeningResponse

# Initialize router
router = APIRouter(prefix="/secure", tags=["AI Screening"])

# Initialize service
ai_screening_service = AIScreeningService()


@router.post(
    "/runAIScreening",
    summary="Run AI Screening on Job Applications",
    description="""
    **Purpose:** Run AI-powered resume screening on job applications with score filtering.
    
    **Role Access:** ORG_HR, SPOC only (HELPER cannot run screening)
    
    **Request Body Example 1 (Filter by Score - 60% or higher):**
    ```json
    {
      "jobId": "6a0028c89d57fa3ca6a76444",
      "minScorePercentage": 60
    }
    ```
    Returns all candidates with 60% or higher score.
    
    **Request Body Example 2 (Filter by Score + Limit Results):**
    ```json
    {
      "jobId": "6a0028c89d57fa3ca6a76444",
      "minScorePercentage": 60,
      "topN": 10
    }
    ```
    Returns top 10 candidates with 60% or higher score.
    
    **Request Body Example 3 (Top N Only):**
    ```json
    {
      "jobId": "6a0028c89d57fa3ca6a76444",
      "topN": 15
    }
    ```
    Returns top 15 candidates regardless of score.
    
    **Request Body Example 4 (Screen Specific Applications):**
    ```json
    {
      "jobId": "6a0028c89d57fa3ca6a76444",
      "applicationIds": ["6a00314a651c6dea3f1acda8", "6a00314a651c6dea3f1acda9"],
      "minScorePercentage": 50
    }
    ```
    
    **Response Example:**
    ```json
    {
      "message": "AI screening completed successfully",
      "jobId": "6a0028c89d57fa3ca6a76444",
      "jobTitle": "Senior Python Backend Developer",
      "totalApplications": 50,
      "totalProcessed": 15,
      "filteredByScore": 15,
      "minScorePercentage": 60,
      "topN": 10,
      "results": [
        {
          "applicationId": "6a00314a651c6dea3f1acda8",
          "jobSeekerId": "69ff264f1bd50eeba0e601f5",
          "jobSeekerName": "Arjun Kumar",
          "jobSeekerEmail": "arjun@example.com",
          "rank": 1,
          "finalScore": 85.5,
          "embeddingScore": 0.82,
          "llmScore": 87,
          "recommendation": "STRONG_FIT",
          "strengths": ["Strong Python development skills", "..."],
          "weaknesses": ["Limited experience with Kubernetes"],
          "explanation": "Selected as the top candidate...",
          "summary": "Arjun has strong Python and FastAPI skills...",
          "meetsCriticalRequirements": true,
          "resumeUrl": "https://res.cloudinary.com/..."
        }
      ],
      "processingTime": 45.2
    }
    ```
    
    **How It Works:**
    1. Fetches resumes from Cloudinary for job portal applications
    2. Analyzes resumes using AI (embeddings + LLM)
    3. Scores candidates based on job requirements (0-100)
    4. Filters by minimum score percentage if provided
    5. Returns top N candidates if limit specified
    6. Stores results in ai_screening_results collection
    
    **Parameters:**
    - `jobId` (required): Job ID to screen applications for
    - `minScorePercentage` (optional): Minimum score percentage (0-100). Only returns candidates with this score or higher
    - `topN` (optional): Maximum number of top candidates to return (1-100)
    - `applicationIds` (optional): Specific application IDs to screen
    
    **Use Cases:**
    - **Filter by quality:** Set `minScorePercentage: 60` to get only good candidates
    - **Limit results:** Set `topN: 10` to get top 10 candidates
    - **Both:** Set both to get top 10 candidates with 60%+ score
    - **All results:** Don't set either parameter to get all screened candidates
    
    **Cost Note:** Uses OpenAI API - HR can screen anytime but be mindful of API costs
    """,
    response_model=AIScreeningResponse,
    responses={
        200: {"description": "AI screening completed successfully"},
        400: {"description": "Invalid request or no applications to screen"},
        403: {"description": "Unauthorized - Only ORG_HR and SPOC can run screening"},
        404: {"description": "Job not found"}
    }
)
async def run_ai_screening(
    request: AIScreeningRequest,
    user: dict = Depends(requireAuth)
):
    """Run AI screening on job applications"""
    
    role = user.get("role")
    
    # Access control
    if role not in ["ORG_HR", "SPOC"]:
        raise HTTPException(
            status_code=403,
            detail="Only ORG_HR and SPOC can run AI screening"
        )
    
    user_org_id = user.get("organizationId")
    user_email = user.get("email")
    
    try:
        result = await ai_screening_service.run_ai_screening(
            job_id=request.jobId,
            user_org_id=user_org_id,
            application_ids=request.applicationIds,
            min_score_percentage=request.minScorePercentage,
            top_n=request.topN
        )
        
        # Log activity
        await logActivity(
            user,
            "AI Screening Completed",
            f"Screened {result['totalProcessed']} applications for job {result['jobTitle']}",
            "Success"
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"ERROR in runAIScreening: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error running AI screening: {str(e)}"
        )


@router.get(
    "/getScreeningResults",
    summary="Get AI Screening Results",
    description="""
    **Purpose:** Retrieve AI screening results for a job to review candidate scores.
    
    **Role Access:** ORG_HR, SPOC, HELPER (read-only)
    
    **Query Parameters:**
    - `jobId` (required): Job ID to get screening results for
    - `applicationId` (optional): Specific application ID to get results for
    
    **Response Example (All Results):**
    ```json
    {
      "message": "Screening results retrieved successfully",
      "jobId": "6a0028c89d57fa3ca6a76444",
      "jobTitle": "Senior Python Backend Developer",
      "totalResults": 10,
      "results": [
        {
          "_id": "6a00314a651c6dea3f1acdaa",
          "screeningSessionId": "6a00314a651c6dea3f1acdab",
          "jobId": "6a0028c89d57fa3ca6a76444",
          "orgId": "507f1f77bcf86cd799439012",
          "applicationId": "6a00314a651c6dea3f1acda8",
          "jobSeekerId": "69ff264f1bd50eeba0e601f5",
          "jobSeekerName": "Arjun Kumar",
          "jobSeekerEmail": "arjun@example.com",
          "rank": 1,
          "finalScore": 85.5,
          "embeddingScore": 0.82,
          "llmScore": 87,
          "recommendation": "STRONG_FIT",
          "strengths": [
            "Strong Python development skills",
            "Experience with FastAPI and REST API development"
          ],
          "weaknesses": [
            "Limited experience with Kubernetes"
          ],
          "explanation": "Selected as the top candidate...",
          "summary": "Arjun has strong Python and FastAPI skills...",
          "meetsCriticalRequirements": true,
          "resumeUrl": "https://res.cloudinary.com/...",
          "currentStage": "Applied",
          "createdAt": "2026-05-10T10:30:00.000Z",
          "createdBy": "507f1f77bcf86cd799439012"
        }
      ]
    }
    ```
    
    **Response Example (Single Application):**
    ```json
    {
      "message": "Screening results retrieved successfully",
      "jobId": "6a0028c89d57fa3ca6a76444",
      "jobTitle": "Senior Python Backend Developer",
      "totalResults": 1,
      "results": [
        {
          "applicationId": "6a00314a651c6dea3f1acda8",
          "jobSeekerName": "Arjun Kumar",
          "finalScore": 85.5,
          "recommendation": "STRONG_FIT",
          "currentStage": "Applied",
          ...
        }
      ]
    }
    ```
    
    **Use Cases:**
    - View all screening results for a job
    - View specific candidate's screening result
    - Review scores before moving to Resume Shortlist stage
    - Compare candidates based on AI scores
    
    **Next Steps After Viewing:**
    1. Review AI scores and recommendations
    2. Use `PUT /secure/updateApplicationStage` to move individual candidates to "Resume Shortlist"
    3. Use `POST /secure/bulkUpdateStage` to move multiple candidates at once
    4. Use `POST /secure/bulkShortlistApplications` for smart bulk shortlisting
    """,
    responses={
        200: {"description": "Screening results retrieved successfully"},
        400: {"description": "Invalid request"},
        403: {"description": "Unauthorized access"},
        404: {"description": "Job not found or no screening results"}
    }
)
async def get_screening_results(
    jobId: str,
    applicationId: str = None,
    user: dict = Depends(requireAuth)
):
    """Get AI screening results for a job"""
    
    role = user.get("role")
    
    # Access control
    if role not in ["ORG_HR", "SPOC", "HELPER"]:
        raise HTTPException(
            status_code=403,
            detail="Only ORG_HR, SPOC, and HELPER can view screening results"
        )
    
    user_org_id = user.get("organizationId")
    
    try:
        result = await ai_screening_service.get_screening_results(
            job_id=jobId,
            user_org_id=user_org_id,
            application_id=applicationId
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"ERROR in getScreeningResults: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving screening results: {str(e)}"
        )
