
import base64
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

FRONTEND_SELF_VERIFY_URL = "https://tfgverify.com/candidate/self-verification"

# Email configuration
GMAIL_USER = os.getenv("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")

def send_email_smtp(to_email, subject, body):
    """
    Send email using Gmail SMTP with App Password (RECOMMENDED for production)
    
    Setup:
    1. Go to Google Account → Security
    2. Enable 2-Step Verification
    3. Generate App Password
    4. Add to .env: GMAIL_USER and GMAIL_APP_PASSWORD
    """
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        raise Exception("Gmail credentials not configured. Set GMAIL_USER and GMAIL_APP_PASSWORD in environment variables.")
    
    msg = MIMEMultipart()
    msg['From'] = GMAIL_USER
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        # Use SMTP_SSL for port 465 (more reliable)
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.send_message(msg)
        print(f"✅ Email sent successfully to {to_email}")
        return True
    except Exception as e:
        print(f"❌ SMTP Error: {e}")
        raise Exception(f"Failed to send email: {str(e)}")


def send_self_verification_email(to_email, candidateName, organizationName,
                                 stage, token, expiresAt):
    """Send self-verification email using SMTP"""
    
    # Build verification link
    link = f"{FRONTEND_SELF_VERIFY_URL}?token={token}"

    body = f"""
Hi {candidateName},

You have been requested to complete the {stage.upper()} stage verification 
for {organizationName}.

Stage: {stage}
Verification Link: {link}
This link will expire at: {expiresAt}

If you did not request this, please contact your HR/Verification team.

Thanks,
{organizationName} Verification Team
"""

    try:
        send_email_smtp(
            to_email=to_email,
            subject=f"{stage.capitalize()} Stage Verification - {organizationName}",
            body=body
        )
        print("Email sent successfully to:", to_email)
    except Exception as e:
        print("Error sending email:", str(e))
        raise Exception(f"Email sending failed: {str(e)}")


def send_password_reset_email(toEmail, userName, userId, newPassword):
    """
    Sends an email notification to the user after password reset.
    Includes username and new password.
    """

    body = f"""
Hi {userName},

Your password has been successfully reset.

Here are your updated login credentials:

User ID (Email): {toEmail}
User Unique ID: {userId}
New Password: {newPassword}

For security reasons, please do not share this password with anyone.

If you did not request this reset, please contact the support team immediately.

Thanks,
Maihoo Verification Team
"""

    try:
        send_email_smtp(
            to_email=toEmail,
            subject="Password Reset Confirmation - Maihoo",
            body=body
        )
        print("Password reset email sent to:", toEmail)
    except Exception as e:
        print("Error sending password reset email:", str(e))
        raise Exception(f"Email sending failed: {str(e)}")

def send_organization_welcome_email(
    toEmail,
    organizationName,
    spocName,
    loginEmail,
    defaultPassword,
    mainDomain,
    subDomain,
    services,
    credentials,
    logoUrl=None
):
    """
    Sends a welcome email when a new organization is registered.
    Includes login details for the SPOC.
    """

    # Convert services list to readable text (e.g., "- Employment Verification: 120.0")
    servicesText = ""
    if services:
        for s in services:
            servicesText += f"- {s.get('serviceName')}: {s.get('price')}\n"
    else:
        servicesText = "No services added yet.\n"

    credentialsText = f"""
Total Allowed Users: {credentials.get('totalAllowed')}
Users Used: {credentials.get('used')}
""".strip()

    body = f"""
Hello {spocName},

Welcome to the BGVApp Platform!

Your organization **{organizationName}** has been successfully registered.

-------------------------
LOGIN CREDENTIALS
-------------------------
Login Email: {loginEmail}
Default Password: {defaultPassword}

Please log in and change your password immediately.

-------------------------
ORGANIZATION DETAILS
-------------------------
Organization Name: {organizationName}
Main Domain: {mainDomain or 'Not Provided'}
Subdomain: {subDomain}

-------------------------
PLAN/USAGE CREDENTIALS
-------------------------
{credentialsText}

-------------------------
SERVICES ENABLED
-------------------------
{servicesText}

-------------------------
LOGO
-------------------------
{logoUrl or 'No logo provided'}

If you have any questions or need help setting up your workspace,
please reach out to your support team.

Thanks,
BGVApp Team
"""

    try:
        send_email_smtp(
            to_email=toEmail,
            subject=f"Welcome to BGVApp - {organizationName} Registration Successful",
            body=body
        )
        print(f"✅ Welcome email sent to {toEmail}")
    except Exception as e:
        print("Error sending organization welcome email:", str(e))
        raise Exception(f"Email sending failed: {str(e)}")
    

def send_ticket_email(toEmail, subject, body):
    """
    Sends ticket-related emails using SMTP
    """
    try:
        send_email_smtp(
            to_email=toEmail,
            subject=subject,
            body=body
        )
        print(f"✅ Ticket email sent to {toEmail}")
    except Exception as e:
        print("Email sending failed:", str(e))
        raise Exception(f"Email sending failed: {str(e)}")


def send_verification_consent_email(to_email, candidate_name, organization_name, 
                                  verification_checks, consent_token, expires_at, 
                                  consent_url=None):
    """
    Sends consent email to candidate before starting backend verification using SMTP.
    
    Args:
        to_email: Candidate's email
        candidate_name: Candidate's name
        organization_name: Organization requesting verification
        verification_checks: List of checks to be performed
        consent_token: Unique token for consent validation
        expires_at: Token expiration time
        consent_url: Frontend consent page URL (optional)
    """
    
    # Default consent URL if not provided
    if not consent_url:
        consent_url = "https://tfgverify.com/candidate/consent"
    
    # Build consent link with token
    consent_link = f"{consent_url}?token={consent_token}"
    
    # Format verification checks list
    checks_list = ""
    for i, check in enumerate(verification_checks, 1):
        checks_list += f"{i}. {check.get('name', 'Unknown Check')}\n"
        if check.get('description'):
            checks_list += f"   - {check['description']}\n"
    
    body = f"""
Dear {candidate_name},

{organization_name} has requested to perform background verification checks on your profile.

Before we begin the verification process, we need your explicit consent to proceed with the following checks:

VERIFICATION CHECKS TO BE PERFORMED:
{checks_list}

IMPORTANT INFORMATION:
- These checks will be conducted by our verification team
- Your personal information will be handled securely and confidentially
- You have the right to know what checks are being performed
- This consent is required before any verification can begin

WHAT YOU NEED TO DO:
1. Click the consent link below
2. Review the detailed list of verification checks
3. Provide your consent by checking the agreement box
4. Submit your response

CONSENT LINK: {consent_link}

This consent link will expire on: {expires_at}

If you have any questions about these verification checks or need clarification, please contact:
- Organization: {organization_name}
- Support: support@bgvapp.in

If you did not expect this verification request, please contact us immediately.

Thank you for your cooperation.

Best regards,
BGVApp Verification Team
"""

    try:
        send_email_smtp(
            to_email=to_email,
            subject=f"Verification Consent Required - {organization_name}",
            body=body
        )
        print(f"✅ Verification consent email sent to {to_email}")
    except Exception as e:
        print(f"Error sending verification consent email: {str(e)}")
        raise Exception(f"Email sending failed: {str(e)}")



def send_manual_verification_email(
    to_email: str,
    check_name: str,
    candidate_data: dict,
    check_specific_data: dict,
    organization_name: str
):
    """
    Send email to verification team (SUPER_ADMIN/SUPER_SPOC) for manual verification
    
    Args:
        to_email: Recipient email (SUPER_ADMIN/SUPER_SPOC/SUPER_ADMIN_HELPER)
        check_name: Name of the manual check
        candidate_data: Candidate information
        check_specific_data: Check-specific data (supervisor contact, certificate URL, etc.)
        organization_name: Organization requesting verification
    """
    
    candidate_name = f"{candidate_data.get('firstName', '')} {candidate_data.get('lastName', '')}".strip()
    candidate_email = candidate_data.get('email', 'N/A')
    candidate_phone = candidate_data.get('phone', 'N/A')
    
    # Build check-specific details
    check_details = ""
    
    if check_name == "supervisory_check_1":
        check_details = f"""
Supervisor Details (Reference 1):
- Name: {check_specific_data.get('name', 'N/A')}
- Phone: {check_specific_data.get('phone', 'N/A')}
- Email: {check_specific_data.get('email', 'N/A')}
- Relationship: {check_specific_data.get('relationship', 'N/A')}
- Company: {check_specific_data.get('company', 'N/A')}
- Designation: {check_specific_data.get('designation', 'N/A')}
- Working Period: {check_specific_data.get('workingPeriod', 'N/A')}

Action Required:
Contact the supervisor and verify:
1. Candidate's employment details
2. Job responsibilities and performance
3. Reason for leaving
4. Eligibility for rehire
"""
    
    elif check_name == "supervisory_check_2":
        check_details = f"""
Supervisor Details (Reference 2):
- Name: {check_specific_data.get('name', 'N/A')}
- Phone: {check_specific_data.get('phone', 'N/A')}
- Email: {check_specific_data.get('email', 'N/A')}
- Relationship: {check_specific_data.get('relationship', 'N/A')}
- Company: {check_specific_data.get('company', 'N/A')}
- Designation: {check_specific_data.get('designation', 'N/A')}
- Working Period: {check_specific_data.get('workingPeriod', 'N/A')}

Action Required:
Contact the supervisor and verify:
1. Candidate's employment details
2. Job responsibilities and performance
3. Reason for leaving
4. Eligibility for rehire
"""
    
    elif check_name in ["employment_history_manual", "employment_check_2"]:
        check_details = f"""
Employment Details:
- Company: {check_specific_data.get('company', 'N/A')}
- Designation: {check_specific_data.get('designation', 'N/A')}
- Joining Date: {check_specific_data.get('joiningDate', 'N/A')}
- Relieving Date: {check_specific_data.get('relievingDate', 'N/A')}
- HR Contact: {check_specific_data.get('hrContact', 'N/A')}
- HR Email: {check_specific_data.get('hrEmail', 'N/A')}
- HR Name: {check_specific_data.get('hrName', 'N/A')}
- Address: {check_specific_data.get('address', 'N/A')}

Documents:
- Relieving Letter: {check_specific_data.get('relievingLetterUrl', 'Not provided')}
- Experience Letter: {check_specific_data.get('experienceLetterUrl', 'Not provided')}
- Salary Slips: {check_specific_data.get('salarySlipsUrl', 'Not provided')}

Action Required:
1. Download and review the documents
2. Contact HR to verify employment details
3. Verify dates, designation, and reason for leaving
4. Submit verification result
"""
    
    elif check_name == "employment_history_manual_2":
        check_details = f"""
Employment Details (Previous Employment):
- Company: {check_specific_data.get('company', 'N/A')}
- Designation: {check_specific_data.get('designation', 'N/A')}
- Joining Date: {check_specific_data.get('joiningDate', 'N/A')}
- Relieving Date: {check_specific_data.get('relievingDate', 'N/A')}
- HR Contact: {check_specific_data.get('hrContact', 'N/A')}
- HR Email: {check_specific_data.get('hrEmail', 'N/A')}
- HR Name: {check_specific_data.get('hrName', 'N/A')}
- Address: {check_specific_data.get('address', 'N/A')}

Documents:
- Relieving Letter: {check_specific_data.get('relievingLetterUrl', 'Not provided')}
- Experience Letter: {check_specific_data.get('experienceLetterUrl', 'Not provided')}
- Salary Slips: {check_specific_data.get('salarySlipsUrl', 'Not provided')}

Action Required:
1. Download and review the documents
2. Contact HR to verify employment details
3. Verify dates, designation, and reason for leaving
4. Submit verification result
"""
    
    elif check_name == "education_check_manual":
        check_details = f"""
Education Details:
- Degree: {check_specific_data.get('degree', 'N/A')}
- Specialization: {check_specific_data.get('specialization', 'N/A')}
- University: {check_specific_data.get('universityName', 'N/A')}
- College: {check_specific_data.get('collegeName', 'N/A')}
- Year of Passing: {check_specific_data.get('yearOfPassing', 'N/A')}
- CGPA/Percentage: {check_specific_data.get('cgpa', 'N/A')}

University Contact:
- Phone: {check_specific_data.get('universityContact', 'N/A')}
- Email: {check_specific_data.get('universityEmail', 'N/A')}
- Address: {check_specific_data.get('universityAddress', 'N/A')}

College Contact:
- Phone: {check_specific_data.get('collegeContact', 'N/A')}
- Email: {check_specific_data.get('collegeEmail', 'N/A')}
- Address: {check_specific_data.get('collegeAddress', 'N/A')}

Documents:
- Certificate: {check_specific_data.get('certificateUrl', 'Not provided')}
- Marksheet: {check_specific_data.get('marksheetUrl', 'Not provided')}

Action Required:
1. Download and review the certificate/marksheet
2. Contact university/college to verify authenticity
3. Verify degree, year of passing, and grades
4. Submit verification result
"""
    
    else:
        check_details = f"""
Check-specific data:
{check_specific_data}

Action Required:
Please review the provided information and complete the verification.
"""
    
    # Build email body
    body = f"""
Manual Verification Required

Organization: {organization_name}
Check Type: {check_name}

Candidate Information:
- Name: {candidate_name}
- Email: {candidate_email}
- Phone: {candidate_phone}
- PAN: {candidate_data.get('panNumber', 'N/A')}
- Aadhaar: {candidate_data.get('aadhaarNumber', 'N/A')}

{check_details}

Please complete this verification and submit the result through the verification portal.

---
This is an automated email from BGV Verification System.
"""
    
    try:
        print(f"📧 Sending manual verification email for {check_name}")
        print(f"   To: {to_email}")
        print(f"   Candidate: {candidate_name}")
        print(f"   Organization: {organization_name}")
        
        send_email_smtp(
            to_email=to_email,
            subject=f"Manual Verification Required - {check_name} - {candidate_name}",
            body=body
        )
        
        print(f"✅ Manual verification email sent successfully")
        return True
        
    except Exception as e:
        print(f"❌ Failed to send manual verification email: {e}")
        return False
