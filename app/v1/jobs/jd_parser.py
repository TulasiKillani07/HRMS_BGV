"""
AI-powered Job Description Parser
Extracts structured fields from JD text or uploaded files
"""
from typing import Dict, Optional
import json


async def parse_job_description_with_ai(jd_text: str) -> Dict:
    """
    Parse job description text using AI to extract structured fields
    
    Args:
        jd_text: Job description text (from file or pasted)
    
    Returns:
        Dictionary with extracted fields
    """
    # Import OpenAI client
    from utils.resume_screening import openai_client
    
    if not openai_client:
        raise Exception("OpenAI client not configured")
    
    prompt = f"""You are an expert HR assistant. Extract structured information from this job description.

JOB DESCRIPTION:
{jd_text[:5000]}

Extract and return a JSON object with these fields:
1. "title": Job title (e.g., "Senior Python Developer")
2. "department": Department name (e.g., "Engineering", "Sales")
3. "location": Location (e.g., "Remote", "New York, NY", "Bangalore, India")
4. "type": Job type - MUST be one of: "Full-time", "Part-time", "Contract", "Internship"
5. "experience": Experience required (e.g., "3+ years", "5-7 years", "Fresher")
6. "salary": Salary range (e.g., "₹8L - ₹15L", "$80K - $110K", "Competitive")
7. "skills": Array of required skills (e.g., ["Python", "FastAPI", "MongoDB"])
8. "description": Clean, well-formatted job description (preserve key responsibilities, requirements, etc.)
9. "deadline": Application deadline if mentioned (format: "YYYY-MM-DD" or null)

IMPORTANT RULES:
- If a field is not found, use reasonable defaults or null
- For "type", ONLY use: "Full-time", "Part-time", "Contract", or "Internship"
- For "skills", extract 5-10 key technical/professional skills
- For "description", clean up the text but keep all important information
- Return ONLY valid JSON, no markdown

Example output:
{{
  "title": "Senior Backend Developer",
  "department": "Engineering",
  "location": "Bangalore, India (Hybrid)",
  "type": "Full-time",
  "experience": "5+ years",
  "salary": "₹15L - ₹25L per annum",
  "skills": ["Python", "Django", "PostgreSQL", "AWS", "Docker"],
  "description": "We are looking for an experienced Backend Developer...",
  "deadline": null
}}

Return ONLY the JSON object, no other text."""

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an expert HR assistant that extracts structured data from job descriptions. Always respond with valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=2000
        )
        
        result_text = response.choices[0].message.content.strip()
        
        # Remove markdown code blocks if present
        if result_text.startswith("```json"):
            result_text = result_text[7:]
        if result_text.startswith("```"):
            result_text = result_text[3:]
        if result_text.endswith("```"):
            result_text = result_text[:-3]
        
        parsed_data = json.loads(result_text.strip())
        
        # Validate and set defaults
        parsed_data.setdefault("title", "")
        parsed_data.setdefault("department", "")
        parsed_data.setdefault("location", "")
        parsed_data.setdefault("type", "Full-time")
        parsed_data.setdefault("experience", "")
        parsed_data.setdefault("salary", "")
        parsed_data.setdefault("skills", [])
        parsed_data.setdefault("description", jd_text)
        parsed_data.setdefault("deadline", None)
        
        # Ensure skills is an array
        if isinstance(parsed_data["skills"], str):
            parsed_data["skills"] = [s.strip() for s in parsed_data["skills"].split(",") if s.strip()]
        
        return parsed_data
        
    except json.JSONDecodeError as e:
        print(f"⚠️ JSON decode error: {e}")
        # Return fallback with original text
        return {
            "title": "",
            "department": "",
            "location": "",
            "type": "Full-time",
            "experience": "",
            "salary": "",
            "skills": [],
            "description": jd_text,
            "deadline": None,
            "error": "Failed to parse JD. Please fill manually."
        }
    except Exception as e:
        print(f"❌ AI parsing error: {e}")
        raise
