"""
Business logic for Applications ATS feature
"""
from typing import Dict, List, Optional
from datetime import datetime, timezone
from bson import ObjectId

# Import from core
from core.database import applicationsCol, jobsCol, candidatesCol


class ApplicationsService:
    """Service for handling job applications"""
    
    async def create_application(
        self,
        job_id: str,
        candidate_id: str,
        source: str,
        stage: str = None,
        ai_score: Optional[float] = None,
        notes: str = "",
        org_id: str = ""
    ) -> Dict:
        """
        Create a new application
        
        Args:
            job_id: Job ID
            candidate_id: Candidate ID
            source: Application source (AI_SCREENING, JOB_PORTAL, MANUAL)
            stage: Initial stage (optional - auto-determined from source if not provided)
            ai_score: AI score if from AI screening
            notes: Initial notes
            org_id: Organization ID
            
        Returns:
            Created application document
        """
        # Get candidate details
        candidate = await candidatesCol.find_one({"_id": ObjectId(candidate_id)})
        if not candidate:
            raise ValueError("Candidate not found")
        
        candidate_email = candidate.get("email", "")
        
        # Check for duplicate application for this job
        existing = await applicationsCol.find_one({
            "jobId": job_id,
            "candidateEmail": candidate_email,
            "isDeleted": False
        })
        
        if existing:
            raise ValueError("Candidate has already applied to this job")
        
        # If adding manual candidate, check if email exists in job_seekers
        if source == "MANUAL" and candidate_email:
            from core.database import jobSeekersCol
            existing_job_seeker = await jobSeekersCol.find_one({
                "email": candidate_email,
                "isActive": True
            })
            if existing_job_seeker:
                raise ValueError(f"A job seeker with email {candidate_email} already exists. Cannot add as manual candidate.")
        
        # Auto-determine stage based on source if not provided
        if stage is None:
            if source == "MANUAL":
                stage = "Resume Shortlist"  # HR already reviewed resume
            elif source == "AI_SCREENING":
                stage = "Resume Shortlist"  # AI already screened
            else:  # JOB_PORTAL
                stage = "Applied"  # Needs review
        
        now = datetime.now(timezone.utc)
        
        # Build application document
        app_doc = {
            "jobId": job_id,
            "orgId": org_id,
            "candidateId": candidate_id,
            
            # Denormalized candidate info
            "candidateName": f"{candidate.get('firstName', '')} {candidate.get('lastName', '')}".strip(),
            "candidateEmail": candidate_email,
            "candidatePhone": candidate.get("phone", ""),
            "resumeUrl": candidate.get("resumePath", ""),
            
            # Application details
            "stage": stage,
            "source": source,
            "aiScore": ai_score,
            "notes": notes,
            
            # Stage history
            "stageHistory": [
                {
                    "stage": stage,
                    "changedBy": "system",
                    "changedAt": now,
                    "notes": f"Application created via {source}"
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
        
        # Insert application
        result = await applicationsCol.insert_one(app_doc)
        app_doc["_id"] = str(result.inserted_id)
        
        # Update job counts
        await self._update_job_counts(job_id)
        
        return app_doc
    
    async def get_applications_for_job(
        self,
        job_id: str,
        user_org_id: str
    ) -> Dict:
        """
        Get all applications for a job (pipeline view)
        Fetches live profile data from job_seekers collection
        
        Args:
            job_id: Job ID
            user_org_id: Organization ID from JWT
            
        Returns:
            Dictionary with applications list and stage counts
        """
        from core.database import jobSeekersCol
        
        # Validate ObjectId format
        if not ObjectId.is_valid(job_id):
            raise ValueError("Invalid job ID format")
        
        # Verify job belongs to user's org
        job = await jobsCol.find_one({
            "_id": ObjectId(job_id),
            "orgId": user_org_id,
            "isDeleted": False
        })
        
        if not job:
            raise ValueError("Job not found or access denied")
        
        # Get all applications
        cursor = applicationsCol.find({
            "jobId": job_id,
            "isDeleted": False
        }).sort("appliedAt", -1)
        
        applications = await cursor.to_list(length=None)
        
        # Fetch live profile from job_seekers for ALL applications
        for app in applications:
            app["_id"] = str(app["_id"])
            
            # Fetch job seeker profile (all applications reference job_seekers)
            if app.get("jobSeekerId"):
                try:
                    job_seeker = await jobSeekersCol.find_one({
                        "_id": ObjectId(app["jobSeekerId"]),
                        "isActive": True
                    })
                    
                    if job_seeker:
                        # Set live profile data
                        app["jobSeekerName"] = job_seeker.get("name")
                        app["jobSeekerEmail"] = job_seeker.get("email")
                        app["jobSeekerPhone"] = job_seeker.get("phone")
                        app["resumeUrl"] = job_seeker.get("resumeUrl", "")
                        
                        # Add detailed profile
                        app["jobSeekerProfile"] = {
                            "name": job_seeker.get("name"),
                            "email": job_seeker.get("email"),
                            "phone": job_seeker.get("phone"),
                            "resumeUrl": job_seeker.get("resumeUrl"),
                            "profileCompletion": job_seeker.get("profileCompletion", 0),
                            "experience": job_seeker.get("profileJson", {}).get("experience", []),
                            "education": job_seeker.get("profileJson", {}).get("education", []),
                            "skills": job_seeker.get("profileJson", {}).get("skills", [])
                        }
                    else:
                        # Job seeker not found or inactive
                        app["jobSeekerName"] = "Unknown"
                        app["jobSeekerEmail"] = "unknown@example.com"
                        app["jobSeekerPhone"] = ""
                        app["resumeUrl"] = ""
                except Exception as e:
                    print(f"Error fetching job seeker profile: {e}")
                    # Set defaults if fetch fails
                    app["jobSeekerName"] = "Unknown"
                    app["jobSeekerEmail"] = "unknown@example.com"
                    app["jobSeekerPhone"] = ""
                    app["resumeUrl"] = ""
        
        # Calculate stage counts
        stage_counts = {}
        for app in applications:
            stage = app.get("stage", "Applied")
            stage_counts[stage] = stage_counts.get(stage, 0) + 1
        
        return {
            "applications": applications,
            "total": len(applications),
            "stageCounts": stage_counts
        }
    
    async def get_application_by_id(
        self,
        application_id: str,
        user_org_id: str
    ) -> Optional[Dict]:
        """
        Get single application details
        
        Args:
            application_id: Application ID
            user_org_id: Organization ID from JWT
            
        Returns:
            Application document or None
        """
        try:
            app = await applicationsCol.find_one({
                "_id": ObjectId(application_id),
                "orgId": user_org_id,
                "isDeleted": False
            })
            
            if app:
                app["_id"] = str(app["_id"])
            
            return app
            
        except:
            return None
    
    async def update_application_stage(
        self,
        application_id: str,
        new_stage: str,
        notes: str,
        user_org_id: str,
        user_email: str
    ) -> Optional[Dict]:
        """
        Update application stage and track history
        
        Args:
            application_id: Application ID
            new_stage: New stage
            notes: Notes about stage change
            user_org_id: Organization ID from JWT
            user_email: Email of user making change
            
        Returns:
            Updated application or None
        """
        try:
            # Get current application
            app = await applicationsCol.find_one({
                "_id": ObjectId(application_id),
                "orgId": user_org_id,
                "isDeleted": False
            })
            
            if not app:
                return None
            
            old_stage = app.get("stage")
            job_id = app.get("jobId")
            now = datetime.now(timezone.utc)
            
            # Add to stage history
            stage_history_entry = {
                "stage": new_stage,
                "changedBy": user_email,
                "changedAt": now,
                "notes": notes or f"Moved from {old_stage} to {new_stage}"
            }
            
            # Update application
            await applicationsCol.update_one(
                {"_id": ObjectId(application_id)},
                {
                    "$set": {
                        "stage": new_stage,
                        "updatedAt": now
                    },
                    "$push": {
                        "stageHistory": stage_history_entry
                    }
                }
            )
            
            # Update job counts if stage changed
            if old_stage != new_stage:
                await self._update_job_counts(job_id)
            
            # Get updated application
            updated_app = await applicationsCol.find_one({"_id": ObjectId(application_id)})
            updated_app["_id"] = str(updated_app["_id"])
            
            return updated_app
            
        except:
            return None
    
    async def bulk_update_stage(
        self,
        application_ids: List[str],
        new_stage: str,
        notes: str,
        user_org_id: str,
        user_email: str
    ) -> Dict:
        """
        Update multiple applications to same stage
        
        Args:
            application_ids: List of application IDs
            new_stage: New stage
            notes: Notes about stage change
            user_org_id: Organization ID from JWT
            user_email: Email of user making change
            
        Returns:
            Dictionary with success/failure counts
        """
        success_count = 0
        failed_count = 0
        job_ids = set()
        
        for app_id in application_ids:
            try:
                result = await self.update_application_stage(
                    application_id=app_id,
                    new_stage=new_stage,
                    notes=notes,
                    user_org_id=user_org_id,
                    user_email=user_email
                )
                
                if result:
                    success_count += 1
                    job_ids.add(result.get("jobId"))
                else:
                    failed_count += 1
                    
            except:
                failed_count += 1
        
        # Update counts for all affected jobs
        for job_id in job_ids:
            await self._update_job_counts(job_id)
        
        return {
            "total": len(application_ids),
            "successful": success_count,
            "failed": failed_count
        }
    
    async def add_note(
        self,
        application_id: str,
        note: str,
        user_org_id: str
    ) -> bool:
        """
        Add note to application
        
        Args:
            application_id: Application ID
            note: Note text
            user_org_id: Organization ID from JWT
            
        Returns:
            True if successful, False otherwise
        """
        try:
            result = await applicationsCol.update_one(
                {
                    "_id": ObjectId(application_id),
                    "orgId": user_org_id,
                    "isDeleted": False
                },
                {
                    "$set": {
                        "notes": note,
                        "updatedAt": datetime.now(timezone.utc)
                    }
                }
            )
            
            return result.modified_count > 0
            
        except:
            return False
    
    async def delete_application(
        self,
        application_id: str,
        user_org_id: str,
        user_email: str
    ) -> bool:
        """
        Soft delete application
        
        Args:
            application_id: Application ID
            user_org_id: Organization ID from JWT
            user_email: Email of user deleting
            
        Returns:
            True if deleted, False otherwise
        """
        try:
            # Get application
            app = await applicationsCol.find_one({
                "_id": ObjectId(application_id),
                "orgId": user_org_id,
                "isDeleted": False
            })
            
            if not app:
                return False
            
            job_id = app.get("jobId")
            now = datetime.now(timezone.utc)
            
            # Soft delete
            await applicationsCol.update_one(
                {"_id": ObjectId(application_id)},
                {
                    "$set": {
                        "isDeleted": True,
                        "deletedAt": now,
                        "deletedBy": user_email,
                        "updatedAt": now
                    }
                }
            )
            
            # Update job counts
            await self._update_job_counts(job_id)
            
            return True
            
        except:
            return False
    
    async def _update_job_counts(self, job_id: str):
        """
        Update job's applicant, shortlisted, and hired counts
        
        Args:
            job_id: Job ID
        """
        try:
            # Count applications by stage
            pipeline = [
                {
                    "$match": {
                        "jobId": job_id,
                        "isDeleted": False
                    }
                },
                {
                    "$group": {
                        "_id": "$stage",
                        "count": {"$sum": 1}
                    }
                }
            ]
            
            cursor = applicationsCol.aggregate(pipeline)
            stage_counts = {doc["_id"]: doc["count"] async for doc in cursor}
            
            # Calculate counts
            total_count = sum(stage_counts.values())
            shortlisted_count = stage_counts.get("Shortlisted", 0)
            hired_count = stage_counts.get("Hired", 0)
            
            # Update job
            await jobsCol.update_one(
                {"_id": ObjectId(job_id)},
                {
                    "$set": {
                        "applicantCount": total_count,
                        "shortlistedCount": shortlisted_count,
                        "hiredCount": hired_count,
                        "updatedAt": datetime.now(timezone.utc)
                    }
                }
            )
            
        except Exception as e:
            print(f"Error updating job counts: {e}")
    
    async def smart_shortlist_applications(
        self,
        job_id: str,
        user_org_id: str,
        criteria_type: str,
        criteria_value: float,
        preview_only: bool = False,
        manual_adjustments: Optional[List[str]] = None,
        user_email: str = ""
    ) -> Dict:
        """
        Smart shortlist applications based on criteria
        
        Args:
            job_id: Job ID
            user_org_id: Organization ID from JWT
            criteria_type: "percentage" or "number"
            criteria_value: Percentage (1-100) or number of applications
            preview_only: If True, only return preview without updating
            manual_adjustments: Optional list of application IDs to include/exclude
            user_email: Email of user performing action
            
        Returns:
            Dictionary with preview and update status
        """
        from core.database import jobSeekersCol
        
        # Validate ObjectId format
        if not ObjectId.is_valid(job_id):
            raise ValueError("Invalid job ID format")
        
        # Verify job belongs to user's org
        job = await jobsCol.find_one({
            "_id": ObjectId(job_id),
            "orgId": user_org_id,
            "isDeleted": False
        })
        
        if not job:
            raise ValueError("Job not found or access denied")
        
        # Get all applications in "Applied" stage
        cursor = applicationsCol.find({
            "jobId": job_id,
            "stage": "Applied",
            "isDeleted": False
        })
        
        applications = await cursor.to_list(length=None)
        
        if not applications:
            raise ValueError("No applications in 'Applied' stage to shortlist")
        
        # Enrich with job seeker data and calculate sort score
        enriched_apps = []
        
        for app in applications:
            app["_id"] = str(app["_id"])
            
            # Fetch job seeker profile
            job_seeker = None
            if app.get("jobSeekerId"):
                try:
                    job_seeker = await jobSeekersCol.find_one({
                        "_id": ObjectId(app["jobSeekerId"]),
                        "isActive": True
                    })
                except:
                    pass
            
            # Get AI score and profile completion
            ai_score = app.get("aiScore")
            profile_completion = 0
            job_seeker_name = "Unknown"
            job_seeker_email = "unknown@example.com"
            
            if job_seeker:
                profile_completion = job_seeker.get("profileCompletion", 0)
                job_seeker_name = job_seeker.get("name", "Unknown")
                job_seeker_email = job_seeker.get("email", "unknown@example.com")
            
            # Calculate sort score (AI score takes priority, fallback to profile completion)
            if ai_score is not None and ai_score > 0:
                sort_score = ai_score
            else:
                sort_score = profile_completion
            
            enriched_apps.append({
                "applicationId": app["_id"],
                "jobSeekerId": app.get("jobSeekerId", ""),
                "jobSeekerName": job_seeker_name,
                "jobSeekerEmail": job_seeker_email,
                "aiScore": ai_score,
                "profileCompletion": profile_completion,
                "sortScore": sort_score,
                "currentStage": app.get("stage", "Applied")
            })
        
        # Sort by sort_score (descending)
        enriched_apps.sort(key=lambda x: x["sortScore"], reverse=True)
        
        # Calculate how many to shortlist
        total_apps = len(enriched_apps)
        
        if criteria_type == "percentage":
            # Calculate number based on percentage
            num_to_shortlist = max(1, int((criteria_value / 100) * total_apps))
        else:  # number
            # Use the number directly
            num_to_shortlist = min(int(criteria_value), total_apps)
        
        # Mark which applications will be shortlisted
        for idx, app in enumerate(enriched_apps):
            app["willBeShortlisted"] = idx < num_to_shortlist
        
        # Apply manual adjustments if provided
        if manual_adjustments:
            for app in enriched_apps:
                if app["applicationId"] in manual_adjustments:
                    # Toggle the selection
                    app["willBeShortlisted"] = not app["willBeShortlisted"]
        
        # Count final shortlist
        final_shortlist_count = sum(1 for app in enriched_apps if app["willBeShortlisted"])
        
        # If not preview only, update applications
        updated_count = 0
        if not preview_only:
            now = datetime.now(timezone.utc)
            
            for app in enriched_apps:
                if app["willBeShortlisted"]:
                    try:
                        # Update application stage
                        await applicationsCol.update_one(
                            {"_id": ObjectId(app["applicationId"])},
                            {
                                "$set": {
                                    "stage": "Resume Shortlist",
                                    "updatedAt": now
                                },
                                "$push": {
                                    "stageHistory": {
                                        "stage": "Resume Shortlist",
                                        "changedBy": user_email,
                                        "changedAt": now,
                                        "notes": f"Smart shortlisted via {criteria_type}: {criteria_value}"
                                    }
                                }
                            }
                        )
                        updated_count += 1
                    except Exception as e:
                        print(f"Error updating application {app['applicationId']}: {e}")
            
            # Update job counts
            await self._update_job_counts(job_id)
        
        return {
            "message": "Preview generated" if preview_only else f"Successfully shortlisted {updated_count} applications",
            "jobId": job_id,
            "criteriaType": criteria_type,
            "criteriaValue": criteria_value,
            "totalApplications": total_apps,
            "applicationsToShortlist": final_shortlist_count,
            "preview": enriched_apps,
            "updated": not preview_only,
            "updatedCount": updated_count if not preview_only else None
        }
