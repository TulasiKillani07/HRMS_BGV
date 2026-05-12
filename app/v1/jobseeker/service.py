"""
Business logic for Job Seeker Portal
"""
from typing import Dict, List, Optional
from datetime import datetime, timezone
from bson import ObjectId
import bcrypt

# Import from core
from core.database import (
    jobSeekersCol,
    jobsCol,
    orgsCol
)


class JobSeekerService:
    """Service for handling job seeker operations"""
    
    # ============================================
    # Authentication
    # ============================================
    
    async def register_job_seeker(
        self,
        name: str,
        email: str,
        phone: str,
        password: str,
        resume_url: Optional[str] = None
    ) -> Dict:
        """
        Register a new job seeker
        
        Args:
            name: Full name
            email: Email address
            phone: Phone number
            password: Plain text password (will be hashed)
            resume_url: Optional S3 URL to resume
            
        Returns:
            Created job seeker document (without passwordHash)
        """
        # Check for duplicate email
        existing = await jobSeekersCol.find_one({"email": email.lower()})
        if existing:
            raise ValueError("Email already registered")
        
        # Hash password with bcrypt (10 rounds)
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(rounds=10))
        
        now = datetime.now(timezone.utc)
        
        # Build job seeker document
        job_seeker_doc = {
            "name": name,
            "email": email.lower(),
            "phone": phone,
            "passwordHash": password_hash.decode('utf-8'),
            "resumeUrl": resume_url,
            "profileJson": {
                "experience": [],
                "education": [],
                "skills": [],
                "bio": "",
                "location": "",
                "linkedinUrl": "",
                "githubUrl": ""
            },
            "savedJobs": [],
            "profileCompletion": self._calculate_profile_completion(
                name=name,
                email=email,
                phone=phone,
                resume_url=resume_url,
                profile_json={
                    "experience": [],
                    "education": [],
                    "skills": []
                }
            ),
            "createdAt": now,
            "updatedAt": now,
            "isActive": True
        }
        
        # Insert into database
        result = await jobSeekersCol.insert_one(job_seeker_doc)
        job_seeker_doc["_id"] = str(result.inserted_id)
        
        # Remove passwordHash before returning
        del job_seeker_doc["passwordHash"]
        
        return job_seeker_doc
    
    async def login_job_seeker(
        self,
        email: str,
        password: str
    ) -> Optional[Dict]:
        """
        Authenticate job seeker
        
        Args:
            email: Email address
            password: Plain text password
            
        Returns:
            Job seeker document (without passwordHash) or None if invalid
        """
        try:
            # Find job seeker
            job_seeker = await jobSeekersCol.find_one({
                "email": email.lower(),
                "isActive": True
            })
            
            if not job_seeker:
                return None
            
            # Verify password
            password_hash = job_seeker.get("passwordHash", "")
            if not password_hash:
                return None
            
            # bcrypt.checkpw expects bytes for both password and hash
            if not bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8')):
                return None
            
            # Convert ObjectId to string
            job_seeker["_id"] = str(job_seeker["_id"])
            
            # Remove passwordHash before returning
            del job_seeker["passwordHash"]
            
            return job_seeker
            
        except Exception as e:
            print(f"❌ Login error: {e}")
            return None
    
    # ============================================
    # Profile Management
    # ============================================
    
    async def get_profile(
        self,
        job_seeker_id: str
    ) -> Optional[Dict]:
        """
        Get job seeker profile
        
        Args:
            job_seeker_id: Job seeker ID
            
        Returns:
            Job seeker document (without passwordHash) or None
        """
        try:
            from main import make_cloudinary_url_downloadable
            
            job_seeker = await jobSeekersCol.find_one({
                "_id": ObjectId(job_seeker_id),
                "isActive": True
            })
            
            if not job_seeker:
                return None
            
            job_seeker["_id"] = str(job_seeker["_id"])
            
            # Keep resume URL clean (no fl_attachment)
            # Transformations applied dynamically when needed
            
            # Remove passwordHash
            if "passwordHash" in job_seeker:
                del job_seeker["passwordHash"]
            
            return job_seeker
            
        except:
            return None
    
    async def update_profile(
        self,
        job_seeker_id: str,
        update_fields: Dict
    ) -> Optional[Dict]:
        """
        Update job seeker profile
        
        Args:
            job_seeker_id: Job seeker ID
            update_fields: Fields to update
            
        Returns:
            Updated job seeker document or None
        """
        try:
            # Get current profile
            job_seeker = await jobSeekersCol.find_one({
                "_id": ObjectId(job_seeker_id),
                "isActive": True
            })
            
            if not job_seeker:
                return None
            
            # Build update document
            update_doc = {}
            
            # Handle top-level fields
            if "name" in update_fields:
                update_doc["name"] = update_fields["name"]
            if "phone" in update_fields:
                update_doc["phone"] = update_fields["phone"]
            
            # Handle profileJson fields
            profile_json = job_seeker.get("profileJson", {})
            
            if "bio" in update_fields:
                profile_json["bio"] = update_fields["bio"]
            if "location" in update_fields:
                profile_json["location"] = update_fields["location"]
            if "linkedinUrl" in update_fields:
                profile_json["linkedinUrl"] = update_fields["linkedinUrl"]
            if "githubUrl" in update_fields:
                profile_json["githubUrl"] = update_fields["githubUrl"]
            if "experience" in update_fields:
                profile_json["experience"] = update_fields["experience"]
            if "education" in update_fields:
                profile_json["education"] = update_fields["education"]
            if "skills" in update_fields:
                profile_json["skills"] = update_fields["skills"]
            
            update_doc["profileJson"] = profile_json
            
            # Recalculate profile completion
            update_doc["profileCompletion"] = self._calculate_profile_completion(
                name=update_doc.get("name", job_seeker.get("name")),
                email=job_seeker.get("email"),
                phone=update_doc.get("phone", job_seeker.get("phone")),
                resume_url=job_seeker.get("resumeUrl"),
                profile_json=profile_json
            )
            
            # Update timestamp
            update_doc["updatedAt"] = datetime.now(timezone.utc)
            
            # Update in database
            await jobSeekersCol.update_one(
                {"_id": ObjectId(job_seeker_id)},
                {"$set": update_doc}
            )
            
            # Get updated profile
            updated_profile = await self.get_profile(job_seeker_id)
            
            return updated_profile
            
        except Exception as e:
            print(f"Error updating profile: {e}")
            return None
    
    async def upload_resume(
        self,
        job_seeker_id: str,
        resume_url: str
    ) -> bool:
        """
        Update resume URL for job seeker
        
        Args:
            job_seeker_id: Job seeker ID
            resume_url: S3 URL to resume
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get current profile for recalculation
            job_seeker = await jobSeekersCol.find_one({
                "_id": ObjectId(job_seeker_id),
                "isActive": True
            })
            
            if not job_seeker:
                return False
            
            # Recalculate profile completion with new resume
            profile_completion = self._calculate_profile_completion(
                name=job_seeker.get("name"),
                email=job_seeker.get("email"),
                phone=job_seeker.get("phone"),
                resume_url=resume_url,
                profile_json=job_seeker.get("profileJson", {})
            )
            
            result = await jobSeekersCol.update_one(
                {"_id": ObjectId(job_seeker_id), "isActive": True},
                {
                    "$set": {
                        "resumeUrl": resume_url,
                        "profileCompletion": profile_completion,
                        "updatedAt": datetime.now(timezone.utc)
                    }
                }
            )
            
            return result.modified_count > 0
            
        except:
            return False
    
    def _calculate_profile_completion(
        self,
        name: str,
        email: str,
        phone: str,
        resume_url: Optional[str],
        profile_json: Dict
    ) -> int:
        """
        Calculate profile completion percentage
        
        Scoring:
        - name: 10%
        - email: 10%
        - phone: 10%
        - resumeUrl: 20%
        - at least 1 experience: 20%
        - at least 1 education: 15%
        - at least 3 skills: 15%
        
        Returns:
            Percentage (0-100)
        """
        score = 0
        
        # Basic fields (always present)
        if name:
            score += 10
        if email:
            score += 10
        if phone:
            score += 10
        
        # Resume
        if resume_url:
            score += 20
        
        # Experience
        experience = profile_json.get("experience", [])
        if len(experience) >= 1:
            score += 20
        
        # Education
        education = profile_json.get("education", [])
        if len(education) >= 1:
            score += 15
        
        # Skills
        skills = profile_json.get("skills", [])
        if len(skills) >= 3:
            score += 15
        
        return score
    
    # ============================================
    # Job Discovery
    # ============================================
    
    async def browse_jobs(
        self,
        search: Optional[str] = None,
        job_type: Optional[str] = None,
        experience: Optional[str] = None,
        location: Optional[str] = None,
        salary: Optional[str] = None,
        page: int = 1,
        limit: int = 20
    ) -> Dict:
        """
        Browse open jobs across all organizations
        
        Args:
            search: Search query (title, skills)
            job_type: Filter by job type
            experience: Filter by experience
            location: Filter by location
            salary: Filter by salary
            page: Page number (1-indexed)
            limit: Results per page
            
        Returns:
            Dictionary with jobs list and pagination info
        """
        # Build query
        query = {
            "status": "open",
            "isDeleted": False
        }
        
        # Search in title and skills
        if search:
            query["$or"] = [
                {"title": {"$regex": search, "$options": "i"}},
                {"skills": {"$regex": search, "$options": "i"}},
                {"orgName": {"$regex": search, "$options": "i"}}
            ]
        
        # Filters
        if job_type:
            query["type"] = job_type
        if experience:
            query["experience"] = {"$regex": experience, "$options": "i"}
        if location:
            query["location"] = {"$regex": location, "$options": "i"}
        if salary:
            query["salary"] = {"$regex": salary, "$options": "i"}
        
        # Count total
        total = await jobsCol.count_documents(query)
        
        # Calculate pagination
        skip = (page - 1) * limit
        total_pages = (total + limit - 1) // limit
        
        # Fetch jobs
        cursor = jobsCol.find(query).sort("createdAt", -1).skip(skip).limit(limit)
        jobs = await cursor.to_list(length=limit)
        
        # Convert ObjectId to string
        for job in jobs:
            job["_id"] = str(job["_id"])
        
        return {
            "jobs": jobs,
            "total": total,
            "page": page,
            "limit": limit,
            "totalPages": total_pages
        }
    
    async def save_job(
        self,
        job_seeker_id: str,
        job_id: str
    ) -> Dict:
        """
        Toggle save/unsave job
        
        Args:
            job_seeker_id: Job seeker ID
            job_id: Job ID
            
        Returns:
            Dictionary with saved status and updated savedJobs list
        """
        try:
            # Get current saved jobs
            job_seeker = await jobSeekersCol.find_one({
                "_id": ObjectId(job_seeker_id),
                "isActive": True
            })
            
            if not job_seeker:
                raise ValueError("Job seeker not found")
            
            saved_jobs = job_seeker.get("savedJobs", [])
            
            # Toggle save
            if job_id in saved_jobs:
                # Unsave
                saved_jobs.remove(job_id)
                action = "unsaved"
            else:
                # Save
                saved_jobs.append(job_id)
                action = "saved"
            
            # Update in database
            await jobSeekersCol.update_one(
                {"_id": ObjectId(job_seeker_id)},
                {
                    "$set": {
                        "savedJobs": saved_jobs,
                        "updatedAt": datetime.now(timezone.utc)
                    }
                }
            )
            
            return {
                "action": action,
                "savedJobs": saved_jobs
            }
            
        except Exception as e:
            raise ValueError(f"Error saving job: {e}")
    
    async def get_saved_jobs(
        self,
        job_seeker_id: str
    ) -> List[Dict]:
        """
        Get all saved jobs with full details
        
        Args:
            job_seeker_id: Job seeker ID
            
        Returns:
            List of job documents
        """
        try:
            # Get saved job IDs
            job_seeker = await jobSeekersCol.find_one({
                "_id": ObjectId(job_seeker_id),
                "isActive": True
            })
            
            if not job_seeker:
                return []
            
            saved_job_ids = job_seeker.get("savedJobs", [])
            
            if not saved_job_ids:
                return []
            
            # Convert to ObjectIds
            object_ids = []
            for job_id in saved_job_ids:
                try:
                    object_ids.append(ObjectId(job_id))
                except:
                    pass
            
            # Fetch jobs
            cursor = jobsCol.find({
                "_id": {"$in": object_ids},
                "status": "open",
                "isDeleted": False
            }).sort("createdAt", -1)
            
            jobs = await cursor.to_list(length=None)
            
            # Convert ObjectId to string
            for job in jobs:
                job["_id"] = str(job["_id"])
            
            return jobs
            
        except:
            return []
    
    # ============================================
    # Applications
    # ============================================
    
    async def apply_to_job(
        self,
        job_seeker_id: str,
        job_id: str
    ) -> Dict:
        """
        Apply to a job
        
        Args:
            job_seeker_id: Job seeker ID
            job_id: Job ID
            
        Returns:
            Created application document
        """
        # Get job seeker profile
        job_seeker = await jobSeekersCol.find_one({
            "_id": ObjectId(job_seeker_id),
            "isActive": True
        })
        
        if not job_seeker:
            raise ValueError("Job seeker not found")
        
        # Get job details
        job = await jobsCol.find_one({
            "_id": ObjectId(job_id),
            "status": "open",
            "isDeleted": False
        })
        
        if not job:
            raise ValueError("Job not found or not open")
        
        # Import applicationsCol (same collection as org uses)
        from core.database import applicationsCol
        
        # Check for duplicate application
        existing = await applicationsCol.find_one({
            "jobId": job_id,
            "jobSeekerId": job_seeker_id,
            "source": "JOB_PORTAL",
            "isDeleted": False
        })
        
        if existing:
            raise ValueError("You have already applied to this job")
        
        now = datetime.now(timezone.utc)
        
        # Create application with reference to job seeker (NO SNAPSHOT)
        # Profile data will be fetched live from job_seekers collection
        application_doc = {
            "jobId": job_id,
            "orgId": job.get("orgId"),
            "jobSeekerId": job_seeker_id,  # Reference to job_seekers collection
            
            # Application details
            "stage": "Applied",
            "source": "JOB_PORTAL",  # Mark as job portal application
            "notes": "",
            
            # Stage history
            "stageHistory": [
                {
                    "stage": "Applied",
                    "changedBy": "system",
                    "changedAt": now,
                    "notes": "Application submitted via Job Portal"
                }
            ],
            
            # Soft delete
            "isDeleted": False,
            "deletedAt": None,
            "deletedBy": None,
            
            # Metadata
            "appliedAt": now,
            "updatedAt": now
        }
        
        # Insert application into SAME collection as org applications
        result = await applicationsCol.insert_one(application_doc)
        application_doc["_id"] = str(result.inserted_id)
        
        # Increment job's applicant count
        await jobsCol.update_one(
            {"_id": ObjectId(job_id)},
            {
                "$inc": {"applicantCount": 1},
                "$set": {"updatedAt": now}
            }
        )
        
        return application_doc
    
    async def get_my_applications(
        self,
        job_seeker_id: str
    ) -> List[Dict]:
        """
        Get all applications for a job seeker with LIVE profile data
        
        Args:
            job_seeker_id: Job seeker ID
            
        Returns:
            List of application documents enriched with current job seeker profile and job details
        """
        try:
            # Import applicationsCol (same collection as org uses)
            from core.database import applicationsCol
            
            # Get applications where jobSeekerId matches
            cursor = applicationsCol.find({
                "jobSeekerId": job_seeker_id,
                "source": "JOB_PORTAL",
                "isDeleted": False
            }).sort("appliedAt", -1)
            
            applications = await cursor.to_list(length=None)
            
            # Get current job seeker profile (LIVE data)
            job_seeker = await jobSeekersCol.find_one({
                "_id": ObjectId(job_seeker_id),
                "isActive": True
            })
            
            # Enrich with job details and live profile
            for app in applications:
                app["_id"] = str(app["_id"])
                
                # Add LIVE job seeker profile data
                if job_seeker:
                    app["candidateProfile"] = {
                        "name": job_seeker.get("name"),
                        "email": job_seeker.get("email"),
                        "phone": job_seeker.get("phone"),
                        "resumeUrl": job_seeker.get("resumeUrl"),
                        "profileCompletion": job_seeker.get("profileCompletion", 0)
                    }
                
                # Get job details
                try:
                    job = await jobsCol.find_one({"_id": ObjectId(app["jobId"])})
                    if job:
                        job["_id"] = str(job["_id"])
                        app["jobDetails"] = {
                            "_id": job["_id"],
                            "title": job.get("title"),
                            "orgName": job.get("orgName"),
                            "location": job.get("location"),
                            "type": job.get("type"),
                            "status": job.get("status")
                        }
                except:
                    app["jobDetails"] = None
            
            return applications
            
        except:
            return []
    
    async def withdraw_application(
        self,
        job_seeker_id: str,
        application_id: str
    ) -> bool:
        """
        Withdraw (soft delete) an application
        
        Args:
            job_seeker_id: Job seeker ID
            application_id: Application ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            from core.database import applicationsCol
            
            # Verify application belongs to job seeker
            application = await applicationsCol.find_one({
                "_id": ObjectId(application_id),
                "jobSeekerId": job_seeker_id,
                "source": "JOB_PORTAL",
                "isDeleted": False
            })
            
            if not application:
                raise ValueError("Application not found or already withdrawn")
            
            # Soft delete
            now = datetime.now(timezone.utc)
            result = await applicationsCol.update_one(
                {"_id": ObjectId(application_id)},
                {
                    "$set": {
                        "isDeleted": True,
                        "deletedAt": now,
                        "deletedBy": job_seeker_id,
                        "updatedAt": now
                    }
                }
            )
            
            # Decrement job's applicant count
            if result.modified_count > 0:
                await jobsCol.update_one(
                    {"_id": ObjectId(application["jobId"])},
                    {
                        "$inc": {"applicantCount": -1},
                        "$set": {"updatedAt": now}
                    }
                )
            
            return result.modified_count > 0
            
        except Exception as e:
            print(f"Error withdrawing application: {e}")
            return False

