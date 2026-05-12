"""
Business logic for Interview Management
"""
from typing import Dict, List, Optional
from datetime import datetime, timezone
from bson import ObjectId

# Import from core
from core.database import (
    interviewsCol,
    applicationsCol,
    jobSeekersCol,
    jobsCol,
    candidatesCol
)


class InterviewService:
    """Service for handling interview operations"""
    
    # Round names
    ROUND_NAMES = {
        1: "Tech Round",
        2: "Manager Round",
        3: "HR Round",
        4: "Final Round"
    }
    
    async def create_interview(
        self,
        application_id: str,
        user_org_id: str,
        user_email: str
    ) -> Dict:
        """
        Create interview record with 4 pending rounds
        
        Args:
            application_id: Application ID
            user_org_id: Organization ID from JWT
            user_email: Email of user creating interview
            
        Returns:
            Created interview document
        """
        # Get application details
        application = await applicationsCol.find_one({
            "_id": ObjectId(application_id),
            "orgId": user_org_id,
            "source": "JOB_PORTAL",
            "isDeleted": False
        })
        
        if not application:
            raise ValueError("Application not found or access denied")
        
        # Check if interview already exists
        existing = await interviewsCol.find_one({
            "applicationId": application_id,
            "isDeleted": False
        })
        
        if existing:
            raise ValueError("Interview already exists for this application")
        
        now = datetime.now(timezone.utc)
        
        # Initialize 4 rounds
        rounds = []
        for round_num in range(1, 5):
            rounds.append({
                "roundNumber": round_num,
                "roundName": self.ROUND_NAMES[round_num],
                "interviewerId": None,
                "interviewer": None,
                "interviewerEmail": None,
                "scheduledAt": None,
                "status": "Pending",
                "rating": None,
                "feedback": "",
                "completedAt": None,
                "updatedBy": None,
                "updatedAt": None
            })
        
        # Build interview document
        interview_doc = {
            "applicationId": application_id,
            "jobSeekerId": application.get("jobSeekerId"),
            "jobId": application.get("jobId"),
            "orgId": user_org_id,
            
            "rounds": rounds,
            "currentRound": 1,
            "overallStatus": "In Progress",
            
            "offerExtended": False,
            "offerExtendedAt": None,
            "offerExtendedBy": None,
            
            "rejected": False,
            "rejectedAt": None,
            "rejectedBy": None,
            "rejectionReason": "",
            "rejectedAtRound": None,
            
            "hired": False,
            "hiredAt": None,
            "hiredBy": None,
            
            "bgvInitiated": False,
            "bgvInitiatedAt": None,
            "bgvInitiatedBy": None,
            "candidateId": None,
            
            "createdAt": now,
            "createdBy": user_email,
            "updatedAt": now,
            "isDeleted": False
        }
        
        # Insert interview
        result = await interviewsCol.insert_one(interview_doc)
        interview_doc["_id"] = str(result.inserted_id)
        
        # Update application stage to "Interview"
        await applicationsCol.update_one(
            {"_id": ObjectId(application_id)},
            {
                "$set": {
                    "stage": "Interview",
                    "updatedAt": now
                },
                "$push": {
                    "stageHistory": {
                        "stage": "Interview",
                        "changedBy": user_email,
                        "changedAt": now,
                        "notes": "Interview process initiated"
                    }
                }
            }
        )
        
        return interview_doc
    
    async def get_interview(
        self,
        interview_id: str,
        user_org_id: str
    ) -> Optional[Dict]:
        """
        Get interview details
        
        Args:
            interview_id: Interview ID
            user_org_id: Organization ID from JWT
            
        Returns:
            Interview document or None
        """
        try:
            interview = await interviewsCol.find_one({
                "_id": ObjectId(interview_id),
                "orgId": user_org_id,
                "isDeleted": False
            })
            
            if interview:
                interview["_id"] = str(interview["_id"])
            
            return interview
            
        except:
            return None
    
    async def schedule_round(
        self,
        interview_id: str,
        round_number: int,
        interviewer_id: str,
        scheduled_at: datetime,
        user_org_id: str,
        user_email: str
    ) -> Optional[Dict]:
        """
        Schedule an interview round
        
        Args:
            interview_id: Interview ID
            round_number: Round number (1-4)
            interviewer_id: Interviewer ID from interviewers collection
            scheduled_at: Scheduled date/time
            user_org_id: Organization ID from JWT
            user_email: Email of user scheduling
            
        Returns:
            Updated interview or None
        """
        from core.database import interviewersCol
        
        # Get interview
        interview = await interviewsCol.find_one({
            "_id": ObjectId(interview_id),
            "orgId": user_org_id,
            "isDeleted": False
        })
        
        if not interview:
            raise ValueError("Interview not found")
        
        # Check if interview is rejected or hired
        if interview.get("rejected") or interview.get("hired"):
            raise ValueError("Cannot schedule round for rejected or hired candidate")
        
        # Check if previous round is completed (for rounds > 1)
        if round_number > 1:
            prev_round = interview["rounds"][round_number - 2]
            if prev_round["status"] != "Passed":
                raise ValueError(f"Previous round must be completed before scheduling Round {round_number}")
        
        # Validate interviewer exists and is active
        interviewer = await interviewersCol.find_one({
            "_id": ObjectId(interviewer_id),
            "organizationId": user_org_id,
            "isDeleted": False
        })
        
        if not interviewer:
            raise ValueError("Interviewer not found")
        
        if not interviewer.get("isActive"):
            raise ValueError("Interviewer is not active")
        
        if not interviewer.get("isAvailable"):
            raise ValueError("Interviewer is not available")
        
        # Get interviewer details
        interviewer_name = interviewer.get("name")
        interviewer_email = interviewer.get("email")
        
        # Update round
        now = datetime.now(timezone.utc)
        update_path = f"rounds.{round_number - 1}"
        
        await interviewsCol.update_one(
            {"_id": ObjectId(interview_id)},
            {
                "$set": {
                    f"{update_path}.interviewerId": interviewer_id,
                    f"{update_path}.interviewer": interviewer_name,
                    f"{update_path}.interviewerEmail": interviewer_email,
                    f"{update_path}.scheduledAt": scheduled_at,
                    f"{update_path}.status": "Scheduled",
                    f"{update_path}.updatedBy": user_email,
                    f"{update_path}.updatedAt": now,
                    "updatedAt": now
                }
            }
        )
        
        # Get updated interview
        updated = await self.get_interview(interview_id, user_org_id)
        return updated
    
    async def update_round(
        self,
        interview_id: str,
        round_number: int,
        status: str,
        rating: int,
        feedback: str,
        user_org_id: str,
        user_email: str
    ) -> Optional[Dict]:
        """
        Update round status (Passed/Failed)
        
        Args:
            interview_id: Interview ID
            round_number: Round number (1-4)
            status: Passed or Failed
            rating: Rating 1-5
            feedback: Feedback text
            user_org_id: Organization ID from JWT
            user_email: Email of user updating
            
        Returns:
            Updated interview or None
        """
        # Get interview
        interview = await interviewsCol.find_one({
            "_id": ObjectId(interview_id),
            "orgId": user_org_id,
            "isDeleted": False
        })
        
        if not interview:
            raise ValueError("Interview not found")
        
        # Check if interview is rejected or hired
        if interview.get("rejected") or interview.get("hired"):
            raise ValueError("Cannot update round for rejected or hired candidate")
        
        # Check if round is scheduled
        round_data = interview["rounds"][round_number - 1]
        if round_data["status"] not in ["Scheduled", "Passed", "Failed"]:
            raise ValueError("Round must be scheduled before updating status")
        
        now = datetime.now(timezone.utc)
        update_path = f"rounds.{round_number - 1}"
        
        update_doc = {
            f"{update_path}.status": status,
            f"{update_path}.rating": rating,
            f"{update_path}.feedback": feedback,
            f"{update_path}.completedAt": now,
            f"{update_path}.updatedBy": user_email,
            f"{update_path}.updatedAt": now,
            "updatedAt": now
        }
        
        # If failed, mark interview as rejected
        if status == "Failed":
            update_doc.update({
                "rejected": True,
                "rejectedAt": now,
                "rejectedBy": user_email,
                "rejectionReason": f"Failed at {round_data['roundName']}",
                "rejectedAtRound": round_number,
                "overallStatus": "Rejected"
            })
        
        # If passed and this is the last round, mark as completed
        elif status == "Passed" and round_number == 4:
            update_doc["overallStatus"] = "Completed"
        
        # If passed, update current round
        elif status == "Passed":
            update_doc["currentRound"] = round_number + 1
        
        await interviewsCol.update_one(
            {"_id": ObjectId(interview_id)},
            {"$set": update_doc}
        )
        
        # Get updated interview
        updated = await self.get_interview(interview_id, user_org_id)
        return updated
    
    async def extend_offer(
        self,
        interview_id: str,
        user_org_id: str,
        user_email: str
    ) -> Optional[Dict]:
        """
        Extend offer to candidate
        
        Args:
            interview_id: Interview ID
            user_org_id: Organization ID from JWT
            user_email: Email of user extending offer
            
        Returns:
            Updated interview or None
        """
        # Get interview
        interview = await interviewsCol.find_one({
            "_id": ObjectId(interview_id),
            "orgId": user_org_id,
            "isDeleted": False
        })
        
        if not interview:
            raise ValueError("Interview not found")
        
        # Check if at least one round is passed
        passed_rounds = [r for r in interview["rounds"] if r["status"] == "Passed"]
        
        if not passed_rounds:
            raise ValueError("At least one interview round must be passed before extending offer")
        
        # Check if already rejected or hired
        if interview.get("rejected"):
            raise ValueError("Cannot extend offer to rejected candidate")
        
        if interview.get("hired"):
            raise ValueError("Candidate is already hired")
        
        now = datetime.now(timezone.utc)
        
        await interviewsCol.update_one(
            {"_id": ObjectId(interview_id)},
            {
                "$set": {
                    "offerExtended": True,
                    "offerExtendedAt": now,
                    "offerExtendedBy": user_email,
                    "overallStatus": "Offer Extended",
                    "updatedAt": now
                }
            }
        )
        
        # Get updated interview
        updated = await self.get_interview(interview_id, user_org_id)
        return updated
    
    async def reject_candidate(
        self,
        interview_id: str,
        reason: str,
        rejected_at_round: Optional[int],
        user_org_id: str,
        user_email: str
    ) -> Optional[Dict]:
        """
        Reject candidate
        
        Args:
            interview_id: Interview ID
            reason: Rejection reason
            rejected_at_round: Round number where rejected
            user_org_id: Organization ID from JWT
            user_email: Email of user rejecting
            
        Returns:
            Updated interview or None
        """
        # Get interview
        interview = await interviewsCol.find_one({
            "_id": ObjectId(interview_id),
            "orgId": user_org_id,
            "isDeleted": False
        })
        
        if not interview:
            raise ValueError("Interview not found")
        
        # Check if already hired
        if interview.get("hired"):
            raise ValueError("Cannot reject hired candidate")
        
        now = datetime.now(timezone.utc)
        
        await interviewsCol.update_one(
            {"_id": ObjectId(interview_id)},
            {
                "$set": {
                    "rejected": True,
                    "rejectedAt": now,
                    "rejectedBy": user_email,
                    "rejectionReason": reason,
                    "rejectedAtRound": rejected_at_round,
                    "overallStatus": "Rejected",
                    "updatedAt": now
                }
            }
        )
        
        # Get updated interview
        updated = await self.get_interview(interview_id, user_org_id)
        return updated
    
    async def mark_as_hired(
        self,
        interview_id: str,
        user_org_id: str,
        user_email: str
    ) -> Optional[Dict]:
        """
        Mark candidate as hired
        
        Args:
            interview_id: Interview ID
            user_org_id: Organization ID from JWT
            user_email: Email of user marking as hired
            
        Returns:
            Updated interview or None
        """
        # Get interview
        interview = await interviewsCol.find_one({
            "_id": ObjectId(interview_id),
            "orgId": user_org_id,
            "isDeleted": False
        })
        
        if not interview:
            raise ValueError("Interview not found")
        
        # Check if offer extended
        if not interview.get("offerExtended"):
            raise ValueError("Offer must be extended before marking as hired")
        
        # Check if already rejected
        if interview.get("rejected"):
            raise ValueError("Cannot hire rejected candidate")
        
        now = datetime.now(timezone.utc)
        
        await interviewsCol.update_one(
            {"_id": ObjectId(interview_id)},
            {
                "$set": {
                    "hired": True,
                    "hiredAt": now,
                    "hiredBy": user_email,
                    "overallStatus": "Hired",
                    "updatedAt": now
                }
            }
        )
        
        # Get updated interview
        updated = await self.get_interview(interview_id, user_org_id)
        return updated
    
    async def initiate_bgv(
        self,
        interview_id: str,
        user_org_id: str,
        user_email: str
    ) -> Dict:
        """
        Initiate BGV - Create candidate in candidates collection
        
        Args:
            interview_id: Interview ID
            user_org_id: Organization ID from JWT
            user_email: Email of user initiating BGV
            
        Returns:
            Dictionary with candidateId
        """
        # Get interview
        interview = await interviewsCol.find_one({
            "_id": ObjectId(interview_id),
            "orgId": user_org_id,
            "isDeleted": False
        })
        
        if not interview:
            raise ValueError("Interview not found")
        
        # Check if hired
        if not interview.get("hired"):
            raise ValueError("Candidate must be hired before initiating BGV")
        
        # Check if BGV already initiated
        if interview.get("bgvInitiated"):
            raise ValueError("BGV already initiated for this candidate")
        
        # Get job seeker details
        job_seeker = await jobSeekersCol.find_one({
            "_id": ObjectId(interview["jobSeekerId"]),
            "isActive": True
        })
        
        if not job_seeker:
            raise ValueError("Job seeker not found")
        
        # Get job details
        job = await jobsCol.find_one({
            "_id": ObjectId(interview["jobId"])
        })
        
        if not job:
            raise ValueError("Job not found")
        
        # Get organization details
        from core.database import orgsCol
        org = await orgsCol.find_one({
            "_id": ObjectId(user_org_id)
        })
        
        org_name = org.get("organizationName") if org else "Unknown"
        
        now = datetime.now(timezone.utc)
        
        # Split name into first and last
        full_name = job_seeker.get("name", "")
        name_parts = full_name.split(" ", 1)
        first_name = name_parts[0] if len(name_parts) > 0 else ""
        last_name = name_parts[1] if len(name_parts) > 1 else ""
        
        # Create candidate document
        candidate_doc = {
            # Pre-filled from job seeker
            "firstName": first_name,
            "middleName": "",
            "lastName": last_name,
            "email": job_seeker.get("email", ""),
            "phone": job_seeker.get("phone", ""),
            
            # From job/application
            "jobTitle": job.get("title", ""),
            "organizationId": user_org_id,
            "organizationName": org_name,
            
            # References
            "jobSeekerId": interview["jobSeekerId"],
            "applicationId": interview["applicationId"],
            "interviewId": interview_id,
            
            # To be filled in BGV form
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
            "resumePath": job_seeker.get("resumeUrl", ""),
            
            # Status
            "status": "PENDING",
            "source": "JOB_PORTAL",
            
            # Metadata
            "createdAt": now.isoformat(),
            "createdBy": user_email,
            "updatedAt": now.isoformat()
        }
        
        # Insert candidate
        result = await candidatesCol.insert_one(candidate_doc)
        candidate_id = str(result.inserted_id)
        
        # Update interview
        await interviewsCol.update_one(
            {"_id": ObjectId(interview_id)},
            {
                "$set": {
                    "bgvInitiated": True,
                    "bgvInitiatedAt": now,
                    "bgvInitiatedBy": user_email,
                    "candidateId": candidate_id,
                    "updatedAt": now
                }
            }
        )
        
        return {
            "candidateId": candidate_id,
            "message": "BGV initiated successfully"
        }
    
    async def get_interviews_for_job(
        self,
        job_id: str,
        user_org_id: str
    ) -> List[Dict]:
        """
        Get all interviews for a job with job seeker details
        
        Args:
            job_id: Job ID
            user_org_id: Organization ID from JWT
            
        Returns:
            List of interview documents with job seeker details
        """
        cursor = interviewsCol.find({
            "jobId": job_id,
            "orgId": user_org_id,
            "isDeleted": False
        }).sort("createdAt", -1)
        
        interviews = await cursor.to_list(length=None)
        
        # Enrich with job seeker details
        for interview in interviews:
            interview["_id"] = str(interview["_id"])
            
            # Fetch job seeker details
            job_seeker_id = interview.get("jobSeekerId")
            print(f"🔍 Interview {interview['_id']}: jobSeekerId = {job_seeker_id}")
            
            if job_seeker_id:
                try:
                    print(f"   Fetching job seeker from database...")
                    job_seeker = await jobSeekersCol.find_one({
                        "_id": ObjectId(job_seeker_id),
                        "isActive": True
                    })
                    
                    if job_seeker:
                        print(f"   ✅ Found job seeker: {job_seeker.get('name')}")
                        # Add job seeker details to interview
                        interview["jobSeekerName"] = job_seeker.get("name", "Unknown")
                        interview["jobSeekerEmail"] = job_seeker.get("email", "")
                        interview["jobSeekerPhone"] = job_seeker.get("phone", "")
                        interview["resumeUrl"] = job_seeker.get("resumeUrl", "")
                        interview["profileCompletion"] = job_seeker.get("profileCompletion", 0)
                        print(f"   Added details: name={interview['jobSeekerName']}, email={interview['jobSeekerEmail']}")
                    else:
                        print(f"   ⚠️ Job seeker not found or inactive")
                        # Job seeker not found
                        interview["jobSeekerName"] = "Unknown"
                        interview["jobSeekerEmail"] = ""
                        interview["jobSeekerPhone"] = ""
                        interview["resumeUrl"] = ""
                        interview["profileCompletion"] = 0
                except Exception as e:
                    print(f"   ❌ Error fetching job seeker {job_seeker_id}: {e}")
                    interview["jobSeekerName"] = "Unknown"
                    interview["jobSeekerEmail"] = ""
                    interview["jobSeekerPhone"] = ""
                    interview["resumeUrl"] = ""
                    interview["profileCompletion"] = 0
            else:
                print(f"   ⚠️ No jobSeekerId in interview")
        
        print(f"📊 Returning {len(interviews)} interviews")
        if interviews:
            print(f"   First interview keys: {list(interviews[0].keys())}")
        
        return interviews
    
    async def get_all_interviews(
        self,
        user_org_id: str,
        status: Optional[str] = None,
        job_id: Optional[str] = None
    ) -> List[Dict]:
        """
        Get all interviews for organization with optional filters and job seeker details
        
        Args:
            user_org_id: Organization ID from JWT
            status: Filter by overall status (In Progress, Completed, Offer Extended, Rejected, Hired)
            job_id: Filter by specific job ID
            
        Returns:
            List of interview documents with job seeker details
        """
        # Build query
        query = {
            "orgId": user_org_id,
            "isDeleted": False
        }
        
        if status:
            query["overallStatus"] = status
        
        if job_id:
            query["jobId"] = job_id
        
        # Fetch interviews
        cursor = interviewsCol.find(query).sort("createdAt", -1)
        interviews = await cursor.to_list(length=None)
        
        # Enrich with job seeker details
        for interview in interviews:
            interview["_id"] = str(interview["_id"])
            
            # Fetch job seeker details
            job_seeker_id = interview.get("jobSeekerId")
            if job_seeker_id:
                try:
                    job_seeker = await jobSeekersCol.find_one({
                        "_id": ObjectId(job_seeker_id),
                        "isActive": True
                    })
                    
                    if job_seeker:
                        # Add job seeker details to interview
                        interview["jobSeekerName"] = job_seeker.get("name", "Unknown")
                        interview["jobSeekerEmail"] = job_seeker.get("email", "")
                        interview["jobSeekerPhone"] = job_seeker.get("phone", "")
                        interview["resumeUrl"] = job_seeker.get("resumeUrl", "")
                        interview["profileCompletion"] = job_seeker.get("profileCompletion", 0)
                    else:
                        # Job seeker not found
                        interview["jobSeekerName"] = "Unknown"
                        interview["jobSeekerEmail"] = ""
                        interview["jobSeekerPhone"] = ""
                        interview["resumeUrl"] = ""
                        interview["profileCompletion"] = 0
                except Exception as e:
                    print(f"Error fetching job seeker {job_seeker_id}: {e}")
                    interview["jobSeekerName"] = "Unknown"
                    interview["jobSeekerEmail"] = ""
                    interview["jobSeekerPhone"] = ""
                    interview["resumeUrl"] = ""
                    interview["profileCompletion"] = 0
        
        return interviews
