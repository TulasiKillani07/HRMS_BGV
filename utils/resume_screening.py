# Resume Screening with OpenAI Embeddings
import os
import io
import numpy as np
from typing import List, Dict, Tuple
from datetime import datetime
import json

# Import text extraction utilities
from utils.ai_utils import extract_text_from_pdf, extract_text_from_docx, extract_text_from_txt

# Temporary fallback for extract_contact_info if not available
try:
    from utils.ai_utils import extract_contact_info, normalize_phone_number
except ImportError:
    def normalize_phone_number(phone: str) -> str:
        """Normalize phone number by removing country codes"""
        import re
        digits_only = re.sub(r'\D', '', phone)
        if len(digits_only) >= 10:
            return digits_only[-10:]
        return digits_only
    
    def extract_contact_info(text: str) -> dict:
        """Fallback contact info extraction"""
        import re
        
        # Phone number patterns
        phone_patterns = [
            r'\+91[-\s]?[6-9]\d{9}',
            r'\b[6-9]\d{9}\b',
            r'\(\+91\)[-\s]?[6-9]\d{9}',
            r'\b0[1-9]\d{8,10}\b',
            r'\+\d{1,3}[-\s]?\d{6,14}',
        ]
        
        # Email patterns
        email_patterns = [
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        ]
        
        # Name extraction (simple version)
        firstName = None
        lastName = None
        lines = text.strip().split('\n')
        for line in lines[:5]:
            line = line.strip()
            if not line or len(line) < 3 or '@' in line or re.search(r'\d{6,}', line):
                continue
            name_pattern = r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}$'
            if re.match(name_pattern, line):
                name_parts = line.split()
                if len(name_parts) >= 2:
                    firstName = name_parts[0]
                    lastName = " ".join(name_parts[1:])
                elif len(name_parts) == 1:
                    firstName = name_parts[0]
                break
        
        phone_numbers = []
        email_addresses = []
        
        for pattern in phone_patterns:
            matches = re.findall(pattern, text)
            phone_numbers.extend(matches)
        
        for pattern in email_patterns:
            matches = re.findall(pattern, text)
            email_addresses.extend(matches)
        
        # Normalize phones
        normalized_phones = [normalize_phone_number(phone) for phone in phone_numbers]
        phone_numbers = list(set([phone for phone in normalized_phones if phone]))
        email_addresses = list(set([email.strip().lower() for email in email_addresses]))
        
        return {
            "firstName": firstName,
            "lastName": lastName,
            "phone_numbers": phone_numbers,
            "email_addresses": email_addresses,
            "contact_found": len(phone_numbers) > 0 or len(email_addresses) > 0,
            "total_phones": len(phone_numbers),
            "total_emails": len(email_addresses)
        }

# OpenAI Integration
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("⚠️ OpenAI not installed. Install with: pip install openai")

# Initialize OpenAI client
from dotenv import load_dotenv
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
if OPENAI_API_KEY and OPENAI_AVAILABLE:
    openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
else:
    openai_client = None
    print("⚠️ OpenAI API key not configured for resume screening")


def generate_ranking_explanation(rank: int, similarity_score: float, match_score: int, recommendation: str, top_strengths: List[str], total_candidates: int) -> str:
    """
    Generate talent-focused explanation for why a candidate got their specific rank
    
    Args:
        rank: Candidate's rank (1, 2, 3, etc.)
        similarity_score: Embedding similarity score (0-1)
        match_score: AI match score (0-100)
        recommendation: AI recommendation (STRONG_FIT, GOOD_FIT, etc.)
        top_strengths: Top 2 strengths from AI analysis
        total_candidates: Total number of candidates screened
    
    Returns:
        Human-readable, talent-focused explanation of the ranking
    """
    
    # Rank position description
    if rank == 1:
        position_desc = "selected as the top candidate"
        reason_prefix = "This candidate stands out because of their"
    elif rank == 2:
        position_desc = "ranked as the second-best candidate"
        reason_prefix = "This candidate earned this position due to their"
    elif rank == 3:
        position_desc = "ranked as the third-best candidate"
        reason_prefix = "This candidate secured this rank through their"
    else:
        position_desc = f"ranked #{rank}"
        reason_prefix = "This candidate is positioned here because of their"
    
    # Build talent-focused explanation
    if top_strengths and len(top_strengths) > 0:
        # Clean up strengths text
        strengths_list = [strength.strip().rstrip('.') for strength in top_strengths[:2]]
        
        if len(strengths_list) == 1:
            strengths_text = strengths_list[0].lower()
        else:
            strengths_text = f"{strengths_list[0].lower()} and {strengths_list[1].lower()}"
        
        # Create talent-focused explanation
        explanation = f"{position_desc.capitalize()} out of {total_candidates} candidates. {reason_prefix} {strengths_text}."
        
        # Add recommendation context
        if recommendation == "STRONG_FIT":
            explanation += " They are an excellent match for this role."
        elif recommendation == "GOOD_FIT":
            explanation += " They show strong potential for this position."
        elif recommendation == "MODERATE_FIT":
            explanation += " They have relevant skills that align with the job requirements."
        else:
            explanation += " They possess qualifications worth considering for this role."
            
    else:
        # Fallback when no strengths available
        explanation = f"{position_desc.capitalize()} out of {total_candidates} candidates based on their overall qualifications and experience that align with the job requirements."
    
    return explanation


def extract_text_from_file(file_content: bytes, filename: str) -> str:
    """
    Extract text from uploaded file based on extension
    
    Args:
        file_content: File bytes
        filename: Original filename with extension
    
    Returns:
        Extracted text content
    """
    file_obj = io.BytesIO(file_content)
    filename_lower = filename.lower()
    
    if filename_lower.endswith('.pdf'):
        return extract_text_from_pdf(file_obj)
    elif filename_lower.endswith('.docx') or filename_lower.endswith('.doc'):
        return extract_text_from_docx(file_obj)
    elif filename_lower.endswith('.txt'):
        return extract_text_from_txt(file_obj)
    else:
        raise ValueError(f"Unsupported file format: {filename}")


def get_embedding(text: str) -> List[float]:
    """
    Generate embedding for text using OpenAI text-embedding-3-small
    
    Args:
        text: Text to embed
    
    Returns:
        Embedding vector (1536 dimensions)
    """
    if not openai_client:
        raise Exception("OpenAI client not configured")
    
    # Truncate text if too long (max 8191 tokens for text-embedding-3-small)
    if len(text) > 30000:  # Rough estimate: 4 chars per token
        text = text[:30000]
    
    response = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    
    return response.data[0].embedding


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Calculate cosine similarity between two vectors"""
    vec1_np = np.array(vec1)
    vec2_np = np.array(vec2)
    
    dot_product = np.dot(vec1_np, vec2_np)
    norm1 = np.linalg.norm(vec1_np)
    norm2 = np.linalg.norm(vec2_np)
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    return float(dot_product / (norm1 * norm2))


async def analyze_resume_with_ai(resume_text: str, jd_text: str, similarity_score: float) -> Dict:
    """
    Use OpenAI to analyze resume against JD and provide detailed insights
    
    Args:
        resume_text: Resume content
        jd_text: Job description content
        similarity_score: Embedding similarity score
    
    Returns:
        Analysis with strengths, weaknesses, skills match, etc.
    """
    if not openai_client:
        raise Exception("OpenAI client not configured")
    
    # Get current date for context
    from datetime import datetime
    current_year = datetime.now().year
    current_date = datetime.now().strftime("%B %d, %Y")
    
    prompt = f"""You are an expert HR recruiter. Analyze this resume against the job description and provide a detailed assessment.

🗓️ CURRENT DATE: Today is {current_date}. 
- ALL dates in {current_year} (January {current_year} through December {current_year}) are VALID and CURRENT
- February {current_year}, March {current_year}, etc. are all PAST/CURRENT dates - NOT future
- Only flag dates in {current_year + 1} or later as potentially problematic
- Recent experience in {current_year} is valid regardless of month

JOB DESCRIPTION:
{jd_text[:3000]}

RESUME:
{resume_text[:4000]}

EMBEDDING SIMILARITY SCORE: {similarity_score:.2%}

Provide a JSON response with:
1. "match_score": Overall match score 0-100
2. "strengths": List of 3-5 key strengths/positive points
3. "weaknesses": List of 3-5 gaps or concerns
4. "skills_match": {{
   "matched": [list of matched skills],
   "missing": [list of missing critical skills]
}}
5. "experience_match": Brief assessment of experience relevance
6. "education_match": Brief assessment of education fit
7. "contact_information": {{
   "firstName": "Candidate's first name from resume",
   "lastName": "Candidate's last name from resume",
   "phone_numbers": [list of phone numbers - ONLY DIGITS, remove +91 or any country codes],
   "email_addresses": [list of email addresses found],
   "contact_completeness": "COMPLETE" | "PARTIAL" | "MISSING"
}}
8. "recommendation": "STRONG_FIT" | "GOOD_FIT" | "MODERATE_FIT" | "WEAK_FIT"
9. "summary": 2-3 sentence overall assessment

Return ONLY valid JSON, no markdown or extra text."""

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",  # ✅ UPGRADED: Latest GPT-4o for better analysis
            messages=[
                {"role": "system", "content": "You are an expert HR recruiter providing structured resume analysis. Always respond with valid JSON only. Be realistic about career timelines and avoid flagging normal career transitions as issues."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,  # ✅ REDUCED: Lower temperature for more consistent analysis
            max_tokens=1200,  # ✅ INCREASED: More tokens for detailed analysis
            top_p=0.9,       # ✅ ADDED: Better quality responses
            frequency_penalty=0.1,  # ✅ ADDED: Reduce repetition
            presence_penalty=0.1    # ✅ ADDED: Encourage diverse responses
        )
        
        analysis_text = response.choices[0].message.content.strip()
        
        # Remove markdown code blocks if present
        if analysis_text.startswith("```json"):
            analysis_text = analysis_text[7:]
        if analysis_text.startswith("```"):
            analysis_text = analysis_text[3:]
        if analysis_text.endswith("```"):
            analysis_text = analysis_text[:-3]
        
        analysis = json.loads(analysis_text.strip())
        
        # Add contact information detection using regex
        contact_info = extract_contact_info(resume_text)
        
        # Merge AI-detected contact info with regex-detected info
        ai_contact = analysis.get("contact_information", {})
        ai_first_name = ai_contact.get("firstName")
        ai_last_name = ai_contact.get("lastName")
        ai_phones = ai_contact.get("phone_numbers", [])
        ai_emails = ai_contact.get("email_addresses", [])
        
        # Import normalize function
        from utils.ai_utils import normalize_phone_number
        
        # Normalize all phone numbers (remove country codes)
        normalized_ai_phones = [normalize_phone_number(phone) for phone in ai_phones if phone]
        normalized_regex_phones = contact_info["phone_numbers"]  # Already normalized
        
        # Combine and deduplicate (now they'll match after normalization)
        all_phones = list(set(normalized_ai_phones + normalized_regex_phones))
        all_emails = list(set(ai_emails + contact_info["email_addresses"]))
        
        # Use AI name if available, otherwise use regex name
        final_first_name = ai_first_name if ai_first_name else contact_info.get("firstName")
        final_last_name = ai_last_name if ai_last_name else contact_info.get("lastName")
        
        # Update analysis with comprehensive contact info
        analysis["contact_information"] = {
            "firstName": final_first_name,
            "lastName": final_last_name,
            "phone_numbers": all_phones,
            "email_addresses": all_emails,
            "contact_completeness": "COMPLETE" if (len(all_phones) > 0 and len(all_emails) > 0) else "PARTIAL" if (len(all_phones) > 0 or len(all_emails) > 0) else "MISSING",
            "total_phones": len(all_phones),
            "total_emails": len(all_emails),
            "regex_detected": contact_info
        }
        
        return analysis
        
    except json.JSONDecodeError as e:
        print(f"⚠️ JSON decode error: {e}")
        # Return fallback analysis
        # Add contact detection even in fallback
        contact_info = extract_contact_info(resume_text)
        
        return {
            "match_score": int(similarity_score * 100),
            "strengths": ["Resume content extracted successfully"],
            "weaknesses": ["Detailed analysis unavailable"],
            "skills_match": {"matched": [], "missing": []},
            "experience_match": "Unable to analyze",
            "education_match": "Unable to analyze",
            "contact_information": {
                "firstName": contact_info.get("firstName"),
                "lastName": contact_info.get("lastName"),
                "phone_numbers": contact_info["phone_numbers"],
                "email_addresses": contact_info["email_addresses"],
                "contact_completeness": "COMPLETE" if (len(contact_info["phone_numbers"]) > 0 and len(contact_info["email_addresses"]) > 0) else "PARTIAL" if (len(contact_info["phone_numbers"]) > 0 or len(contact_info["email_addresses"]) > 0) else "MISSING",
                "total_phones": len(contact_info["phone_numbers"]),
                "total_emails": len(contact_info["email_addresses"]),
                "regex_detected": contact_info
            },
            "recommendation": "MODERATE_FIT" if similarity_score > 0.7 else "WEAK_FIT",
            "summary": f"Embedding similarity: {similarity_score:.2%}. Manual review recommended."
        }
    except Exception as e:
        print(f"❌ AI analysis error: {e}")
        raise


async def screen_resumes(
    resume_files: List[Tuple[bytes, str]],  # List of (file_content, filename)
    jd_file: Tuple[bytes, str],  # (jd_content, jd_filename)
    top_n: int = 5
) -> Dict:
    """
    Screen multiple resumes against a job description using embeddings
    
    Args:
        resume_files: List of tuples (file_content_bytes, filename)
        jd_file: Tuple of (jd_content_bytes, jd_filename)
        top_n: Number of top resumes to return
    
    Returns:
        Dictionary with top resumes and their analysis
    """
    if not openai_client:
        raise Exception("OpenAI client not configured. Please set OPENAI_API_KEY in .env")
    
    # Extract JD text
    jd_content, jd_filename = jd_file
    print(f"📄 Extracting JD from: {jd_filename}")
    jd_text = extract_text_from_file(jd_content, jd_filename)
    
    if not jd_text or len(jd_text.strip()) < 50:
        raise ValueError("Job description is too short or extraction failed")
    
    print(f"✅ JD extracted: {len(jd_text)} characters")
    
    # Generate JD embedding
    print("🔄 Generating JD embedding...")
    jd_embedding = get_embedding(jd_text)
    print(f"✅ JD embedding generated: {len(jd_embedding)} dimensions")
    
    # Process all resumes
    resume_results = []
    
    for idx, (resume_content, resume_filename) in enumerate(resume_files, 1):
        try:
            print(f"\n📄 Processing resume {idx}/{len(resume_files)}: {resume_filename}")
            
            # Extract text
            resume_text = extract_text_from_file(resume_content, resume_filename)
            
            if not resume_text or len(resume_text.strip()) < 50:
                print(f"⚠️ Skipping {resume_filename}: Text too short")
                continue
            
            print(f"✅ Text extracted: {len(resume_text)} characters")
            
            # Generate embedding
            resume_embedding = get_embedding(resume_text)
            print(f"✅ Embedding generated")
            
            # Calculate similarity
            similarity = cosine_similarity(jd_embedding, resume_embedding)
            print(f"📊 Similarity score: {similarity:.4f}")
            
            resume_results.append({
                "filename": resume_filename,
                "text": resume_text,
                "embedding": resume_embedding,
                "similarity_score": similarity
            })
            
        except Exception as e:
            print(f"❌ Error processing {resume_filename}: {e}")
            continue
    
    if not resume_results:
        raise ValueError("No resumes could be processed successfully")
    
    # Sort by similarity score (descending)
    resume_results.sort(key=lambda x: x["similarity_score"], reverse=True)
    
    # Get top N resumes
    top_resumes = resume_results[:top_n]
    
    print(f"\n🎯 Analyzing top {len(top_resumes)} resumes with AI...")
    
    # Analyze top resumes with AI
    final_results = []
    for idx, resume in enumerate(top_resumes, 1):
        print(f"\n🤖 AI Analysis {idx}/{len(top_resumes)}: {resume['filename']}")
        
        try:
            analysis = await analyze_resume_with_ai(
                resume["text"],
                jd_text,
                resume["similarity_score"]
            )
            
            # Generate ranking explanation
            ranking_explanation = generate_ranking_explanation(
                idx, 
                resume["similarity_score"], 
                analysis.get("match_score", 0),
                analysis.get("recommendation", "MODERATE_FIT"),
                analysis.get("strengths", [])[:2],  # Top 2 strengths
                len(top_resumes)
            )
            
            final_results.append({
                "rank": idx,
                "filename": resume["filename"],
                "similarity_score": round(resume["similarity_score"], 4),
                "match_score": analysis.get("match_score", 0),
                "recommendation": analysis.get("recommendation", "MODERATE_FIT"),
                "ranking_explanation": ranking_explanation,
                "summary": analysis.get("summary", ""),
                "strengths": analysis.get("strengths", []),
                "weaknesses": analysis.get("weaknesses", []),
                "skills_match": analysis.get("skills_match", {"matched": [], "missing": []}),
                "experience_match": analysis.get("experience_match", ""),
                "education_match": analysis.get("education_match", ""),
                "contact_information": analysis.get("contact_information", {})
            })
            
            print(f"✅ Analysis complete: {analysis.get('recommendation', 'N/A')}")
            
        except Exception as e:
            print(f"⚠️ AI analysis failed for {resume['filename']}: {e}")
            # Generate ranking explanation for fallback
            ranking_explanation = generate_ranking_explanation(
                idx, 
                resume["similarity_score"], 
                int(resume["similarity_score"] * 100),
                "MODERATE_FIT",
                ["Resume processed successfully"],
                len(top_resumes)
            )
            
            # Add basic result without AI analysis
            final_results.append({
                "rank": idx,
                "filename": resume["filename"],
                "similarity_score": round(resume["similarity_score"], 4),
                "match_score": int(resume["similarity_score"] * 100),
                "recommendation": "MODERATE_FIT",
                "ranking_explanation": ranking_explanation,
                "summary": f"Embedding similarity: {resume['similarity_score']:.2%}",
                "strengths": ["Resume processed successfully"],
                "weaknesses": ["Detailed AI analysis unavailable"],
                "skills_match": {"matched": [], "missing": []},
                "experience_match": "Manual review required",
                "education_match": "Manual review required",
                "contact_information": {"phone_numbers": [], "email_addresses": [], "contact_completeness": "MISSING"}
            })
    
    return {
        "total_resumes_processed": len(resume_results),
        "total_resumes_uploaded": len(resume_files),
        "top_n_requested": top_n,
        "top_resumes": final_results,
        "jd_filename": jd_filename,
        "processed_at": datetime.utcnow().isoformat()
    }
