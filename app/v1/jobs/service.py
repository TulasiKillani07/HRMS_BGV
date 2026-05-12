"""
Business logic for Jobs ATS feature
"""
from typing import Dict, List, Optional
from datetime import datetime, timezone
from bson import ObjectId

# Import from core
from core.database import jobsCol, applicationsCol


class JobsService:
    """Service for handling job postings"""
    
    async def create_job(
        self,
        title: str,
        department: str,
        location: str,
        job_type: str,
        experience: str,
        salary: str,
        skills_string: str,
        description: str,
        status: str,
        deadline: Optional[str],
        org_id: str,
        creator_email: str
    ) -> Dict:
        """
        Create a new job posting
        
        Args:
            All job fields + org_id from user
            
        Returns:
            Created job document
        """
        from core.database import orgsCol
        
        # Fetch organization name
        org = await orgsCol.find_one({"_id": ObjectId(org_id)})
        if not org:
            raise ValueError("Organization not found")
        
        org_name = org.get("organizationName", "")
        
        now = datetime.now(timezone.utc)
        
        # Parse skills from comma-separated string
        skills = [s.strip() for s in skills_string.split(",") if s.strip()]
        
        # Parse deadline
        deadline_date = None
        if deadline:
            try:
                deadline_date = datetime.fromisoformat(deadline.replace('Z', '+00:00'))
            except:
                pass
        
        # Build job document
        job_doc = {
            "orgId": org_id,
            "orgName": org_name,
            "title": title,
            "department": department,
            "location": location,
            "type": job_type,
            "experience": experience,
            "salary": salary,
            "skills": skills,
            "description": description,
            "status": status,
            "deadline": deadline_date,
            
            # Initialize counts
            "applicantCount": 0,
            "shortlistedCount": 0,
            "hiredCount": 0,
            
            # Soft delete
            "isDeleted": False,
            "deletedAt": None,
            "deletedBy": None,
            
            # Metadata
            "createdBy": creator_email,
            "createdAt": now,
            "updatedAt": now
        }
        
        # Insert into database
        result = await jobsCol.insert_one(job_doc)
        job_doc["_id"] = str(result.inserted_id)
        
        return job_doc
    
    async def get_jobs(
        self,
        user_role: str,
        user_org_id: Optional[str],
        filter_org_id: Optional[str] = None,
        filter_status: Optional[str] = None,
        search_query: Optional[str] = None
    ) -> List[Dict]:
        """
        Get jobs based on role and filters
        
        Args:
            user_role: Role of requesting user
            user_org_id: Organization ID from JWT (for org roles)
            filter_org_id: Optional org filter (for superadmin)
            filter_status: Optional status filter
            search_query: Optional search in title/skills
            
        Returns:
            List of job documents
        """
        # Build query
        query = {"isDeleted": False}
        
        # Role-based filtering
        if user_role in ["ORG_HR", "SPOC", "HELPER"]:
            # Org roles see only their org's jobs
            query["orgId"] = user_org_id
        elif user_role in ["SUPER_ADMIN", "SUPER_SPOC", "SUPER_ADMIN_HELPER"]:
            # Superadmin can filter by org
            if filter_org_id:
                query["orgId"] = filter_org_id
        
        # Status filter
        if filter_status:
            query["status"] = filter_status
        
        # Search query
        if search_query:
            query["$or"] = [
                {"title": {"$regex": search_query, "$options": "i"}},
                {"skills": {"$regex": search_query, "$options": "i"}}
            ]
        
        # Fetch jobs
        cursor = jobsCol.find(query).sort("createdAt", -1)
        jobs = await cursor.to_list(length=None)
        
        # Convert ObjectId to string
        for job in jobs:
            job["_id"] = str(job["_id"])
        
        return jobs
    
    async def get_job_by_id(
        self,
        job_id: str,
        user_role: str,
        user_org_id: Optional[str]
    ) -> Optional[Dict]:
        """
        Get single job by ID with access control
        
        Args:
            job_id: Job ID
            user_role: Role of requesting user
            user_org_id: Organization ID from JWT
            
        Returns:
            Job document or None
        """
        try:
            # Validate ObjectId format
            if not ObjectId.is_valid(job_id):
                return None
            
            job = await jobsCol.find_one({
                "_id": ObjectId(job_id),
                "isDeleted": False
            })
            
            if not job:
                return None
            
            # Access control
            if user_role in ["ORG_HR", "SPOC", "HELPER"]:
                if job["orgId"] != user_org_id:
                    return None  # Not authorized
            
            job["_id"] = str(job["_id"])
            return job
            
        except Exception as e:
            print(f"Error in get_job_by_id: {str(e)}")
            return None
    
    async def update_job(
        self,
        job_id: str,
        update_fields: Dict,
        user_org_id: str
    ) -> Optional[Dict]:
        """
        Update job fields
        
        Args:
            job_id: Job ID
            update_fields: Fields to update
            user_org_id: Organization ID from JWT (for verification)
            
        Returns:
            Updated job document or None
        """
        try:
            # Verify ownership
            job = await jobsCol.find_one({
                "_id": ObjectId(job_id),
                "orgId": user_org_id,
                "isDeleted": False
            })
            
            if not job:
                return None
            
            # Parse skills if provided
            if "skills" in update_fields and isinstance(update_fields["skills"], str):
                update_fields["skills"] = [s.strip() for s in update_fields["skills"].split(",") if s.strip()]
            
            # Parse deadline if provided
            if "deadline" in update_fields and update_fields["deadline"]:
                try:
                    update_fields["deadline"] = datetime.fromisoformat(
                        update_fields["deadline"].replace('Z', '+00:00')
                    )
                except:
                    pass
            
            # Update timestamp
            update_fields["updatedAt"] = datetime.now(timezone.utc)
            
            # Update in database
            await jobsCol.update_one(
                {"_id": ObjectId(job_id)},
                {"$set": update_fields}
            )
            
            # Fetch updated job
            updated_job = await jobsCol.find_one({"_id": ObjectId(job_id)})
            updated_job["_id"] = str(updated_job["_id"])
            
            return updated_job
            
        except:
            return None
    
    async def delete_job(
        self,
        job_id: str,
        user_org_id: str,
        user_email: str
    ) -> bool:
        """
        Soft delete job and cascade delete applications
        
        Args:
            job_id: Job ID
            user_org_id: Organization ID from JWT (for verification)
            user_email: Email of user deleting
            
        Returns:
            True if deleted, False otherwise
        """
        try:
            # Verify ownership
            job = await jobsCol.find_one({
                "_id": ObjectId(job_id),
                "orgId": user_org_id,
                "isDeleted": False
            })
            
            if not job:
                return False
            
            now = datetime.now(timezone.utc)
            
            # Soft delete job
            await jobsCol.update_one(
                {"_id": ObjectId(job_id)},
                {
                    "$set": {
                        "isDeleted": True,
                        "deletedAt": now,
                        "deletedBy": user_email,
                        "updatedAt": now
                    }
                }
            )
            
            # Soft delete all applications for this job
            await applicationsCol.update_many(
                {"jobId": job_id, "isDeleted": False},
                {
                    "$set": {
                        "isDeleted": True,
                        "deletedAt": now,
                        "deletedBy": user_email,
                        "updatedAt": now
                    }
                }
            )
            
            return True
            
        except:
            return False
    
    async def duplicate_job(
        self,
        job_id: str,
        user_org_id: str,
        user_email: str
    ) -> Optional[Dict]:
        """
        Duplicate an existing job
        
        Args:
            job_id: Job ID to duplicate
            user_org_id: Organization ID from JWT
            user_email: Email of user duplicating
            
        Returns:
            New job document or None
        """
        try:
            # Get original job
            original_job = await jobsCol.find_one({
                "_id": ObjectId(job_id),
                "orgId": user_org_id,
                "isDeleted": False
            })
            
            if not original_job:
                return None
            
            now = datetime.now(timezone.utc)
            
            # Create duplicate
            new_job = {
                "orgId": original_job["orgId"],
                "orgName": original_job["orgName"],
                "title": f"{original_job['title']} (Copy)",
                "department": original_job["department"],
                "location": original_job["location"],
                "type": original_job["type"],
                "experience": original_job["experience"],
                "salary": original_job["salary"],
                "skills": original_job["skills"],
                "description": original_job["description"],
                "status": "draft",  # Always start as draft
                "deadline": original_job.get("deadline"),
                
                # Reset counts
                "applicantCount": 0,
                "shortlistedCount": 0,
                "hiredCount": 0,
                
                # Soft delete
                "isDeleted": False,
                "deletedAt": None,
                "deletedBy": None,
                
                # Metadata
                "createdBy": user_email,
                "createdAt": now,
                "updatedAt": now
            }
            
            # Insert
            result = await jobsCol.insert_one(new_job)
            new_job["_id"] = str(result.inserted_id)
            
            return new_job
            
        except:
            return None
    
    async def change_job_status(
        self,
        job_id: str,
        new_status: str,
        user_org_id: str
    ) -> bool:
        """
        Change job status (open/closed)
        
        Args:
            job_id: Job ID
            new_status: New status ("open" or "closed")
            user_org_id: Organization ID from JWT
            
        Returns:
            True if updated, False otherwise
        """
        try:
            result = await jobsCol.update_one(
                {
                    "_id": ObjectId(job_id),
                    "orgId": user_org_id,
                    "isDeleted": False
                },
                {
                    "$set": {
                        "status": new_status,
                        "updatedAt": datetime.now(timezone.utc)
                    }
                }
            )
            
            return result.modified_count > 0
            
        except:
            return False
    
    async def auto_close_expired_jobs(self):
        """
        Auto-close jobs that have passed their deadline
        Called by a background task/cron job
        
        Returns:
            Number of jobs closed
        """
        now = datetime.now(timezone.utc)
        
        result = await jobsCol.update_many(
            {
                "status": "open",
                "deadline": {"$lte": now},
                "isDeleted": False
            },
            {
                "$set": {
                    "status": "closed",
                    "updatedAt": now
                }
            }
        )
        
        return result.modified_count
