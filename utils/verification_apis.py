"""
Verification API functions for background verification checks
Moved from apis.py for better organization
"""
import asyncio
import aiohttp
from datetime import datetime, timezone
from bson import ObjectId

# ---------------------------------------------------
# 📌 Surepass Dummy Credentials (REPLACE THEM)
# ---------------------------------------------------
SUREPASS_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTc2MzgwMDM0NywianRpIjoiNjA5ZTZmOTctNTcxOS00MjA2LWEwZDAtMjc5ZmFiZTQ0ODQ1IiwidHlwZSI6ImFjY2VzcyIsImlkZW50aXR5IjoiZGV2LnRocmVzaGluZ0BzdXJlcGFzcy5pbyIsIm5iZiI6MTc2MzgwMDM0NywiZXhwIjoyMzk0NTIwMzQ3LCJlbWFpbCI6InRocmVzaGluZ0BzdXJlcGFzcy5pbyIsInRlbmFudF9pZCI6Im1haW4iLCJ1c2VyX2NsYWltcyI6eyJzY29wZXMiOlsidXNlciJdfX0.h90UBZtuKinYF4kjsJ8sGjDR0rtAXNDsDpJwS3bQAEw"
SUREPASS_CUSTOMER_ID = ""


# ---------------------------------------------------
# 📌 HTTP utility
# ---------------------------------------------------
async def post_json(url: str, headers: dict, payload: dict):
    try:
        print(f"🔵 Attempting API call to: {url}")
        print(f"🔵 Payload: {payload}")
        
        # Try with httpx first (better SSL handling)
        try:
            import httpx
            async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                print(f"✅ Response status: {resp.status_code}")
                data = resp.json()
                print(f"✅ Response data: {data}")
                
                success = resp.status_code == 200 and data.get("success", False)
                status = "COMPLETED" if success else "FAILED"
                remarks = data if not success else data.get("data", data)
                return status, remarks
        except ImportError:
            print("⚠️ httpx not available, falling back to aiohttp")
        
        # Fallback to aiohttp with SSL disabled
        import ssl
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        connector = aiohttp.TCPConnector(ssl=ssl_context, force_close=True)
        
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                print(f"✅ Response status: {resp.status}")
                data = await resp.json()
                print(f"✅ Response data: {data}")
                
                success = resp.status == 200 and data.get("success", False)
                status = "COMPLETED" if success else "FAILED"
                remarks = data if not success else data.get("data", data)
                return status, remarks

    except Exception as e:
        print(f"❌ API Error: {e}")
        return "FAILED", f"API Error: {str(e)}"


# ---------------------------------------------------
# 📌 Verification Functions
# ---------------------------------------------------
async def verify_pan_aadhaar_seeding(pan_number: str, aadhaar_number: str):
    url = "https://kyc-api.surepass.io/api/v1/pan/aadhaar-pan-link-check"
    headers = {"Authorization": f"Bearer {SUREPASS_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "pan_number": pan_number,
        "aadhaar_number": aadhaar_number
    }
    return await post_json(url, headers, payload)


async def verify_pan(pan_number: str):
    url = "https://kyc-api.surepass.io/api/v1/pan/pan"
    headers = {"Authorization": f"Bearer {SUREPASS_TOKEN}", "Content-Type": "application/json"}
    payload = {"id_number": pan_number}
    return await post_json(url, headers, payload)


async def verify_employment_history(uan_number: str):
    url = "https://kyc-api.surepass.io/api/v1/income/employment-history-uan-v2"
    headers = {"Authorization": f"Bearer {SUREPASS_TOKEN}", "Content-Type": "application/json"}
    payload = {"id_number": uan_number}
    return await post_json(url, headers, payload)


async def verify_pan_to_uan(pan_number: str):
    url = "https://kyc-api.surepass.io/api/v1/pan/pan-to-uan"
    headers = {"Authorization": f"Bearer {SUREPASS_TOKEN}", "Content-Type": "application/json"}
    payload = {"pan_number": pan_number}
    return await post_json(url, headers, payload)


async def verify_credit_report(candidate: dict):
    """
    CIBIL Credit Report verification with PDF download and S3 storage
    Downloads the temporary PDF link and stores it permanently in S3
    """
    from core.database import orgsCol
    
    url = "https://kyc-api.surepass.io/api/v1/credit-report-cibil/fetch-report-pdf"
    headers = {"Authorization": f"Bearer {SUREPASS_TOKEN}", "Content-Type": "application/json"}
    
    # Combine first name and last name, handle potential spelling variations
    first_name = candidate.get("firstName", "").strip()
    last_name = candidate.get("lastName", "").strip()
    full_name = f"{first_name} {last_name}".strip()
    
    payload = {
        "mobile": candidate.get("phone"),
        "pan": candidate.get("panNumber"),
        "name": full_name,
        "gender": candidate.get("gender", "male").lower(),
        "consent": "Y"
    }
    
    # Get the CIBIL report with temporary PDF link
    status, remarks = await post_json(url, headers, payload)
    
    print(f"🔍 CIBIL API Response - Status: {status}")
    print(f"🔍 CIBIL API Response - Remarks type: {type(remarks)}")
    if isinstance(remarks, dict):
        print(f"🔍 CIBIL API Response - Remarks keys: {list(remarks.keys())}")
        print(f"🔍 CIBIL API Response - Has credit_report_link: {remarks.get('credit_report_link') is not None}")
    
    # If successful and contains PDF link, download and store in S3
    if (status == "COMPLETED" and 
        isinstance(remarks, dict) and 
        remarks.get("credit_report_link")):
        
        try:
            pdf_link = remarks["credit_report_link"]
            print(f"📄 Downloading CIBIL PDF from temporary link: {pdf_link[:100]}...")
            
            # Download the PDF from temporary link
            async with aiohttp.ClientSession() as session:
                async with session.get(pdf_link) as pdf_response:
                    if pdf_response.status == 200:
                        pdf_content = await pdf_response.read()
                        print(f"✅ Downloaded PDF content: {len(pdf_content)} bytes")
                        
                        # Create S3 file name and path
                        pan_number = candidate.get("panNumber", "unknown")
                        timestamp = int(datetime.now().timestamp())
                        file_name = f"cibil_report_{pan_number}_{timestamp}.pdf"
                        
                        # Get organization name
                        org_name = candidate.get("organizationName", "unknown_org")
                        if not org_name or org_name == "unknown_org":
                            org_id = candidate.get("organizationId")
                            if org_id:
                                try:
                                    org = await orgsCol.find_one({"_id": ObjectId(org_id)})
                                    if org:
                                        org_name = org.get("organizationName", "unknown_org")
                                except:
                                    pass
                        
                        org_name = org_name.replace(" ", "_")
                        folder_path = f"{org_name}/{first_name}_{last_name}/documents"
                        
                        print(f"📁 S3 folder path: {folder_path}")
                        print(f"📄 S3 file name: {file_name}")
                        
                        # Import upload function
                        from main import upload_to_s3
                        
                        # Upload to S3
                        s3_url = await upload_to_s3(pdf_content, file_name, folder_path)
                        
                        # Add S3 URL to response data
                        remarks["s3_pdf_url"] = s3_url
                        remarks["pdf_stored"] = True
                        remarks["s3_folder_path"] = folder_path
                        remarks["s3_file_name"] = file_name
                        remarks["credit_report_link_permanent"] = s3_url
                        
                        print(f"✅ CIBIL PDF stored permanently in S3: {s3_url}")
                    else:
                        print(f"⚠️ Failed to download PDF: HTTP {pdf_response.status}")
                        remarks["pdf_stored"] = False
                        remarks["download_error"] = f"HTTP {pdf_response.status}"
                        
        except Exception as e:
            print(f"⚠️ Error downloading/storing CIBIL PDF: {e}")
            import traceback
            traceback.print_exc()
            remarks["pdf_stored"] = False
            remarks["download_error"] = str(e)
    
    return status, remarks


async def verify_court_record(candidate: dict):
    """
    Court record verification with exact name matching
    """
    url = "https://kyc-api.surepass.io/api/v1/ecourts/ecourt-search-v2"
    headers = {"Authorization": f"Bearer {SUREPASS_TOKEN}", "Content-Type": "application/json"}
    
    current_year = str(datetime.now().year)
    
    payload = {
        "name": f"{candidate.get('firstName')} {candidate.get('lastName')}",
        "father_name": "",
        "address": candidate.get("address", ""),
        "year": current_year
    }
    
    print(f"🔍 Court record search for: {payload['name']}, Year: {current_year}")
    
    status, response = await post_json(url, headers, payload)
    
    if status != "COMPLETED":
        return status, response
    
    # Filter for exact matches
    first_name = candidate.get('firstName', '').lower().strip()
    last_name = candidate.get('lastName', '').lower().strip()
    
    if isinstance(response, dict) and 'data' in response and 'result' in response['data']:
        all_cases = response['data']['result']
        matched_cases = []
        
        for case in all_cases:
            if not isinstance(case, dict):
                continue
            
            respondent = case.get('respondent', '').lower()
            respondent_normalized = respondent.replace('.', ' ').replace(',', ' ')
            respondent_normalized = ' '.join(respondent_normalized.split())
            
            if first_name in respondent_normalized and last_name in respondent_normalized:
                matched_cases.append(case)
                if len(matched_cases) >= 2:
                    break
        
        filtered_response = {
            "success": response.get('success', True),
            "message": response.get('message', 'Success'),
            "data": {
                "client_id": response['data'].get('client_id'),
                "name": response['data'].get('name'),
                "father_name": response['data'].get('father_name'),
                "address": response['data'].get('address'),
                "year": response['data'].get('year'),
                "state": response['data'].get('state'),
                "total_cases_from_api": len(all_cases),
                "exact_matches_found": len(matched_cases),
                "result": matched_cases,
                "filtering_applied": True,
                "filter_criteria": f"Exact match for '{first_name} {last_name}' as respondent"
            }
        }
        
        return status, filtered_response
    
    return status, response


# ---------------------------------------------------
# 📌 Internal Verification Functions (Manual/AI)
# ---------------------------------------------------
async def verify_address_manual(candidate: dict):
    """Internal address verification - manual check only"""
    return "PENDING", {
        "message": "Address verification pending manual review",
        "candidateAddress": candidate.get("address", ""),
        "district": candidate.get("district", ""),
        "state": candidate.get("state", ""),
        "pincode": candidate.get("pincode", ""),
        "requiresManualVerification": True
    }


async def verify_education_manual(candidate: dict):
    """Education check manual offline"""
    return "PENDING", {
        "message": "Education verification pending manual offline research",
        "candidateName": f"{candidate.get('firstName', '')} {candidate.get('lastName', '')}".strip(),
        "requiresManualVerification": True,
        "instructions": "Manually verify education credentials through institution contact"
    }


async def verify_supervisory_check(candidate: dict):
    """Supervisory check - manual phone call"""
    return "PENDING", {
        "message": "Supervisory check pending manual phone verification",
        "candidateName": f"{candidate.get('firstName', '')} {candidate.get('lastName', '')}".strip(),
        "candidatePhone": candidate.get("phone", ""),
        "requiresManualVerification": True,
        "instructions": "Contact candidate's previous organization for employment verification"
    }


async def verify_employment_history_manual(candidate: dict):
    """Employment history manual offline verification"""
    return "PENDING", {
        "message": "Employment history verification pending manual offline check",
        "candidateName": f"{candidate.get('firstName', '')} {candidate.get('lastName', '')}".strip(),
        "requiresManualVerification": True,
        "instructions": "Manually verify employment history through previous employers"
    }


async def verify_ai_cv_validation(candidate: dict):
    """AI CV Validation check"""
    return "PENDING", {
        "message": "AI CV validation pending manual verification with AI analysis",
        "candidateName": f"{candidate.get('firstName', '')} {candidate.get('lastName', '')}".strip(),
        "candidateEmail": candidate.get("email", ""),
        "requiresManualVerification": True,
        "requiresAIAnalysis": True,
        "instructions": "Upload candidate's CV/Resume for AI-powered authenticity analysis"
    }


async def verify_ai_education_validation(candidate: dict):
    """AI Education Validation check"""
    return "PENDING", {
        "message": "AI education validation pending manual verification with AI analysis",
        "candidateName": f"{candidate.get('firstName', '')} {candidate.get('lastName', '')}".strip(),
        "candidateEmail": candidate.get("email", ""),
        "requiresManualVerification": True,
        "requiresAIAnalysis": True,
        "requiresOCR": True,
        "instructions": "Upload education certificate for AI-powered OCR extraction and validation"
    }


# ---------------------------------------------------
# 📌 Field Validation
# ---------------------------------------------------
def validate_fields(check_type, candidate):
    """
    Validate if candidate has required fields for a specific check
    Returns: (is_valid: bool, missing_field: str or None)
    """
    required = {
        # Automated API checks
        "pan_aadhaar_seeding": ["aadhaarNumber", "panNumber"],
        "pan_verification": ["panNumber"],
        "employment_history": ["uanNumber"],
        "verify_pan_to_uan": ["panNumber"],
        "credit_report": ["phone", "panNumber", "firstName", "lastName"],
        "court_record": ["firstName", "lastName", "address"],
        
        # Manual verification checks
        "supervisory_check_1": ["supervisoryCheck1"],
        "supervisory_check_2": ["supervisoryCheck2"],
        "employment_check_2": ["employmentHistory2"],
        "employment_history_manual": ["employmentHistory1"],
        "employment_history_manual_2": ["employmentHistory2"],
        "education_check_manual": ["educationCheck"],
        "address_verification": ["address"],
        "ai_cv_validation": ["firstName", "lastName"],
        "supervisory_check": ["firstName", "lastName"]
    }

    fields = required.get(check_type, [])
    
    for field in fields:
        field_data = candidate.get(field)
        
        if not field_data:
            return False, field
        
        # For nested objects, validate sub-fields
        if isinstance(field_data, dict):
            if field in ["supervisoryCheck1", "supervisoryCheck2"]:
                if not field_data.get("name") or not field_data.get("phone"):
                    return False, f"{field} (requires name and phone)"
            
            elif field in ["employmentHistory1", "employmentHistory2"]:
                if not field_data.get("company") or not field_data.get("hrContact"):
                    return False, f"{field} (requires company and hrContact)"
                if not field_data.get("relievingLetterUrl"):
                    return False, f"{field} (requires relievingLetterUrl document)"
            
            elif field == "educationCheck":
                if not field_data.get("certificateUrl"):
                    return False, f"{field} (requires certificateUrl document)"
                if not field_data.get("universityContact"):
                    return False, f"{field} (requires universityContact)"
    
    return True, None


# ---------------------------------------------------
# 📌 Dispatcher
# ---------------------------------------------------
async def run_verification(check_type: str, candidate: dict):
    """Main verification dispatcher"""
    check_type = check_type.lower().strip()

    ok, missing_field = validate_fields(check_type, candidate)
    if not ok:
        return "SKIPPED", f"Missing required field: {missing_field}"

    # API-based checks
    if check_type == "pan_aadhaar_seeding":
        return await verify_pan_aadhaar_seeding(
            candidate.get("panNumber"),
            candidate.get("aadhaarNumber")
        )

    if check_type == "pan_verification":
        return await verify_pan(candidate.get("panNumber"))

    if check_type == "employment_history":
        return await verify_employment_history(candidate.get("uanNumber"))

    if check_type == "verify_pan_to_uan":
        return await verify_pan_to_uan(candidate.get("panNumber"))

    if check_type == "credit_report":
        return await verify_credit_report(candidate)

    if check_type == "court_record":
        return await verify_court_record(candidate)
    
    # Manual/AI checks
    if check_type == "address_verification":
        return await verify_address_manual(candidate)
    
    if check_type == "education_check_manual":
        return await verify_education_manual(candidate)
    
    if check_type == "ai_cv_validation":
        return await verify_ai_cv_validation(candidate)
    
    if check_type == "ai_education_validation":
        return await verify_ai_education_validation(candidate)
    
    if check_type in ["supervisory_check", "supervisory_check_1", "supervisory_check_2"]:
        return await verify_supervisory_check(candidate)
    
    if check_type in ["employment_history_manual", "employment_history_manual_2", "employment_check_2"]:
        return await verify_employment_history_manual(candidate)

    return "FAILED", f"Unknown check type: {check_type}"
