# Enhanced Resume Screening with Weighted Scoring
import os
import io
import numpy as np
from typing import List, Dict, Tuple, Optional
from datetime import datetime
import json
import re

# Import base utilities
from utils.resume_screening import (
    extract_text_from_file,
    get_embedding,
    cosine_similarity,
    openai_client
)
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
from utils.resume_screening import generate_ranking_explanation


def generate_enhanced_ranking_explanation(
    rank: int, 
    embedding_score: float, 
    llm_score: int, 
    final_score: float,
    meets_critical_requirements: bool,
    recommendation: str, 
    top_strengths: List[str], 
    total_candidates: int,
    must_have_requirements: List[str]
) -> str:
    """
    Generate talent-focused enhanced explanation for why a candidate got their specific rank
    
    Args:
        rank: Candidate's rank (1, 2, 3, etc.)
        embedding_score: Embedding similarity score (0-1)
        llm_score: LLM match score (0-100)
        final_score: Final weighted score
        meets_critical_requirements: Whether candidate meets all critical requirements
        recommendation: AI recommendation
        top_strengths: Top 2 strengths from AI analysis
        total_candidates: Total number of candidates screened
        must_have_requirements: List of critical requirements
    
    Returns:
        Human-readable, talent-focused explanation of the ranking
    """
    
    # Rank position description
    if rank == 1:
        position_desc = "selected as the top candidate"
        reason_prefix = "This candidate excels with their"
    elif rank == 2:
        position_desc = "ranked as the second-best candidate"
        reason_prefix = "This candidate stands out due to their"
    elif rank == 3:
        position_desc = "ranked as the third-best candidate"
        reason_prefix = "This candidate earned this position through their"
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
        
        # Add critical requirements context
        if meets_critical_requirements:
            explanation += f" They fulfill all {len(must_have_requirements)} critical job requirements."
        else:
            missing_count = len(must_have_requirements) - sum(1 for req in must_have_requirements if any(strength.lower() in req.lower() or req.lower() in strength.lower() for strength in top_strengths))
            if missing_count > 0:
                explanation += f" However, they may need development in {missing_count} critical requirement(s)."
        
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
        if meets_critical_requirements:
            explanation = f"{position_desc.capitalize()} out of {total_candidates} candidates. They meet all critical job requirements and demonstrate strong overall qualifications."
        else:
            explanation = f"{position_desc.capitalize()} out of {total_candidates} candidates based on their relevant experience, though they may need development in some critical areas."
    
    return explanation


async def analyze_resume_with_requirements(
    resume_text: str,
    jd_text: str,
    similarity_score: float,
    must_have_requirements: Optional[List[str]] = None,
    nice_to_have: Optional[List[str]] = None
) -> Dict:
    """
    Enhanced resume analysis with explicit requirement checking
    
    Args:
        resume_text: Resume content
        jd_text: Job description content
        similarity_score: Embedding similarity score
        must_have_requirements: List of critical requirements
        nice_to_have: List of preferred but not critical requirements
    
    Returns:
        Enhanced analysis with requirement compliance
    """
    if not openai_client:
        raise Exception("OpenAI client not configured")
    
    # Build requirements section
    requirements_section = ""
    if must_have_requirements:
        requirements_section += "\nCRITICAL REQUIREMENTS (MUST HAVE):\n"
        for req in must_have_requirements:
            requirements_section += f"- {req}\n"
    
    if nice_to_have:
        requirements_section += "\nPREFERRED REQUIREMENTS (NICE TO HAVE):\n"
        for req in nice_to_have:
            requirements_section += f"- {req}\n"
    
    # Get current date for context
    from datetime import datetime
    current_year = datetime.now().year
    current_date = datetime.now().strftime("%B %d, %Y")  # e.g., "December 21, 2024"
    
    prompt = f"""You are an expert HR recruiter. Analyze this resume against the job description with REALISTIC requirement checking.

🗓️ CURRENT DATE CONTEXT: Today is {current_date}. Be realistic about career timelines:
- ALL dates in {current_year} (January {current_year} through December {current_year}) are VALID and CURRENT
- February {current_year}, March {current_year}, etc. are all PAST/CURRENT dates - NOT future
- Only flag dates in {current_year + 1} or later as potentially problematic
- Graduating {current_year} + starting work {current_year} = NORMAL (campus placement)
- Academic years ({current_year-1}-{current_year}) + {current_year} job start = NORMAL progression
- Part-time work during studies = COMMON and acceptable
- Short gaps (1-6 months) between jobs = NORMAL transition time
- Career changes and industry switches = NORMAL career evolution

JOB DESCRIPTION:
{jd_text[:3000]}

{requirements_section}

RESUME:
{resume_text[:4000]}

EMBEDDING SIMILARITY SCORE: {similarity_score:.2%}

CRITICAL REQUIREMENT CHECKING GUIDELINES:
- Only mark requirements as "not_met" if there's CLEAR evidence they're missing
- Consider related skills and transferable experience
- Don't penalize for normal career transitions or timeline patterns
- If any critical requirement is genuinely missing, match_score should be below 60

Provide a JSON response with:
1. "meets_critical_requirements": true/false (ALL must-haves satisfied?)
2. "critical_requirements_status": {{
   "requirement": "met/not_met/unclear",
   ...
}}
3. "match_score": Overall match score 0-100 (only penalize for genuine skill gaps, not timeline issues)
4. "strengths": List of 3-5 key strengths
5. "weaknesses": List of 3-5 genuine gaps or concerns (NOT timeline issues)
6. "skills_match": {{
   "matched": [list of matched skills],
   "missing_critical": [list of genuinely missing critical skills],
   "missing_nice_to_have": [list of missing nice-to-have skills]
}}
7. "experience_match": {{
   "years": number of years experience,
   "relevance": "high/medium/low",
   "assessment": "brief realistic assessment"
}}
8. "education_match": Brief realistic assessment
9. "contact_information": {{
   "firstName": "Candidate's first name from resume",
   "lastName": "Candidate's last name from resume",
   "phone_numbers": [list of phone numbers - ONLY DIGITS, remove +91 or any country codes],
   "email_addresses": [list of email addresses found],
   "contact_completeness": "COMPLETE" | "PARTIAL" | "MISSING"
}}
10. "red_flags": List of GENUINE concerns only (not normal career patterns)
11. "recommendation": "STRONG_FIT" | "GOOD_FIT" | "MODERATE_FIT" | "WEAK_FIT" | "REJECT"
12. "summary": 2-3 sentence realistic overall assessment

Return ONLY valid JSON, no markdown."""

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",  # ✅ UPGRADED: Latest GPT-4o for enhanced analysis
            messages=[
                {"role": "system", "content": "You are an expert HR recruiter providing structured resume analysis with strict requirement checking. Always respond with valid JSON only. Be realistic about career timelines - same year graduation and job start is normal. Focus on genuine issues, not normal career transitions."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.15,  # ✅ REDUCED: Even lower temperature for consistent evaluation
            max_tokens=1500,   # ✅ INCREASED: More tokens for detailed analysis
            top_p=0.9,        # ✅ ADDED: Better quality responses
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
        
        # Add embedding score to analysis
        analysis["embedding_similarity"] = similarity_score
        
        return analysis
        
    except json.JSONDecodeError as e:
        print(f"⚠️ JSON decode error: {e}")
        # Add contact detection even in fallback
        contact_info = extract_contact_info(resume_text)
        
        # Return fallback analysis
        return {
            "meets_critical_requirements": False,
            "critical_requirements_status": {},
            "match_score": int(similarity_score * 100),
            "strengths": ["Resume content extracted successfully"],
            "weaknesses": ["Detailed analysis unavailable"],
            "skills_match": {"matched": [], "missing_critical": [], "missing_nice_to_have": []},
            "experience_match": {"years": 0, "relevance": "unclear", "assessment": "Unable to analyze"},
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
            "red_flags": ["AI analysis failed - manual review required"],
            "recommendation": "MODERATE_FIT" if similarity_score > 0.7 else "WEAK_FIT",
            "summary": f"Embedding similarity: {similarity_score:.2%}. Manual review required.",
            "embedding_similarity": similarity_score
        }
    except Exception as e:
        print(f"❌ AI analysis error: {e}")
        raise


def calculate_weighted_score(
    embedding_score: float,
    llm_match_score: int,
    meets_critical_requirements: bool,
    embedding_weight: float = 0.3,
    llm_weight: float = 0.7
) -> float:
    """
    Calculate weighted final score combining embedding and LLM scores
    
    Args:
        embedding_score: Similarity score from embeddings (0-1)
        llm_match_score: Match score from LLM (0-100)
        meets_critical_requirements: Whether critical requirements are met
        embedding_weight: Weight for embedding score (default 0.3)
        llm_weight: Weight for LLM score (default 0.7)
    
    Returns:
        Weighted score (0-100)
    """
    # If critical requirements not met, cap score at 50
    if not meets_critical_requirements:
        return min(50, (embedding_score * 100 * embedding_weight) + (llm_match_score * llm_weight))
    
    # Normal weighted calculation
    weighted_score = (embedding_score * 100 * embedding_weight) + (llm_match_score * llm_weight)
    return round(weighted_score, 2)


async def screen_resumes_enhanced(
    resume_files: List[Tuple[bytes, str]],
    jd_file: Tuple[bytes, str],
    top_n: int = 5,
    must_have_requirements: Optional[List[str]] = None,
    nice_to_have: Optional[List[str]] = None,
    min_embedding_score: float = 0.5,
    embedding_weight: float = 0.3,
    llm_weight: float = 0.7
) -> Dict:
    """
    Enhanced resume screening with requirement checking and weighted scoring
    
    Args:
        resume_files: List of tuples (file_content_bytes, filename)
        jd_file: Tuple of (jd_content_bytes, jd_filename)
        top_n: Number of top resumes to return
        must_have_requirements: List of critical requirements
        nice_to_have: List of preferred requirements
        min_embedding_score: Minimum embedding score to consider (default 0.5)
        embedding_weight: Weight for embedding score (default 0.3)
        llm_weight: Weight for LLM score (default 0.7)
    
    Returns:
        Dictionary with top resumes and enhanced analysis
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
            
            # Filter out low-scoring resumes early
            if similarity < min_embedding_score:
                print(f"⚠️ Skipping {resume_filename}: Below minimum threshold ({similarity:.4f} < {min_embedding_score})")
                continue
            
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
        raise ValueError("No resumes met the minimum criteria")
    
    # Sort by similarity score (descending)
    resume_results.sort(key=lambda x: x["similarity_score"], reverse=True)
    
    # Get top N*2 for LLM analysis (analyze more, then re-rank)
    candidates_for_analysis = min(top_n * 2, len(resume_results))
    top_candidates = resume_results[:candidates_for_analysis]
    
    print(f"\n🎯 Analyzing top {len(top_candidates)} resumes with enhanced AI...")
    
    # Analyze candidates with enhanced LLM
    analyzed_results = []
    for idx, resume in enumerate(top_candidates, 1):
        print(f"\n🤖 Enhanced AI Analysis {idx}/{len(top_candidates)}: {resume['filename']}")
        
        try:
            analysis = await analyze_resume_with_requirements(
                resume["text"],
                jd_text,
                resume["similarity_score"],
                must_have_requirements,
                nice_to_have
            )
            
            # Calculate weighted final score
            final_score = calculate_weighted_score(
                resume["similarity_score"],
                analysis.get("match_score", 0),
                analysis.get("meets_critical_requirements", False),
                embedding_weight,
                llm_weight
            )
            
            analyzed_results.append({
                "filename": resume["filename"],
                "embedding_similarity": round(resume["similarity_score"], 4),
                "llm_match_score": analysis.get("match_score", 0),
                "final_weighted_score": final_score,
                "meets_critical_requirements": analysis.get("meets_critical_requirements", False),
                "critical_requirements_status": analysis.get("critical_requirements_status", {}),
                "recommendation": analysis.get("recommendation", "MODERATE_FIT"),
                "summary": analysis.get("summary", ""),
                "strengths": analysis.get("strengths", []),
                "weaknesses": analysis.get("weaknesses", []),
                "skills_match": analysis.get("skills_match", {}),
                "experience_match": analysis.get("experience_match", {}),
                "education_match": analysis.get("education_match", ""),
                "contact_information": analysis.get("contact_information", {}),
                "red_flags": analysis.get("red_flags", [])
            })
            
            print(f"✅ Analysis complete: {analysis.get('recommendation', 'N/A')} (Final Score: {final_score})")
            
        except Exception as e:
            print(f"⚠️ AI analysis failed for {resume['filename']}: {e}")
            continue
    
    # Re-rank by final weighted score
    analyzed_results.sort(key=lambda x: x["final_weighted_score"], reverse=True)
    
    # Return top N after re-ranking
    final_top_n = analyzed_results[:top_n]
    
    # Add ranks and ranking explanations
    for idx, result in enumerate(final_top_n, 1):
        result["rank"] = idx
        
        # Generate enhanced ranking explanation
        print(f"🔍 Generating ranking explanation for rank {idx}: {result['filename']}")
        ranking_explanation = generate_enhanced_ranking_explanation(
            idx,
            result["embedding_similarity"],
            result["llm_match_score"],
            result["final_weighted_score"],
            result["meets_critical_requirements"],
            result["recommendation"],
            result["strengths"][:2],  # Top 2 strengths
            len(final_top_n),
            must_have_requirements or []
        )
        result["ranking_explanation"] = ranking_explanation
        print(f"✅ Ranking explanation added: {ranking_explanation[:100]}...")
    
    return {
        "total_resumes_processed": len(resume_results),
        "total_resumes_uploaded": len(resume_files),
        "resumes_analyzed_with_llm": len(analyzed_results),
        "top_n_requested": top_n,
        "jd_filename": jd_filename,
        "must_have_requirements": must_have_requirements or [],
        "nice_to_have": nice_to_have or [],
        "scoring_weights": {
            "embedding_weight": embedding_weight,
            "llm_weight": llm_weight
        },
        "top_resumes": final_top_n,
        "processed_at": datetime.utcnow().isoformat()
    }
