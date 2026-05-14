"""
Business logic for AI Screening
"""
from typing import Dict, List, Optional
from datetime import datetime, timezone
from bson import ObjectId
import time
import io
import requests

# Import from core
from core.database import (
    applicationsCol,
    jobsCol,
    jobSeekersCol,
    aiScreeningResultsCol
)

# Import AI screening utilities
from utils.resume_screening_enhanced import screen_resumes_enhanced


class AIScreeningService:
    """Service for handling AI screening operations"""
    
    async def run_ai_screening(
        self,
        job_id: str,
        user_org_id: str,
        application_ids: Optional[List[str]] = None,
        min_score_percentage: Optional[float] = None,
        top_n: Optional[int] = None
    ) -> Dict:
        """
        Run AI screening on job applications
        
        Args:
            job_id: Job ID
            user_org_id: Organization ID from JWT
            application_ids: Optional list of specific application IDs to screen
            min_score_percentage: Optional minimum score percentage (0-100)
            top_n: Optional maximum number of top candidates to return
            
        Returns:
            Dictionary with screening results
        """
        start_time = time.time()
        
        # Get job details
        job = await jobsCol.find_one({
            "_id": ObjectId(job_id),
            "orgId": user_org_id,
            "isDeleted": False
        })
        
        if not job:
            raise ValueError("Job not found or access denied")
        
        # Build query for applications
        query = {
            "jobId": job_id,
            "isDeleted": False
        }
        
        # If specific application IDs provided, filter by them (and allow any source)
        if application_ids:
            query["_id"] = {"$in": [ObjectId(app_id) for app_id in application_ids]}
        else:
            # Only filter by JOB_PORTAL source when screening all applications
            query["source"] = "JOB_PORTAL"
        
        # Get applications
        cursor = applicationsCol.find(query)
        applications = await cursor.to_list(length=None)
        
        if not applications:
            raise ValueError("No applications found to screen")
        
        print(f"🔍 Found {len(applications)} applications to screen")
        for app in applications:
            print(f"   - Application {str(app['_id'])}: jobSeekerId={app.get('jobSeekerId')}, source={app.get('source')}")
        
        # Fetch resumes from Cloudinary
        resume_files = []
        application_map = {}  # Map filename to application
        failed_applications = []  # Track failed applications
        
        for app in applications:
            job_seeker_id = app.get("jobSeekerId")
            app_id = str(app["_id"])
            
            print(f"\n🔄 Processing application {app_id}...")
            
            if not job_seeker_id:
                failed_applications.append({
                    "applicationId": app_id,
                    "reason": "No job seeker ID"
                })
                print(f"⚠️ Application {app_id}: No job seeker ID")
                continue
            
            print(f"   Looking for job seeker: {job_seeker_id}")
            
            # Get job seeker details
            job_seeker = await jobSeekersCol.find_one({
                "_id": ObjectId(job_seeker_id),
                "isActive": True
            })
            
            if not job_seeker:
                failed_applications.append({
                    "applicationId": app_id,
                    "reason": "Job seeker not found or inactive"
                })
                print(f"⚠️ Application {app_id}: Job seeker {job_seeker_id} not found or inactive")
                continue
            
            print(f"   Found job seeker: {job_seeker.get('name')}")
            
            resume_url = job_seeker.get("resumeUrl")
            if not resume_url:
                failed_applications.append({
                    "applicationId": app_id,
                    "jobSeekerName": job_seeker.get("name", "Unknown"),
                    "reason": "No resume uploaded"
                })
                print(f"⚠️ Application {app_id}: Job seeker {job_seeker.get('name')} has no resume")
                continue
            
            print(f"   Resume URL: {resume_url}")
            
            # Remove fl_attachment flag for programmatic access
            # fl_attachment forces download in browser, but we need to read the file
            fetch_url = resume_url.replace('/fl_attachment/', '/')
            
            print(f"   Fetch URL: {fetch_url}")
            
            try:
                # Download resume from Cloudinary
                print(f"📥 Downloading resume for {job_seeker.get('name')}...")
                response = requests.get(fetch_url, timeout=30)
                response.raise_for_status()
                resume_bytes = response.content
                
                print(f"   Downloaded {len(resume_bytes)} bytes")
                
                # Create filename
                filename = f"{job_seeker_id}.pdf"
                
                # Add to resume files
                resume_files.append({
                    "filename": filename,
                    "content": resume_bytes
                })
                
                # Map filename to application
                application_map[filename] = {
                    "applicationId": app_id,
                    "jobSeekerId": job_seeker_id,
                    "jobSeekerName": job_seeker.get("name", "Unknown"),
                    "jobSeekerEmail": job_seeker.get("email", ""),
                    "resumeUrl": resume_url
                }
                
                print(f"✅ Successfully downloaded resume for {job_seeker.get('name')}")
                
            except Exception as e:
                failed_applications.append({
                    "applicationId": app_id,
                    "jobSeekerName": job_seeker.get("name", "Unknown"),
                    "reason": f"Failed to download resume: {str(e)}"
                })
                print(f"❌ Error downloading resume for {job_seeker_id} ({job_seeker.get('name')}): {e}")
                continue
        
        if not resume_files:
            error_details = "\n".join([f"- {f['applicationId']}: {f['reason']}" for f in failed_applications])
            raise ValueError(f"No resumes found to screen. Failed applications:\n{error_details}")
        
        print(f"📊 Summary: {len(resume_files)} resumes ready, {len(failed_applications)} failed")
        if failed_applications:
            print(f"⚠️ Failed applications: {failed_applications}")
        
        # Run AI screening
        job_description = job.get("description", "")
        required_skills = job.get("skills", [])
        
        # Prepare JD file (job description as bytes)
        jd_text = f"""Job Title: {job.get('title', '')}
Department: {job.get('department', '')}
Location: {job.get('location', '')}
Experience Required: {job.get('experience', '')}
Job Type: {job.get('type', '')}

Required Skills:
{', '.join(required_skills)}

Job Description:
{job_description}
"""
        jd_bytes = jd_text.encode('utf-8')
        jd_file = (jd_bytes, "job_description.txt")
        
        # Prepare resume files in the format expected by screen_resumes_enhanced
        resume_files_formatted = [
            (rf["content"], rf["filename"]) 
            for rf in resume_files
        ]
        
        # Extract must-have requirements from skills
        must_have_requirements = required_skills if required_skills else None
        
        # Run AI screening with high topN to get all results, then filter
        # We'll request all resumes (up to 100) and filter by score later
        max_results = len(resume_files_formatted)
        
        # Run AI screening with lower embedding threshold to not filter out candidates prematurely
        # We'll filter by final score (minScorePercentage) instead
        screening_results = await screen_resumes_enhanced(
            resume_files=resume_files_formatted,
            jd_file=jd_file,
            top_n=max_results,  # Get all results
            must_have_requirements=must_have_requirements,
            nice_to_have=None,
            min_embedding_score=0.3,  # Lower threshold - let LLM analysis decide
            embedding_weight=0.3,
            llm_weight=0.7
        )
        
        # Process results and store in database
        all_results = []
        screening_session_id = str(ObjectId())  # Unique ID for this screening session
        now = datetime.now(timezone.utc)
        
        for result in screening_results.get("top_resumes", []):
            filename = result.get("filename")
            app_data = application_map.get(filename)
            
            if not app_data:
                continue
            
            final_score = result.get("final_weighted_score", 0)
            
            # Apply minimum score filter if provided
            if min_score_percentage is not None:
                if final_score < min_score_percentage:
                    continue  # Skip candidates below threshold
            
            # Update application with AI score
            await applicationsCol.update_one(
                {"_id": ObjectId(app_data["applicationId"])},
                {
                    "$set": {
                        "aiScore": final_score,
                        "updatedAt": now
                    }
                }
            )
            
            # Build result object
            result_doc = {
                "screeningSessionId": screening_session_id,
                "jobId": job_id,
                "orgId": user_org_id,
                "applicationId": app_data["applicationId"],
                "jobSeekerId": app_data["jobSeekerId"],
                "jobSeekerName": app_data["jobSeekerName"],
                "jobSeekerEmail": app_data["jobSeekerEmail"],
                "rank": result.get("rank", 0),
                "finalScore": final_score,
                "embeddingScore": result.get("embedding_similarity", 0),
                "llmScore": result.get("llm_match_score", 0),
                "recommendation": result.get("recommendation", ""),
                "strengths": result.get("strengths", []),
                "weaknesses": result.get("weaknesses", []),
                "explanation": result.get("ranking_explanation", ""),
                "summary": result.get("summary", ""),
                "meetsCriticalRequirements": result.get("meets_critical_requirements", False),
                "resumeUrl": app_data["resumeUrl"],
                "createdAt": now,
                "createdBy": user_org_id
            }
            
            # Store in ai_screening_results collection
            await aiScreeningResultsCol.insert_one(result_doc)
            
            # Add to results list
            all_results.append({
                "applicationId": app_data["applicationId"],
                "jobSeekerId": app_data["jobSeekerId"],
                "jobSeekerName": app_data["jobSeekerName"],
                "jobSeekerEmail": app_data["jobSeekerEmail"],
                "rank": result.get("rank", 0),
                "finalScore": final_score,
                "embeddingScore": result.get("embedding_similarity", 0),
                "llmScore": result.get("llm_match_score", 0),
                "recommendation": result.get("recommendation", ""),
                "strengths": result.get("strengths", []),
                "weaknesses": result.get("weaknesses", []),
                "explanation": result.get("ranking_explanation", ""),
                "summary": result.get("summary", ""),
                "meetsCriticalRequirements": result.get("meets_critical_requirements", False),
                "resumeUrl": app_data["resumeUrl"]
            })
        
        # Apply topN limit if provided
        if top_n is not None and top_n < len(all_results):
            processed_results = all_results[:top_n]
        else:
            processed_results = all_results
        
        processing_time = time.time() - start_time
        
        return {
            "message": "AI screening completed successfully",
            "jobId": job_id,
            "jobTitle": job.get("title", ""),
            "totalApplications": len(applications),
            "totalProcessed": len(all_results),
            "totalFailed": len(failed_applications),
            "failedApplications": failed_applications if failed_applications else None,
            "filteredByScore": len(all_results) if min_score_percentage else None,
            "minScorePercentage": min_score_percentage,
            "topN": top_n,
            "results": processed_results,
            "processingTime": round(processing_time, 2)
        }
    
    async def get_screening_results(
        self,
        job_id: str,
        user_org_id: str,
        application_id: Optional[str] = None
    ) -> Dict:
        """
        Get AI screening results for a job or specific application
        
        Args:
            job_id: Job ID
            user_org_id: Organization ID from JWT
            application_id: Optional specific application ID
            
        Returns:
            Dictionary with screening results
        """
        # Verify job belongs to user's org
        job = await jobsCol.find_one({
            "_id": ObjectId(job_id),
            "orgId": user_org_id,
            "isDeleted": False
        })
        
        if not job:
            raise ValueError("Job not found or access denied")
        
        # Build query
        query = {
            "jobId": job_id,
            "orgId": user_org_id
        }
        
        # If specific application requested
        if application_id:
            query["applicationId"] = application_id
        
        # Get screening results
        cursor = aiScreeningResultsCol.find(query).sort("rank", 1)
        results = await cursor.to_list(length=None)
        
        if not results:
            return {
                "message": "No screening results found",
                "jobId": job_id,
                "jobTitle": job.get("title", ""),
                "totalResults": 0,
                "results": []
            }
        
        # Process results
        processed_results = []
        for result in results:
            result["_id"] = str(result["_id"])
            
            # Get current application stage
            app = await applicationsCol.find_one({
                "_id": ObjectId(result["applicationId"])
            })
            
            result["currentStage"] = app.get("stage", "Applied") if app else "Unknown"
            
            processed_results.append(result)
        
        return {
            "message": "Screening results retrieved successfully",
            "jobId": job_id,
            "jobTitle": job.get("title", ""),
            "totalResults": len(processed_results),
            "results": processed_results
        }

    async def add_from_screening(
        self,
        first_name: Optional[str],
        last_name: Optional[str],
        email: Optional[str],
        phone: Optional[str],
        resume_url: Optional[str],
        resume_filename: Optional[str],
        job_id: Optional[str],
        org_id: str,
        org_name: str,
        add_as: str,
        user_email: str,
        # AI Screening Results
        final_score: Optional[float] = None,
        embedding_score: Optional[float] = None,
        llm_score: Optional[int] = None,
        recommendation: Optional[str] = None,
        strengths: Optional[List[str]] = None,
        weaknesses: Optional[List[str]] = None,
        summary: Optional[str] = None,
        explanation: Optional[str] = None,
        meets_critical_requirements: Optional[bool] = None
    ) -> Dict:
        """
        Add candidate or jobseeker from AI screening results
        
        Args:
            first_name: First name
            last_name: Last name
            email: Email address
            phone: Phone number
            resume_url: Resume URL from Cloudinary
            resume_filename: Original resume filename
            job_id: Job ID (required if add_as='jobseeker')
            org_id: Organization ID
            org_name: Organization name
            add_as: 'candidate' or 'jobseeker'
            user_email: Email of user adding
            
        Returns:
            Dictionary with created record details
        """
        from core.database import candidatesCol, orgsCol
        
        # Validation
        if not any([first_name, last_name, email, phone]):
            raise ValueError("At least one field (firstName, lastName, email, or phone) is required")
        
        if add_as not in ["candidate", "jobseeker"]:
            raise ValueError("addAs must be either 'candidate' or 'jobseeker'")
        
        if add_as == "jobseeker" and not job_id:
            raise ValueError("jobId is required when addAs='jobseeker'")
        
        full_name = f"{first_name or ''} {last_name or ''}".strip()
        now = datetime.now(timezone.utc)
        
        # Option 1: Add as Candidate (Direct BGV)
        if add_as == "candidate":
            # Check for duplicate in candidates collection (within org)
            if email or phone:
                duplicate_query = {"organizationId": org_id}
                or_conditions = []
                
                if email:
                    or_conditions.append({"email": email})
                if phone:
                    or_conditions.append({"phone": phone})
                
                if or_conditions:
                    duplicate_query["$or"] = or_conditions
                    existing = await candidatesCol.find_one(duplicate_query)
                    if existing:
                        raise ValueError(f"A candidate with this email/phone already exists in your organization")
            
            # Create candidate document
            candidate_doc = {
                "firstName": first_name or "",
                "middleName": "",
                "lastName": last_name or "",
                "email": email or "",
                "phone": phone or "",
                "jobTitle": "",
                "organizationId": org_id,
                "organizationName": org_name,
                
                # References (empty for direct add)
                "jobSeekerId": None,
                "applicationId": None,
                "interviewId": None,
                
                # BGV fields (to be filled later)
                "aadhaarNumber": "",
                "panNumber": "",
                "dob": "",
                "fatherName": "",
                "address": "",
                "district": "",
                "state": "",
                "pincode": "",
                "uanNumber": "",
                "gender": "",
                
                # Resume
                "resumePath": resume_url or "",
                
                # Status
                "status": "PENDING",
                "source": "AI_SCREENING",
                
                # Metadata
                "createdAt": now.isoformat(),
                "createdBy": user_email,
                "updatedAt": now.isoformat()
            }
            
            result = await candidatesCol.insert_one(candidate_doc)
            candidate_id = str(result.inserted_id)
            
            return {
                "message": "Candidate added successfully for BGV process",
                "addedAs": "candidate",
                "id": candidate_id,
                "name": full_name,
                "email": email,
                "phone": phone,
                "applicationId": None,
                "nextStep": "Complete BGV form for this candidate"
            }
        
        # Option 2: Add as Job Seeker (Hiring Pipeline)
        else:  # add_as == "jobseeker"
            # Check for duplicate in job_seekers collection
            if email or phone:
                duplicate_query = {"isActive": True}
                or_conditions = []
                
                if email:
                    or_conditions.append({"email": email})
                if phone:
                    or_conditions.append({"phone": phone})
                
                if or_conditions:
                    duplicate_query["$or"] = or_conditions
                    existing = await jobSeekersCol.find_one(duplicate_query)
                    if existing:
                        raise ValueError(f"A job seeker with this email/phone already exists")
            
            # Create job seeker document
            job_seeker_doc = {
                "name": full_name,
                "email": email,
                "phone": phone,
                "resumeUrl": resume_url,
                "resumeFilename": resume_filename,
                "source": "ai_screening",
                "addedBy": "HR",
                "addedByEmail": user_email,
                "addedByOrg": org_id,
                "addedByOrgName": org_name,
                "createdAt": now.isoformat(),
                "updatedAt": now.isoformat(),
                "profileJson": {
                    "contact_information": {
                        "name": full_name,
                        "email": email,
                        "phone": phone
                    },
                    "experience": [],
                    "education": [],
                    "skills": []
                },
                "profileCompletion": 10,
                "isActive": True,
                "passwordHash": None
            }
            
            result = await jobSeekersCol.insert_one(job_seeker_doc)
            job_seeker_id = str(result.inserted_id)
            
            # Create application with stage "Resume Shortlist" (already screened by AI)
            # Get job details
            job = await jobsCol.find_one({"_id": ObjectId(job_id)})
            if not job:
                raise ValueError("Job not found")
            
            application_doc = {
                "jobId": job_id,
                "orgId": org_id,
                "jobSeekerId": job_seeker_id,
                "candidateName": full_name,
                "candidateEmail": email or "",
                "candidatePhone": phone or "",
                "resumeUrl": resume_url or "",
                "stage": "Resume Shortlist",  # Already screened by AI
                "source": "AI_SCREENING",
                "aiScore": None,
                "notes": "Added from AI screening",
                "stageHistory": [
                    {
                        "stage": "Resume Shortlist",
                        "changedBy": user_email,
                        "changedAt": now,
                        "notes": "Added from AI screening - resume already reviewed"
                    }
                ],
                "isDeleted": False,
                "deletedAt": None,
                "deletedBy": None,
                "appliedAt": now,
                "updatedAt": now
            }
            
            app_result = await applicationsCol.insert_one(application_doc)
            application_id = str(app_result.inserted_id)
            
            # Store AI screening results if provided
            if final_score is not None:
                screening_result_doc = {
                    "screeningSessionId": None,  # No session for manual add
                    "jobId": job_id,
                    "orgId": org_id,
                    "applicationId": application_id,
                    "jobSeekerId": job_seeker_id,
                    "jobSeekerName": full_name,
                    "jobSeekerEmail": email or "",
                    "rank": None,  # No rank for manual add
                    "finalScore": final_score,
                    "embeddingScore": embedding_score or 0,
                    "llmScore": llm_score or 0,
                    "recommendation": recommendation or "",
                    "strengths": strengths or [],
                    "weaknesses": weaknesses or [],
                    "explanation": explanation or "",
                    "summary": summary or "",
                    "meetsCriticalRequirements": meets_critical_requirements or False,
                    "resumeUrl": resume_url or "",
                    "createdAt": now,
                    "createdBy": user_email
                }
                
                await aiScreeningResultsCol.insert_one(screening_result_doc)
                
                # Also update application with AI score
                await applicationsCol.update_one(
                    {"_id": ObjectId(application_id)},
                    {"$set": {"aiScore": final_score}}
                )
            
            return {
                "message": "Job seeker added successfully and application created",
                "addedAs": "jobseeker",
                "id": job_seeker_id,
                "name": full_name,
                "email": email,
                "phone": phone,
                "applicationId": application_id,
                "nextStep": "Job seeker is now in 'Resume Shortlist' stage. Schedule interview when ready."
            }
