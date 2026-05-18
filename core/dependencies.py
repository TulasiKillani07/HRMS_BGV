"""
Shared dependencies for FastAPI routes
Extracted to avoid circular imports
"""
from fastapi import Request, HTTPException
from typing import Optional
from bson import ObjectId
import time
import os
import hmac
import hashlib
import base64
import json
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import from core
from core.database import usersCol, orgsCol, activityLogsCol

# Cookie name for session
cookieName = "bgvSession"

# Session secret (HMAC-based, not JWT)
sessionSecret = b"super-secret-key"


def decodeToken(token: str) -> dict:
    """Decode HMAC token (not JWT)"""
    try:
        bodyB64, sigB64 = token.split(".", 1)
        body = base64.urlsafe_b64decode(bodyB64 + "==")
        sig = base64.urlsafe_b64decode(sigB64 + "==")
        expected = hmac.new(sessionSecret, body, hashlib.sha256).digest()
        if not hmac.compare_digest(sig, expected):
            raise ValueError("bad signature")
        data = json.loads(body)
        
        # Check expiration
        if "exp" in data and data["exp"] < int(time.time()):
            raise HTTPException(status_code=401, detail="token expired")
        
        return data
    except ValueError as e:
        raise HTTPException(status_code=401, detail=f"invalid token: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=401, detail="invalid token")


async def requireAuth(request: Request):
    """
    Authentication dependency for protected routes
    """
    token = request.cookies.get(cookieName)

    # Fallback for Postman / mobile clients
    if not token:
        authHeader = request.headers.get("Authorization")
        if authHeader and authHeader.startswith("Bearer "):
            token = authHeader.split("Bearer ")[1].strip()

    if not token:
        raise HTTPException(status_code=401, detail="no session cookie")

    data = decodeToken(token)
    
    # 🔒 SECURITY: Reject JOBSEEKER role from org/admin endpoints
    if data.get("role") == "JOBSEEKER":
        raise HTTPException(status_code=403, detail="Access denied: Job seekers cannot access this endpoint")
    
    user = await usersCol.find_one({"email": data["email"], "isActive": True})
    if not user:
        raise HTTPException(status_code=401, detail="user not found")
    return user


async def resolveNamesInDescription(description: str) -> str:
    """
    Resolve IDs in description to names
    """
    # Simple implementation - just return description as-is
    # The full implementation from main.py can be added if needed
    return description


async def logActivity(user, action, description, status):
    """
    Log user activity to activity logs collection
    """
    # SELF-verification (public endpoint): no authenticated user
    if user is None:
        userId = None
        userEmail = "self-verification"
        userRole = "SELF"
        orgId = None
        orgName = None
        userName = "Self Verification"
    else:
        userId = str(user.get("_id")) if user.get("_id") else None
        userEmail = user.get("email")
        userRole = user.get("role")
        orgId = str(user.get("organizationId")) if user.get("organizationId") else None
        
        # Get user's name from database
        userName = userEmail  # Default fallback
        if userId:
            try:
                user_record = await usersCol.find_one({"_id": ObjectId(userId)})
                if user_record:
                    user_name = user_record.get('userName', '')
                    if user_name:
                        userName = user_name
            except:
                pass
        
        # Get organization name from database
        orgName = None
        if orgId:
            try:
                organization = await orgsCol.find_one({"_id": ObjectId(orgId)})
                if organization:
                    orgName = organization.get('organizationName') or organization.get('name', '')
            except Exception as e:
                print(f"❌ Error fetching org {orgId}: {e}")
                pass

    # Enhance description with names
    enhanced_description = await resolveNamesInDescription(description)

    # Convert timestamp to IST (UTC+5:30)
    utc_now = datetime.now(timezone.utc)
    ist_offset = timedelta(hours=5, minutes=30)
    ist_now = utc_now + ist_offset

    log_entry = {
        "userId": userId,
        "userEmail": userEmail,
        "userName": userName,
        "userRole": userRole,
        "organizationId": orgId,
        "organizationName": orgName,
        "action": action,
        "description": enhanced_description,
        "status": status,
        "timestamp": ist_now,
        "createdAt": utc_now
    }

    try:
        await activityLogsCol.insert_one(log_entry)
    except Exception as e:
        print(f"❌ Error logging activity: {e}")
