from datetime import datetime, timezone, timedelta
from bson import ObjectId
from utils.email_utils import send_ticket_email
import random

# ------------------------------
# Ticket Categories & SLA
# ------------------------------
TICKET_CATEGORIES = {
    "IT_ISSUE": {
        "label": "IT Support",
        "assignTo": "IT_TEAM",
        "priority": "HIGH",
        "sla_hours": 4,
        "description": "Technical issues, login problems, system errors"
    },
    "VERIFICATION_ISSUE": {
        "label": "Verification Problem",
        "assignTo": "VERIFICATION_TEAM",
        "priority": "MEDIUM",
        "sla_hours": 24,
        "description": "Issues with background verification checks"
    },
    "HR_QUERY": {
        "label": "HR Question",
        "assignTo": "HR_TEAM",
        "priority": "LOW",
        "sla_hours": 48,
        "description": "General HR questions, policy clarifications"
    },
    "BILLING": {
        "label": "Billing/Payment",
        "assignTo": "FINANCE_TEAM",
        "priority": "HIGH",
        "sla_hours": 12,
        "description": "Payment issues, invoice queries"
    },
    "FEATURE_REQUEST": {
        "label": "Feature Request",
        "assignTo": "PRODUCT_TEAM",
        "priority": "LOW",
        "sla_hours": 168,  # 1 week
        "description": "New feature suggestions"
    },
    "BUG_REPORT": {
        "label": "Bug Report",
        "assignTo": "DEV_TEAM",
        "priority": "HIGH",
        "sla_hours": 8,
        "description": "Software bugs and errors"
    },
    "ACCOUNT_ISSUE": {
        "label": "Account Issue",
        "assignTo": "SUPPORT_TEAM",
        "priority": "MEDIUM",
        "sla_hours": 12,
        "description": "Account access, permissions, profile issues"
    },
    "OTHER": {
        "label": "Other",
        "assignTo": "SUPPORT_TEAM",
        "priority": "MEDIUM",
        "sla_hours": 24,
        "description": "General queries"
    }
}

# ------------------------------
# Team Email Addresses (configure these)
# ------------------------------
# GLOBAL BGV SUPPORT TEAMS (fallback for all orgs)
GLOBAL_TEAM_EMAILS = {
    "IT_TEAM": ["hemanthyegireddyad@gmail.com", "hemanthdevapple@gmail.com"],
    "VERIFICATION_TEAM": ["verification@bgvapp.in"],
    "HR_TEAM": ["hr@bgvapp.in"],
    "FINANCE_TEAM": ["finance@bgvapp.in", "billing@bgvapp.in"],
    "PRODUCT_TEAM": ["product@bgvapp.in"],
    "DEV_TEAM": ["dev@bgvapp.in", "bugs@bgvapp.in"],
    "SUPPORT_TEAM": ["support@bgvapp.in"],
    "ESCALATION": ["escalation@bgvapp.in", "admin@bgvapp.in"]
}

# DEPRECATED: Use get_team_emails() instead
TEAM_EMAILS = GLOBAL_TEAM_EMAILS

# ------------------------------
# Smart Assignment Logic
# ------------------------------
async def get_assignee(user, usersCol, category="OTHER", priority="MEDIUM"):
    """
    Smart ticket assignment based on category and role hierarchy.
    
    Args:
        user: The user creating the ticket
        usersCol: MongoDB users collection
        category: Ticket category (IT_ISSUE, VERIFICATION_ISSUE, etc.)
        priority: Ticket priority (LOW, MEDIUM, HIGH, CRITICAL)
    
    Returns:
        Assigned user object or None
    """
    
    role = user.get("role")
    userEmail = user.get("email", "").lower().strip()
    userOrgId = user.get("organizationId")
    
    # ---------------------------------------------------------
    # CATEGORY-BASED ROUTING
    # ---------------------------------------------------------
    categoryInfo = TICKET_CATEGORIES.get(category, TICKET_CATEGORIES["OTHER"])
    targetTeam = categoryInfo["assignTo"]
    
    # ---------------------------------------------------------
    # NEW WORKFLOW: ALL TICKETS → SUPER_ADMIN/SUPER_SPOC FIRST
    # ---------------------------------------------------------
    # ORG_HR/HELPER creates ticket → Always assign to SUPER_ADMIN/SUPER_SPOC
    # They will then reassign to appropriate team members
    
    # Find SUPER_ADMIN or SUPER_SPOC
    superUsers = await usersCol.find({
        "role": {"$in": ["SUPER_ADMIN", "SUPER_SPOC"]},
        "isActive": True
    }).to_list(length=None)
    
    if superUsers:
        # Prefer SUPER_SPOC over SUPER_ADMIN if available
        superSpoc = [u for u in superUsers if u.get("role") == "SUPER_SPOC"]
        if superSpoc:
            return superSpoc[0]  # Assign to SUPER_SPOC
        else:
            return superUsers[0]  # Fallback to SUPER_ADMIN
    
    # ❌ No SUPER_ADMIN or SUPER_SPOC available
    return None
    
    # Note: All categories now go to SUPER_ADMIN/SUPER_SPOC first
    # No direct assignment to specialized teams
    
    # ---------------------------------------------------------
    # HIERARCHICAL ASSIGNMENT (for non-IT issues)
    # ---------------------------------------------------------
    
    # 1. HELPER → Assign to ORG_HR in same org
    if role == "HELPER":
        orgHr = await usersCol.find_one({
            "organizationId": userOrgId,
            "role": "ORG_HR",
            "isActive": True
        })
        if orgHr:
            return orgHr
    
    # 2. ORG_HR → Assign to SPOC in same org
    if role == "ORG_HR":
        spoc = await usersCol.find_one({
            "organizationId": userOrgId,
            "role": "SPOC",
            "isActive": True
        })
        if spoc:
            return spoc
    
    # 3. SPOC → Assign to SUPER_ADMIN
    if role == "SPOC":
        superAdmin = await usersCol.find_one({
            "role": "SUPER_ADMIN",
            "isActive": True
        })
        if superAdmin:
            return superAdmin
    
    # 4. SUPER_ADMIN → Assign to SUPER_SPOC
    if role == "SUPER_ADMIN":
        superSpoc = await usersCol.find_one({
            "role": "SUPER_SPOC",
            "isActive": True
        })
        if superSpoc:
            return superSpoc
    
    # 5. SUPER_SPOC → Assign to self (final authority)
    if role in ["SUPER_SPOC", "SUPER_ADMIN"]:
        return user
    
    # ---------------------------------------------------------
    # FALLBACK: Assign to any available SUPER_ADMIN
    # ---------------------------------------------------------
    globalAdmins = await usersCol.find({
        "role": {"$in": ["SUPER_ADMIN", "SUPER_SPOC"]},
        "isActive": True
    }).to_list(length=None)
    
    if globalAdmins:
        return random.choice(globalAdmins)
    
    # Last resort: assign to creator
    return user


# ------------------------------
# Calculate SLA Deadline
# ------------------------------
def calculate_sla_deadline(category, priority):
    """Calculate SLA deadline based on category and priority"""
    
    categoryInfo = TICKET_CATEGORIES.get(category, TICKET_CATEGORIES["OTHER"])
    base_hours = categoryInfo["sla_hours"]
    
    # Adjust based on priority
    priority_multipliers = {
        "CRITICAL": 0.5,  # Half the time
        "HIGH": 0.75,
        "MEDIUM": 1.0,
        "LOW": 1.5
    }
    
    multiplier = priority_multipliers.get(priority, 1.0)
    final_hours = base_hours * multiplier
    
    deadline = datetime.now(timezone.utc) + timedelta(hours=final_hours)
    return deadline.isoformat()


# ------------------------------
# Get Team Emails (Dynamic - checks org first, then global)
# ------------------------------
async def get_team_emails(category, organizationId, orgsCol):
    """
    Get team emails for a category.
    Priority:
    1. Organization-specific team (if configured in org doc)
    2. Global BGV team (fallback)
    
    Args:
        category: Ticket category (IT_ISSUE, etc.)
        organizationId: Organization ID
        orgsCol: MongoDB organizations collection
    
    Returns:
        List of email addresses
    """
    
    team = TICKET_CATEGORIES.get(category, {}).get("assignTo", "SUPPORT_TEAM")
    
    # Try to get org-specific team emails
    if organizationId:
        try:
            org = await orgsCol.find_one({"_id": ObjectId(organizationId)})
            if org and "supportTeams" in org:
                org_team_emails = org.get("supportTeams", {}).get(team, [])
                if org_team_emails:
                    return org_team_emails
        except Exception as e:
            print(f"Error fetching org team emails: {e}")
    
    # Fallback to global team
    return GLOBAL_TEAM_EMAILS.get(team, GLOBAL_TEAM_EMAILS["SUPPORT_TEAM"])


# ------------------------------
# Send Team Notification
# ------------------------------
async def notify_team(category, ticket_data, orgsCol):
    """Send email notification to relevant team"""
    
    team_emails = await get_team_emails(
        category, 
        ticket_data.get('organizationId'), 
        orgsCol
    )
    
    subject = f"[{ticket_data['priority']}] New Ticket: {ticket_data['subject']}"
    
    body = f"""
New Support Ticket Created

Ticket ID: {ticket_data['ticketId']}
Category: {ticket_data['category']}
Priority: {ticket_data['priority']}
Created By: {ticket_data['createdBy']} ({ticket_data['createdByRole']})
Organization: {ticket_data.get('organizationName', 'N/A')}

Subject: {ticket_data['subject']}

Description:
{ticket_data['description']}

SLA Deadline: {ticket_data['slaDeadline']}

Assigned To: {ticket_data.get('assignedToEmail', 'Unassigned')}

---
Please respond within the SLA timeframe.
"""
    
    # Send to all team members
    for email in team_emails:
        try:
            send_ticket_email(email, subject, body)
        except Exception as e:
            print(f"Failed to send notification to {email}: {e}")


# ------------------------------
# Utility Functions
# ------------------------------
def now():
    return datetime.now(timezone.utc).isoformat()


def generate_ticket_id():
    """Generate unique ticket ID"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_suffix = random.randint(1000, 9999)
    return f"TKT-{timestamp}-{random_suffix}"
