# AI Utilities - CV Authenticity Validation with OpenAI
import PyPDF2
import docx
import uuid
from datetime import datetime
import re
import json
import os
from typing import Dict, List, Optional

# ------------------------------------------------
# CONTACT INFORMATION DETECTION
# ------------------------------------------------

def normalize_phone_number(phone: str) -> str:
    """
    Normalize phone number by removing country codes and special characters
    Returns only digits (last 10 digits for Indian numbers)
    
    Examples:
    - "+91-9876543210" → "9876543210"
    - "9876543210" → "9876543210"
    - "+91 9876543210" → "9876543210"
    - "(+91) 9876543210" → "9876543210"
    """
    # Remove all non-digit characters
    digits_only = re.sub(r'\D', '', phone)
    
    # For Indian numbers, keep last 10 digits (removes country code if present)
    if len(digits_only) >= 10:
        return digits_only[-10:]
    
    # For shorter numbers (landlines, etc.), return as is
    return digits_only


def extract_name_from_text(text: str) -> Dict[str, Optional[str]]:
    """
    Extract candidate name from resume text using regex patterns
    Typically the name appears at the top of the resume
    
    Returns:
    - Dictionary with firstName and lastName, or None values if not found
    - Example: {"firstName": "John", "lastName": "Doe"}
    """
    # Split text into lines
    lines = text.strip().split('\n')
    
    # Name is usually in first 5 lines
    for line in lines[:5]:
        line = line.strip()
        
        # Skip empty lines
        if not line or len(line) < 3:
            continue
        
        # Skip lines with email or phone (these are not names)
        if '@' in line or re.search(r'\d{6,}', line):
            continue
        
        # Skip common resume headers
        skip_keywords = ['resume', 'curriculum vitae', 'cv', 'profile', 'contact', 'email', 'phone', 'address']
        if any(keyword in line.lower() for keyword in skip_keywords):
            continue
        
        # Name pattern: 2-4 words, each starting with capital letter, only letters and spaces
        name_pattern = r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}$'
        if re.match(name_pattern, line):
            # Split full name into firstName and lastName
            name_parts = line.split()
            if len(name_parts) >= 2:
                return {
                    "firstName": name_parts[0],
                    "lastName": " ".join(name_parts[1:])  # Everything after first word is lastName
                }
            elif len(name_parts) == 1:
                return {
                    "firstName": name_parts[0],
                    "lastName": None
                }
    
    return {"firstName": None, "lastName": None}


def extract_contact_info(text: str) -> Dict:
    """
    Extract name, phone numbers and email addresses from text
    
    Returns:
    {
        "firstName": "John",
        "lastName": "Doe",
        "phone_numbers": ["9876543210"],  # Normalized (no country codes)
        "email_addresses": ["john@example.com", "john.doe@company.co.in"],
        "contact_found": True/False
    }
    """
    
    # Phone number patterns (Indian and international)
    phone_patterns = [
        r'\+91[-\s]?[6-9]\d{9}',  # +91-9876543210 or +91 9876543210
        r'\b[6-9]\d{9}\b',        # 9876543210 (10 digit Indian mobile)
        r'\(\+91\)[-\s]?[6-9]\d{9}',  # (+91) 9876543210
        r'\b0[1-9]\d{8,10}\b',    # Landline numbers
        r'\+\d{1,3}[-\s]?\d{6,14}',  # International format
    ]
    
    # Email patterns
    email_patterns = [
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    ]
    
    # Extract name (returns dict with firstName and lastName)
    name_dict = extract_name_from_text(text)
    
    phone_numbers = []
    email_addresses = []
    
    # Extract phone numbers
    for pattern in phone_patterns:
        matches = re.findall(pattern, text)
        phone_numbers.extend(matches)
    
    # Normalize phone numbers (remove country codes, keep only digits)
    normalized_phones = [normalize_phone_number(phone) for phone in phone_numbers]
    
    # Remove duplicates after normalization
    unique_phones = list(set([phone for phone in normalized_phones if phone]))
    
    # Extract email addresses
    for pattern in email_patterns:
        matches = re.findall(pattern, text)
        email_addresses.extend(matches)
    
    # Remove duplicates and clean emails
    unique_emails = list(set([email.strip().lower() for email in email_addresses]))
    
    return {
        "firstName": name_dict.get("firstName"),
        "lastName": name_dict.get("lastName"),
        "phone_numbers": unique_phones,
        "email_addresses": unique_emails,
        "contact_found": len(unique_phones) > 0 or len(unique_emails) > 0,
        "total_phones": len(unique_phones),
        "total_emails": len(unique_emails)
    }

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# OpenAI Integration
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("⚠️ OpenAI not installed. Install with: pip install openai")

# Initialize OpenAI client
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
if OPENAI_API_KEY and OPENAI_AVAILABLE:
    openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
else:
    openai_client = None
    print("⚠️ OpenAI API key not configured")

# ------------------------------------------------
# TEXT EXTRACTION UTILITIES
# ------------------------------------------------

def extract_text_from_pdf(file_obj):
    """Extract text from PDF file"""
    try:
        reader = PyPDF2.PdfReader(file_obj)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        print(f"❌ PDF extraction error: {e}")
        return ""

def extract_text_from_docx(file_obj):
    """Extract text from DOCX file"""
    try:
        doc = docx.Document(file_obj)
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        return text.strip()
    except Exception as e:
        print(f"❌ DOCX extraction error: {e}")
        return ""

def extract_text_from_txt(file_obj):
    """Extract text from TXT file"""
    try:
        content = file_obj.read()
        if isinstance(content, bytes):
            content = content.decode('utf-8')
        return content.strip()
    except Exception as e:
        print(f"❌ TXT extraction error: {e}")
        return ""

# ------------------------------------------------
# AI CV AUTHENTICITY VALIDATION (NO JD REQUIRED)
# ------------------------------------------------

async def validate_cv_authenticity(cv_text: str, has_uan: bool = False, candidate_type: str = "UNKNOWN", uan_note: str = "") -> Dict:
    """
    Validate CV authenticity - check for abnormalities, education overlaps, inconsistencies
    NO JD comparison - pure authenticity check
    
    Parameters:
    - cv_text: Extracted text from CV
    - has_uan: Boolean - whether candidate has verified UAN (formal employment)
    - candidate_type: "FRESHER", "EXPERIENCED_WITH_UAN", "EXPERIENCED_NO_UAN", "UNKNOWN"
    - uan_note: Note about UAN verification status
    
    Returns:
    - Positive findings (strengths, valid points)
    - Negative findings (red flags, inconsistencies, overlaps)
    - Authenticity score (0-100)
    """
    if not openai_client:
        raise Exception("OpenAI client not configured")
    
    try:
        # Build context with UAN verification status
        context_info = f"Candidate Type: {candidate_type}\n"
        context_info += f"UAN Verification: {uan_note}\n\n"
        
        if has_uan:
            context_info += "✅ IMPORTANT: Candidate has verified UAN number (Universal Account Number from EPFO).\n"
            context_info += "This means they have formal employment history with provident fund contributions.\n"
            context_info += "This significantly increases credibility and authenticity of employment claims.\n\n"
        else:
            context_info += "⚠️ NOTE: Candidate has NO UAN number.\n"
            context_info += "This could mean: fresher, freelancer, worked in unorganized sector, or foreign employment.\n"
            context_info += "Employment claims cannot be verified through official EPFO records.\n\n"
        
        # Get current date for context
        from datetime import datetime
        current_year = datetime.now().year
        current_month = datetime.now().month
        current_date = datetime.now().strftime("%B %d, %Y")  # e.g., "December 21, 2024"
        
        # Build the full prompt
        system_prompt = f"""You are an expert Background Verification analyst specializing in CV authenticity checks.
Your job is to identify GENUINE red flags while being EXTREMELY REALISTIC about normal career patterns.

🗓️ CURRENT DATE CONTEXT: Today is {current_date}. You are analyzing this CV on this date.
- ALL dates in {current_year} (January {current_year} through December {current_year}) are VALID and CURRENT
- February {current_year}, March {current_year}, etc. are all PAST/CURRENT dates - NOT future
- Only flag dates in {current_year + 1} or later as potentially problematic
- Treat ALL {current_year} dates as valid, regardless of month

GENUINE RED FLAGS to identify (BE VERY STRICT - only flag if CLEARLY impossible):
1. **Impossible simultaneous activities**: Full-time study + full-time work in different cities at EXACT same time
2. **Clear timeline impossibilities**: Starting work BEFORE graduation at the same company (not internship conversion)
3. **Major unexplained gaps**: >18 months with NO education, work, or explanation
4. **Obviously fabricated information**: Fake company names, impossible achievements, clear inconsistencies
5. **Future dates**: Any experience or education ending AFTER {current_year} (i.e., {current_year + 1} or later)
6. **Clearly exaggerated claims**: Unrealistic salary jumps, impossible responsibilities for age/experience

NORMAL PATTERNS (DO NOT FLAG - these are COMMON and ACCEPTABLE):
1. **Same year transitions**: Graduating {current_year} + starting work {current_year} = NORMAL campus placement
2. **Academic year overlaps**: "{current_year-1}-{current_year}" education + "{current_year}" job start = NORMAL
3. **Part-time work during studies**: Students working while studying = VERY COMMON
4. **Internship conversions**: Summer internship becoming full-time role = NORMAL
5. **Short gaps**: 1-6 months between jobs/education = NORMAL transition time
6. **Career changes**: Switching industries, roles, or career paths = NORMAL
7. **Month overlaps**: Starting new job while serving notice period = NORMAL
8. **Vague dates**: "{current_year}" education + "{current_year}" work without specific months = NORMAL
9. **Academic calendar differences**: Academic years don't align with calendar years = NORMAL

TIMELINE ANALYSIS RULES:
- If only YEARS are provided (no months), assume NO overlap unless clearly impossible
- "{current_year} graduation" + "{current_year} job start" = ASSUME different months, NOT an overlap
- Academic years ({current_year-1}-{current_year}) ending + {current_year} job start = NORMAL progression
- Only flag overlaps if SPECIFIC dates show impossible simultaneous full-time commitments

Be LENIENT and REALISTIC. Focus only on CLEAR impossibilities, not normal career patterns."""

        user_prompt = f"""{context_info}

🚨 CRITICAL DATE INSTRUCTION: Today is {current_date}. 
ALL dates in {current_year} are VALID and CURRENT - including February {current_year}, March {current_year}, etc.
DO NOT flag ANY month in {current_year} as "future dates" - they are all PAST or CURRENT.

CANDIDATE CV/RESUME:
{cv_text}

Analyze this CV for AUTHENTICITY ONLY (not job matching). Be REALISTIC and focus on GENUINE issues:

LOOK FOR GENUINE RED FLAGS:
1. **Impossible overlaps**: Full-time education + full-time work in different locations simultaneously
2. **Timeline impossibilities**: Starting work before graduation at same company, impossible date sequences
3. **Major unexplained gaps**: >18 months without education/work explanation
4. **Fabricated information**: Clearly fake companies, impossible achievements, inconsistent details

DO NOT FLAG AS ISSUES:
0. **ANY DATES IN {current_year}**: January {current_year}, February {current_year}, March {current_year}, April {current_year}, May {current_year}, June {current_year}, July {current_year}, August {current_year}, September {current_year}, October {current_year}, November {current_year}, December {current_year} - ALL VALID, NOT future dates
1. **Same year transitions**: Graduating {current_year} + starting work {current_year} (normal campus placement)
2. **Part-time work during studies**: Students working while studying (very common)
3. **Short overlaps**: 1-2 month overlaps during job transitions (normal notice periods)
4. **Career changes**: Switching industries or roles (normal career evolution)
5. **Internship to full-time**: Converting internships to permanent roles
6. **Vague dates**: "{current_year-1}-{current_year}" education + "{current_year}" job start is NORMAL, not an overlap

**CONTACT INFORMATION EXTRACTION**:
- Extract ALL phone numbers (mobile, landline, international formats)
- Extract ALL email addresses found in the CV
- Assess contact information completeness (phone + email = complete)

**UAN Verification Context**:
   - If UAN verified: Employment claims have official backing, higher credibility
   - If NO UAN: Employment claims unverified but not necessarily false

**NEGATIVE FINDINGS GUIDELINES**:
- Only list GENUINE problems with CLEAR evidence
- DO NOT flag normal career transitions as problems
- DO NOT list opposites of positive points
- Focus on factual inconsistencies with specific examples
- Avoid generic statements unless backed by clear evidence
- If dates are vague (only years), DO NOT assume overlaps

**TIMELINE ANALYSIS - BE EXTREMELY LENIENT**:
- Only flag CLEAR impossibilities with specific evidence
- "{current_year} graduation + {current_year} job start" = NORMAL, not an overlap
- Academic years ({current_year-1}-{current_year}) + {current_year} work = NORMAL progression
- Assume different months unless proven otherwise
- Focus on OBVIOUS impossibilities, not theoretical overlaps

Provide balanced analysis with realistic authenticity score. Err on the side of being LENIENT rather than strict."""

        # Print the prompts for debugging
        print("\n" + "="*80)
        print("🤖 SENDING TO OPENAI GPT-4o (Latest Model)")
        print("="*80)
        print("\n📋 SYSTEM PROMPT:")
        print("-"*80)
        print(system_prompt)
        print("\n📋 USER PROMPT:")
        print("-"*80)
        print(user_prompt)
        print("\n" + "="*80)
        
        response = openai_client.chat.completions.create(
            model="gpt-4o",  # ✅ UPGRADED: Latest GPT-4o (most intelligent model)
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ],
            functions=[{
                "name": "validate_cv_authenticity",
                "description": "Validate CV authenticity and identify red flags",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "authenticity_score": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 100,
                            "description": "Overall authenticity score (0-100)"
                        },
                        "candidate_profile": {
                            "type": "object",
                            "properties": {
                                "total_experience_years": {"type": "number"},
                                "education_level": {"type": "string"},
                                "career_progression": {"type": "string", "enum": ["CONSISTENT", "INCONSISTENT", "UNCLEAR"]},
                                "timeline_clarity": {"type": "string", "enum": ["CLEAR", "VAGUE", "MISSING"]}
                            }
                        },
                        "positive_findings": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Strengths and valid points found in CV"
                        },
                        "negative_findings": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "ONLY genuine red flags and factual inconsistencies. Do NOT list opposites of positive findings. Focus on actual problems like impossible timelines, fake companies, or major gaps >12 months."
                        },
                        "education_analysis": {
                            "type": "object",
                            "properties": {
                                "education_entries": {"type": "array", "items": {"type": "string"}},
                                "overlaps_detected": {"type": "boolean", "description": "Only flag TRUE for IMPOSSIBLE overlaps (full-time study + full-time work in different cities with SPECIFIC conflicting dates). Same year graduation + job start is NORMAL. Academic years (2023-2024) + 2024 work is NORMAL."},
                                "overlap_details": {"type": "array", "items": {"type": "string"}, "description": "Only list GENUINE impossible overlaps with specific conflicting dates, not normal career transitions or same-year progressions"},
                                "education_score": {"type": "number", "minimum": 0, "maximum": 100}
                            }
                        },
                        "employment_analysis": {
                            "type": "object",
                            "properties": {
                                "employment_entries": {"type": "array", "items": {"type": "string"}},
                                "gaps_detected": {"type": "boolean", "description": "Only flag TRUE for gaps >18 months without ANY explanation (education, work, travel, etc.). Short gaps (1-6 months) are normal job transitions."},
                                "gap_details": {"type": "array", "items": {"type": "string"}, "description": "Only list significant unexplained gaps >18 months with specific date ranges, not normal transition periods"},
                                "uan_verification_status": {"type": "string", "enum": ["MATCHED", "MISMATCHED", "NOT_AVAILABLE"]},
                                "uan_discrepancies": {"type": "array", "items": {"type": "string"}},
                                "employment_score": {"type": "number", "minimum": 0, "maximum": 100}
                            }
                        },
                        "timeline_analysis": {
                            "type": "object",
                            "properties": {
                                "timeline_consistent": {"type": "boolean", "description": "Only mark FALSE for CLEAR impossibilities with specific evidence, not normal career transitions or same-year progressions"},
                                "timeline_issues": {"type": "array", "items": {"type": "string"}, "description": "Only list GENUINE timeline problems with specific conflicting dates, not normal same-year transitions or academic-to-work progressions"},
                                "timeline_score": {"type": "number", "minimum": 0, "maximum": 100}
                            }
                        },
                        "contact_information": {
                            "type": "object",
                            "properties": {
                                "phone_numbers": {"type": "array", "items": {"type": "string"}, "description": "Phone numbers found in CV"},
                                "email_addresses": {"type": "array", "items": {"type": "string"}, "description": "Email addresses found in CV"},
                                "contact_completeness": {"type": "string", "enum": ["COMPLETE", "PARTIAL", "MISSING"], "description": "Whether contact info is complete"},
                                "contact_score": {"type": "number", "minimum": 0, "maximum": 100, "description": "Contact information completeness score"}
                            }
                        },
                        "red_flags": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "severity": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
                                    "category": {"type": "string"},
                                    "description": {"type": "string"}
                                }
                            }
                        },
                        "recommendation": {
                            "type": "string",
                            "enum": ["APPROVE", "REVIEW_REQUIRED", "REJECT"],
                            "description": "Final recommendation based on authenticity"
                        },
                        "summary": {"type": "string", "description": "Brief summary of findings"}
                    },
                    "required": ["authenticity_score", "positive_findings", "negative_findings", "contact_information", "recommendation"]
                }
            }],
            function_call={"name": "validate_cv_authenticity"},
            temperature=0.1,  # ✅ REDUCED: Lower temperature for more consistent, less hallucinatory responses
            max_tokens=2000,  # ✅ INCREASED: More tokens for detailed analysis
            top_p=0.9,       # ✅ ADDED: Nucleus sampling for better quality
            frequency_penalty=0.1,  # ✅ ADDED: Reduce repetition
            presence_penalty=0.1    # ✅ ADDED: Encourage diverse responses
        )
        
        function_call = response.choices[0].message.function_call
        if function_call:
            result = json.loads(function_call.arguments)
            
            # Print the response for debugging
            print("\n" + "="*80)
            print("✅ RECEIVED FROM OPENAI")
            print("="*80)
            print(json.dumps(result, indent=2))
            print("="*80 + "\n")
            
            # Add contact information detection using regex
            print(f"🔍 Starting contact detection on CV text (length: {len(cv_text)} chars)")
            contact_info = extract_contact_info(cv_text)
            print(f"🔍 Regex detected: {contact_info}")
            
            # Merge AI-detected contact info with regex-detected info
            ai_contact = result.get("contact_information", {})
            ai_phones = ai_contact.get("phone_numbers", [])
            ai_emails = ai_contact.get("email_addresses", [])
            print(f"🤖 AI detected: phones={ai_phones}, emails={ai_emails}")
            
            # Combine and deduplicate
            all_phones = list(set(ai_phones + contact_info["phone_numbers"]))
            all_emails = list(set(ai_emails + contact_info["email_addresses"]))
            
            # Update result with comprehensive contact info
            result["contact_information"] = {
                "phone_numbers": all_phones,
                "email_addresses": all_emails,
                "contact_completeness": "COMPLETE" if (len(all_phones) > 0 and len(all_emails) > 0) else "PARTIAL" if (len(all_phones) > 0 or len(all_emails) > 0) else "MISSING",
                "contact_score": min(100, (len(all_phones) * 40) + (len(all_emails) * 60)),  # Email weighted higher
                "total_phones": len(all_phones),
                "total_emails": len(all_emails),
                "regex_detected": contact_info
            }
            
            print(f"📞 Final Contact Detection: {len(all_phones)} phones, {len(all_emails)} emails")
            print(f"📞 Contact Info Added to Result: {result.get('contact_information', 'MISSING!')}")
            
            return result
        else:
            raise Exception("No authenticity analysis generated")
            
    except Exception as e:
        print(f"❌ CV authenticity validation error: {e}")
        raise Exception(f"Failed to validate CV authenticity: {str(e)}")

# ----
# --------------------------------------------
# OCR TEXT EXTRACTION (for education documents)
# ------------------------------------------------

def extract_text_with_ocr(file_path: str) -> str:
    """
    Extract text from image or PDF using OCR (Tesseract)
    Works with: JPG, PNG, PDF
    
    Args:
        file_path: Path to image or PDF file
    
    Returns:
        Extracted text
    """
    try:
        import pytesseract
        from PIL import Image
        
        ext = file_path.split(".")[-1].lower()
        
        if ext == "pdf":
            # Try PDF text extraction first (faster, no OCR needed)
            try:
                print(f"📄 Attempting direct PDF text extraction...")
                with open(file_path, 'rb') as f:
                    text = extract_text_from_pdf(f)
                    if text and len(text.strip()) > 50:  # If we got meaningful text
                        print(f"✅ Extracted text directly from PDF (no OCR needed)")
                        return text
            except Exception as pdf_err:
                print(f"⚠️ Direct PDF extraction failed: {pdf_err}")
            
            # Fallback to OCR if direct extraction failed or returned little text
            try:
                from pdf2image import convert_from_path
                print(f"📄 Converting PDF to images for OCR...")
                images = convert_from_path(file_path)
                text = ""
                for i, image in enumerate(images):
                    print(f"🔍 OCR processing page {i+1}/{len(images)}")
                    page_text = pytesseract.image_to_string(image)
                    text += page_text + "\n\n"
                return text.strip()
            except ImportError:
                raise Exception("pdf2image not installed. Install with: pip install pdf2image")
            except Exception as ocr_err:
                if "poppler" in str(ocr_err).lower():
                    raise Exception(
                        "Poppler not installed. Install with: brew install poppler (macOS) or apt-get install poppler-utils (Linux). "
                        "Alternatively, upload a text-based PDF or image file instead."
                    )
                raise Exception(f"PDF OCR failed: {str(ocr_err)}")
        
        elif ext in ["jpg", "jpeg", "png", "tiff", "bmp"]:
            # Direct OCR on image
            print(f"🔍 OCR processing image...")
            image = Image.open(file_path)
            text = pytesseract.image_to_string(image)
            return text.strip()
        
        else:
            raise Exception(f"Unsupported file type for OCR: {ext}. Supported: PDF, JPG, PNG, TIFF, BMP")
            
    except Exception as e:
        print(f"❌ OCR extraction error: {e}")
        raise Exception(f"Failed to extract text with OCR: {str(e)}")


# ------------------------------------------------
# AI EDUCATION VALIDATION
# ------------------------------------------------

async def validate_education_document(document_text: str) -> Dict:
    """
    Validate education document using OpenAI GPT-4o-mini
    Extracts structured education information
    
    Args:
        document_text: Extracted text from education certificate/marksheet
    
    Returns:
        Structured education data with validation
    """
    if not openai_client:
        raise Exception("OpenAI client not configured")
    
    # Get current date for context
    from datetime import datetime
    current_year = datetime.now().year
    current_date = datetime.now().strftime("%B %d, %Y")
    
    try:
        print(f"🎓 Starting AI education document validation...")
        print(f"🔍 DEBUG: Model=gpt-4o, Updated={current_date}, Version=LENIENT")
        print(f"🔍 DEBUG: Document text length: {len(document_text)} chars")
        print(f"🔍 DEBUG: First 200 chars: {document_text[:200]}...")
        
        response = openai_client.chat.completions.create(
            model="gpt-4o",  # ✅ UPGRADED: Latest GPT-4o for education validation
            messages=[
                {
                    "role": "system",
                    "content": f"""You are an expert education document validator.
Extract structured information from education certificates, marksheets, and degree documents.

🗓️ CURRENT DATE: Today is {current_date}. ALL dates in {current_year} are VALID and CURRENT.

IMPORTANT: Be realistic about timeline analysis. Consider these NORMAL patterns:
- Graduating in {current_year} and starting work in {current_year} is NORMAL (campus placements)
- Academic years often overlap with calendar years (e.g., {current_year-1}-{current_year} academic year)
- Part-time work during studies is common and acceptable
- Short gaps between education completion and job start are normal

Validate:
1. Degree/qualification type
2. Field of study/specialization
3. Institution name
4. Duration (start and end dates)
5. Grades/marks/CGPA
6. Authenticity indicators
7. Red flags (tampering, inconsistencies) - BUT BE REALISTIC"""
                },
                {
                    "role": "user",
                    "content": f"""Analyze this education document and extract structured information:

DOCUMENT TEXT:
{document_text}

Extract all education details and validate authenticity."""
                }
            ],
            functions=[{
                "name": "validate_education",
                "description": "Extract and validate education document information",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "degree_type": {
                            "type": "string",
                            "description": "Type of degree (e.g., Bachelor of Technology, Master of Science, High School)"
                        },
                        "field_of_study": {
                            "type": "string",
                            "description": "Major/specialization (e.g., Computer Science, Mechanical Engineering)"
                        },
                        "institution_name": {
                            "type": "string",
                            "description": "Name of university/college/school"
                        },
                        "start_date": {
                            "type": "string",
                            "description": "Start year or date (e.g., 2014, Aug 2014)"
                        },
                        "end_date": {
                            "type": "string",
                            "description": "End year or date (e.g., 2018, May 2018)"
                        },
                        "duration_years": {
                            "type": "number",
                            "description": "Duration in years"
                        },
                        "grade": {
                            "type": "string",
                            "description": "Grade/marks/CGPA (e.g., First Class, 8.5 CGPA, 85%)"
                        },
                        "board_university": {
                            "type": "string",
                            "description": "Affiliated board/university"
                        },
                        "document_type": {
                            "type": "string",
                            "enum": ["DEGREE_CERTIFICATE", "MARKSHEET", "PROVISIONAL_CERTIFICATE", "TRANSCRIPT", "OTHER"],
                            "description": "Type of document"
                        },
                        "authenticity_score": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 100,
                            "description": "Authenticity score (0-100)"
                        },
                        "verification_status": {
                            "type": "string",
                            "enum": ["VERIFIED", "SUSPICIOUS", "INCOMPLETE", "UNCLEAR"],
                            "description": "Overall verification status"
                        },
                        "positive_findings": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Valid/authentic elements found"
                        },
                        "red_flags": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "severity": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
                                    "issue": {"type": "string"},
                                    "description": {"type": "string"}
                                }
                            },
                            "description": "Issues or suspicious elements"
                        },
                        "extracted_text_quality": {
                            "type": "string",
                            "enum": ["EXCELLENT", "GOOD", "FAIR", "POOR"],
                            "description": "Quality of OCR text extraction"
                        },
                        "recommendation": {
                            "type": "string",
                            "enum": ["APPROVE", "REVIEW_REQUIRED", "REJECT"],
                            "description": "Final recommendation"
                        },
                        "summary": {
                            "type": "string",
                            "description": "Brief summary of findings"
                        }
                    },
                    "required": ["degree_type", "institution_name", "authenticity_score", "verification_status", "recommendation"]
                }
            }],
            function_call={"name": "validate_education"},
            temperature=0.1,  # ✅ REDUCED: Lower temperature for consistency
            max_tokens=1500,  # ✅ INCREASED: More tokens for detailed analysis
            top_p=0.9,       # ✅ ADDED: Better quality responses
            frequency_penalty=0.1,  # ✅ ADDED: Reduce repetition
            presence_penalty=0.1    # ✅ ADDED: Encourage diverse responses
        )
        
        function_call = response.choices[0].message.function_call
        if function_call:
            result = json.loads(function_call.arguments)
            
            print(f"✅ Education validation completed")
            print(f"📊 Score: {result.get('authenticity_score', 0)}/100")
            print(f"🎓 Degree: {result.get('degree_type', 'N/A')}")
            print(f"🏫 Institution: {result.get('institution_name', 'N/A')}")
            
            return result
        else:
            raise Exception("No education validation generated")
            
    except Exception as e:
        print(f"❌ Education validation error: {e}")
        raise Exception(f"Failed to validate education document: {str(e)}")
