"""
Routes for bulk candidate upload feature
"""
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from fastapi.responses import StreamingResponse
import io
from bson import ObjectId

# Import from core
from core.database import orgsCol

# Import from main (existing functions)
from main import requireAuth, logActivity

# Import from current module
from .service import BulkUploadService
from .schemas import BulkUploadResponse

# Initialize router
router = APIRouter(prefix="/secure", tags=["Candidates - Bulk Upload"])

# Initialize service
bulk_upload_service = BulkUploadService()


@router.get(
    "/downloadCandidateTemplate",
    summary="Download CSV Template for Bulk Upload",
    description="""
    **Purpose:** Download a CSV template file for bulk candidate upload.
    
    **Use Case:** Before uploading candidates in bulk, download this template to see the exact format required.
    
    **Key Features:**
    - ✅ Returns CSV file with all required columns only
    - ✅ Includes sample data row for reference
    - ✅ Ready to fill and upload
    
    **CSV Columns Included:**
    - **Required:** firstName, lastName, phone, email, aadhaarNumber, panNumber, fatherName, dob, gender, address, district, state, pincode
    
    **Workflow:**
    1. Download template → Fill candidate data → Upload via bulk upload endpoint
    """,
    responses={
        200: {
            "description": "CSV template file downloaded successfully",
            "content": {
                "text/csv": {
                    "example": "firstName,lastName,phone,email,aadhaarNumber,panNumber,fatherName,dob,gender,address,district,state,pincode\nJohn,Doe,9876543210,john@example.com,123456789012,ABCDE1234F,Robert Doe,1990-01-15,Male,123 Main St,Mumbai,Maharashtra,400001"
                }
            }
        },
        401: {"description": "Unauthorized - Invalid or missing token"}
    }
)
async def download_candidate_template(user: dict = Depends(requireAuth)):
    """Download CSV template for bulk candidate upload"""
    
    # Generate CSV template using service
    csv_content = bulk_upload_service.generate_csv_template()
    
    # Return as downloadable file
    return StreamingResponse(
        io.BytesIO(csv_content.encode('utf-8')),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=candidate_bulk_upload_template.csv"}
    )


@router.post(
    "/bulkUploadCandidates",
    summary="Bulk Upload Candidates via CSV",
    response_model=BulkUploadResponse,
    description="""
    **Purpose:** Upload multiple candidates at once using a CSV file.
    
    **Use Case:** Efficiently add hundreds of candidates in a single operation instead of adding them one by one.
    
    **Key Features:**
    - ✅ Upload up to 1000 candidates per CSV file
    - ✅ Automatic duplicate detection (email/PAN/Aadhaar)
    - ✅ Detailed success/failure report for each row
    - ✅ Continues processing even if some rows fail
    - ✅ Role-based organization assignment
    
    **Role-Based Behavior:**
    - **SUPER_ADMIN/SUPER_SPOC:** Must provide `organizationId` (can upload to any org)
    - **SUPER_ADMIN_HELPER:** Must provide `organizationId` (only accessible orgs)
    - **ORG_HR/SPOC/HELPER:** `organizationId` auto-assigned from user profile
    
    **CSV Requirements:**
    - **Format:** UTF-8 encoded CSV file
    - **Max Rows:** 1000 candidates per upload
    - **Required Columns:** firstName, lastName, phone, email, aadhaarNumber, panNumber, fatherName, dob, gender, address, district, state, pincode
    
    **Duplicate Handling:**
    - Candidates with existing email, PAN, or Aadhaar will be skipped
    - Skipped rows will be reported in the `failedRows` array
    
    **Response:**
    - Returns summary with total/successful/failed counts
    - Lists all successful candidates with their IDs
    - Lists all failed rows with error messages
    
    **Workflow:**
    1. Download template via GET /secure/downloadCandidateTemplate
    2. Fill in candidate data
    3. Upload CSV file (+ organizationId if required)
    4. Review success/failure report
    5. Fix failed rows and re-upload if needed
    """,
    responses={
        201: {
            "description": "Bulk upload completed with detailed report",
            "content": {
                "application/json": {
                    "example": {
                        "status": "completed",
                        "summary": {
                            "totalRows": 100,
                            "successful": 95,
                            "failed": 5
                        },
                        "successfulCandidates": [
                            {
                                "row": 2,
                                "candidateId": "507f1f77bcf86cd799439011",
                                "name": "John Doe",
                                "email": "john@example.com"
                            }
                        ],
                        "failedRows": [
                            {
                                "row": 23,
                                "data": {"firstName": "Jane", "lastName": "Smith"},
                                "error": "Duplicate candidate - email already exists"
                            }
                        ]
                    }
                }
            }
        },
        400: {"description": "Bad Request - Invalid CSV format or missing required fields"},
        403: {"description": "Forbidden - Unauthorized organization access"},
        404: {"description": "Organization not found"}
    }
)
async def bulk_upload_candidates(
    file: UploadFile = File(..., description="CSV file containing candidate data (max 1000 rows)"),
    organizationId: str = Form(None, description="Organization ID (required for SUPER_ADMIN/SUPER_SPOC/SUPER_ADMIN_HELPER)"),
    user: dict = Depends(requireAuth)
):
    """Bulk upload candidates via CSV file"""
    
    role = user.get("role")
    creator_email = user.get("email")
    accessible_orgs = user.get("accessibleOrganizations", [])
    
    # Validate file type
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")
    
    # ------------------------
    # 🔐 Role-based Organization Handling
    # ------------------------
    org_id = None
    org_name = None
    
    if role in ["SUPER_ADMIN", "SUPER_SPOC"]:
        if not organizationId:
            raise HTTPException(status_code=400, detail="Organization ID required for Super Admin")
        org_id = organizationId
        org = await orgsCol.find_one({"_id": ObjectId(org_id)})
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")
        org_name = org.get("organizationName")
    
    elif role == "SUPER_ADMIN_HELPER":
        if not organizationId:
            raise HTTPException(status_code=400, detail="Organization ID required")
        if organizationId not in accessible_orgs:
            raise HTTPException(status_code=403, detail="You are not authorized for this organization")
        org_id = organizationId
        org = await orgsCol.find_one({"_id": ObjectId(org_id)})
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")
        org_name = org.get("organizationName")
    
    elif role in ["ORG_HR", "SPOC"]:
        org_id = user.get("organizationId")
        if not org_id:
            raise HTTPException(status_code=400, detail="Organization ID missing for HR/SPOC")
        org = await orgsCol.find_one({"_id": ObjectId(org_id)})
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")
        org_name = org.get("organizationName")
    
    elif role == "HELPER":
        if "candidate:create" not in user.get("permissions", []):
            raise HTTPException(status_code=403, detail="You don't have permission to add candidates")
        org_id = user.get("organizationId")
        if not org_id:
            raise HTTPException(status_code=400, detail="Organization ID missing for helper")
        org = await orgsCol.find_one({"_id": ObjectId(org_id)})
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")
        org_name = org.get("organizationName")
    
    else:
        raise HTTPException(status_code=403, detail="Unauthorized role")
    
    # ------------------------
    # 📄 Process CSV Upload
    # ------------------------
    try:
        file_content = await file.read()
        result = await bulk_upload_service.process_csv_upload(
            file_content,
            org_id,
            org_name,
            creator_email
        )
        
        # Log activity
        await logActivity(
            user,
            "Bulk Candidate Upload",
            f"Uploaded {result['summary']['successful']} candidates to {org_name}. Failed: {result['summary']['failed']}",
            "Info"
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing CSV: {str(e)}")
