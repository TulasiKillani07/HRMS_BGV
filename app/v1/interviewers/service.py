"""
Business logic for Interviewer Management
"""
from typing import Dict, List, Optional
from datetime import datetime, timezone
from bson import ObjectId

# Import from core
from core.database import interviewersCol, interviewsCol, orgsCol


class InterviewerService:
    """Service for handling interviewer operations"""
    
    async def create_interviewer(
        self,
        name: str,
        email: str,
        phone: str,
        designation: str,
        department: str,
        expertise: List[str],
        round_preferences: List[int],
        availability_notes: Optional[str],
        org_id: str,
        user_email: str
    ) -> Dict:
        """
        Create a new interviewer
        
        Args:
            name: Interviewer name
            email: Interviewer email
            phone: Interviewer phone
            designation: Job designation
            department: Department
            expertise: List of skills/expertise
            round_preferences: Preferred rounds (1-4)
            availability_notes: Availability notes
            org_id: Organization ID
            user_email: Email of user creating interviewer
            
        Returns:
            Created interviewer document
        """
        # Check for duplicate email in same organization
        existing = await interviewersCol.find_one({
            "email": email,
            "organizationId": org_id,
            "isDeleted": False
        })
        
        if existing:
            raise ValueError(f"Interviewer with email {email} already exists in your organization")
        
        # Get organization name
        org = await orgsCol.find_one({"_id": ObjectId(org_id)})
        org_name = org.get("organizationName", "Unknown") if org else "Unknown"
        
        now = datetime.now(timezone.utc)
        
        # Build interviewer document
        interviewer_doc = {
            "name": name,
            "email": email,
            "phone": phone,
            "designation": designation,
            "department": department,
            "organizationId": org_id,
            "organizationName": org_name,
            
            # Expertise and preferences
            "expertise": expertise or [],
            "roundPreferences": round_preferences or [],
            
            # Availability
            "isActive": True,
            "isAvailable": True,
            "availabilityNotes": availability_notes or "",
            
            # Statistics (initialized to zero)
            "stats": {
                "totalInterviewsConducted": 0,
                "upcomingInterviews": 0,
                "averageRating": None,
                "passRate": None
            },
            
            # Metadata
            "createdAt": now,
            "createdBy": user_email,
            "updatedAt": now,
            "isDeleted": False,
            "deletedAt": None,
            "deletedBy": None
        }
        
        # Insert interviewer
        result = await interviewersCol.insert_one(interviewer_doc)
        interviewer_doc["_id"] = str(result.inserted_id)
        interviewer_doc["interviewerId"] = str(result.inserted_id)
        
        return interviewer_doc
    
    async def get_interviewers(
        self,
        org_id: str,
        is_active: Optional[bool] = None,
        is_available: Optional[bool] = None,
        department: Optional[str] = None
    ) -> List[Dict]:
        """
        Get all interviewers for an organization with optional filters
        
        Args:
            org_id: Organization ID
            is_active: Filter by active status
            is_available: Filter by availability
            department: Filter by department
            
        Returns:
            List of interviewer documents
        """
        # Build query
        query = {
            "organizationId": org_id,
            "isDeleted": False
        }
        
        if is_active is not None:
            query["isActive"] = is_active
        
        if is_available is not None:
            query["isAvailable"] = is_available
        
        if department:
            query["department"] = department
        
        # Fetch interviewers
        cursor = interviewersCol.find(query).sort("name", 1)
        interviewers = await cursor.to_list(length=None)
        
        # Add interviewerId and convert ObjectId to string
        for interviewer in interviewers:
            interviewer["_id"] = str(interviewer["_id"])
            interviewer["interviewerId"] = interviewer["_id"]
        
        return interviewers
    
    async def get_interviewer_by_id(
        self,
        interviewer_id: str,
        org_id: str
    ) -> Optional[Dict]:
        """
        Get single interviewer details
        
        Args:
            interviewer_id: Interviewer ID
            org_id: Organization ID
            
        Returns:
            Interviewer document or None
        """
        try:
            interviewer = await interviewersCol.find_one({
                "_id": ObjectId(interviewer_id),
                "organizationId": org_id,
                "isDeleted": False
            })
            
            if interviewer:
                interviewer["_id"] = str(interviewer["_id"])
                interviewer["interviewerId"] = interviewer["_id"]
                
                # Calculate real-time statistics
                await self._update_interviewer_stats(interviewer_id, org_id)
                
                # Fetch updated stats
                updated = await interviewersCol.find_one({"_id": ObjectId(interviewer_id)})
                if updated:
                    interviewer["stats"] = updated.get("stats", {})
            
            return interviewer
            
        except:
            return None
    
    async def update_interviewer(
        self,
        interviewer_id: str,
        org_id: str,
        update_data: Dict,
        user_email: str
    ) -> Optional[Dict]:
        """
        Update interviewer details
        
        Args:
            interviewer_id: Interviewer ID
            org_id: Organization ID
            update_data: Fields to update
            user_email: Email of user updating
            
        Returns:
            Updated interviewer or None
        """
        try:
            # Check if interviewer exists
            interviewer = await interviewersCol.find_one({
                "_id": ObjectId(interviewer_id),
                "organizationId": org_id,
                "isDeleted": False
            })
            
            if not interviewer:
                return None
            
            # Build update document
            update_doc = {
                "updatedAt": datetime.now(timezone.utc)
            }
            
            # Add fields to update
            for key, value in update_data.items():
                if value is not None:
                    update_doc[key] = value
            
            # Update interviewer
            await interviewersCol.update_one(
                {"_id": ObjectId(interviewer_id)},
                {"$set": update_doc}
            )
            
            # Get updated interviewer
            updated = await self.get_interviewer_by_id(interviewer_id, org_id)
            return updated
            
        except:
            return None
    
    async def delete_interviewer(
        self,
        interviewer_id: str,
        org_id: str,
        user_email: str
    ) -> bool:
        """
        Soft delete interviewer
        
        Args:
            interviewer_id: Interviewer ID
            org_id: Organization ID
            user_email: Email of user deleting
            
        Returns:
            True if deleted, False otherwise
        """
        try:
            # Check if interviewer exists
            interviewer = await interviewersCol.find_one({
                "_id": ObjectId(interviewer_id),
                "organizationId": org_id,
                "isDeleted": False
            })
            
            if not interviewer:
                return False
            
            # Check if interviewer has upcoming interviews
            upcoming_count = await interviewsCol.count_documents({
                "rounds.interviewerId": interviewer_id,
                "rounds.status": {"$in": ["Scheduled", "Pending"]},
                "isDeleted": False
            })
            
            if upcoming_count > 0:
                raise ValueError(f"Cannot delete interviewer with {upcoming_count} upcoming interviews")
            
            now = datetime.now(timezone.utc)
            
            # Soft delete
            await interviewersCol.update_one(
                {"_id": ObjectId(interviewer_id)},
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
            
        except ValueError:
            raise
        except:
            return False
    
    async def _update_interviewer_stats(
        self,
        interviewer_id: str,
        org_id: str
    ):
        """
        Calculate and update interviewer statistics
        
        Args:
            interviewer_id: Interviewer ID
            org_id: Organization ID
        """
        try:
            # Count total interviews conducted (completed rounds)
            total_conducted = await interviewsCol.count_documents({
                "organizationId": org_id,
                "rounds": {
                    "$elemMatch": {
                        "interviewerId": interviewer_id,
                        "status": {"$in": ["Passed", "Failed"]}
                    }
                },
                "isDeleted": False
            })
            
            # Count upcoming interviews (scheduled or pending)
            upcoming = await interviewsCol.count_documents({
                "organizationId": org_id,
                "rounds": {
                    "$elemMatch": {
                        "interviewerId": interviewer_id,
                        "status": {"$in": ["Scheduled", "Pending"]}
                    }
                },
                "isDeleted": False
            })
            
            # Calculate average rating and pass rate
            pipeline = [
                {"$match": {
                    "organizationId": org_id,
                    "isDeleted": False
                }},
                {"$unwind": "$rounds"},
                {"$match": {
                    "rounds.interviewerId": interviewer_id,
                    "rounds.status": {"$in": ["Passed", "Failed"]}
                }},
                {"$group": {
                    "_id": None,
                    "avgRating": {"$avg": "$rounds.rating"},
                    "totalRounds": {"$sum": 1},
                    "passedRounds": {
                        "$sum": {"$cond": [{"$eq": ["$rounds.status", "Passed"]}, 1, 0]}
                    }
                }}
            ]
            
            cursor = interviewsCol.aggregate(pipeline)
            stats_result = await cursor.to_list(length=1)
            
            avg_rating = None
            pass_rate = None
            
            if stats_result:
                result = stats_result[0]
                avg_rating = round(result.get("avgRating", 0), 2) if result.get("avgRating") else None
                total_rounds = result.get("totalRounds", 0)
                passed_rounds = result.get("passedRounds", 0)
                pass_rate = round(passed_rounds / total_rounds, 2) if total_rounds > 0 else None
            
            # Update stats
            await interviewersCol.update_one(
                {"_id": ObjectId(interviewer_id)},
                {
                    "$set": {
                        "stats": {
                            "totalInterviewsConducted": total_conducted,
                            "upcomingInterviews": upcoming,
                            "averageRating": avg_rating,
                            "passRate": pass_rate
                        }
                    }
                }
            )
            
        except Exception as e:
            print(f"Error updating interviewer stats: {e}")
