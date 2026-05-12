# Address Verification using Google Maps Geocoding API
import os
import googlemaps
from typing import Dict, Tuple, Optional
from difflib import SequenceMatcher
import re
from dotenv import load_dotenv

load_dotenv()

# Initialize Google Maps client
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
if GOOGLE_MAPS_API_KEY:
    gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)
else:
    gmaps = None
    print("⚠️ Google Maps API key not configured")


def normalize_address(address: str) -> str:
    """
    Normalize address for better comparison
    """
    if not address:
        return ""
    
    # Convert to lowercase
    address = address.lower().strip()
    
    # Common abbreviation expansions
    abbreviations = {
        'mg road': 'mahatma gandhi road',
        'mg rd': 'mahatma gandhi road',
        'jr road': 'jawaharlal nehru road',
        'jn road': 'jawaharlal nehru road',
        'apts': 'apartments',
        'apt': 'apartment',
        'bldg': 'building',
        'blk': 'block',
        'st': 'street',
        'rd': 'road',
        'ave': 'avenue',
        'blvd': 'boulevard',
        'nagar': 'nagar',
        'colony': 'colony',
        'layout': 'layout'
    }
    
    # Replace abbreviations
    for abbr, full in abbreviations.items():
        address = re.sub(r'\b' + abbr + r'\b', full, address)
    
    # Remove extra spaces and punctuation
    address = re.sub(r'[,\-\.\(\)]', ' ', address)
    address = re.sub(r'\s+', ' ', address)
    
    return address.strip()


def extract_address_components(geocode_result: dict) -> Dict[str, str]:
    """
    Extract standardized address components from Google geocoding result
    """
    components = {
        'street_number': '',
        'route': '',
        'locality': '',
        'sublocality': '',
        'administrative_area_level_2': '',  # District
        'administrative_area_level_1': '',  # State
        'postal_code': '',
        'country': ''
    }
    
    if not geocode_result or 'address_components' not in geocode_result:
        return components
    
    for component in geocode_result['address_components']:
        for comp_type in component['types']:
            if comp_type in components:
                components[comp_type] = component['long_name']
    
    return components


def calculate_similarity(str1: str, str2: str) -> float:
    """
    Calculate similarity between two strings using SequenceMatcher
    """
    if not str1 or not str2:
        return 0.0
    
    # Normalize both strings
    str1_norm = normalize_address(str1)
    str2_norm = normalize_address(str2)
    
    return SequenceMatcher(None, str1_norm, str2_norm).ratio()


def calculate_component_scores(candidate_address: str, google_components: Dict[str, str]) -> Dict[str, float]:
    """
    Calculate similarity scores for each address component
    """
    # Parse candidate address (basic parsing)
    candidate_lower = candidate_address.lower()
    
    scores = {}
    
    # Street number matching
    street_numbers = re.findall(r'\b\d+[a-z]?\b', candidate_lower)
    if street_numbers and google_components['street_number']:
        scores['street_number'] = 1.0 if google_components['street_number'].lower() in street_numbers else 0.0
    else:
        scores['street_number'] = 0.5  # Neutral if not found
    
    # Route/Street name matching
    if google_components['route']:
        scores['route'] = calculate_similarity(candidate_lower, google_components['route'])
    else:
        scores['route'] = 0.5
    
    # Locality matching
    locality_terms = [google_components['locality'], google_components['sublocality']]
    locality_score = 0.0
    for term in locality_terms:
        if term and term.lower() in candidate_lower:
            locality_score = max(locality_score, 1.0)
        elif term:
            locality_score = max(locality_score, calculate_similarity(candidate_lower, term))
    scores['locality'] = locality_score
    
    # City/District matching
    city_terms = [google_components['administrative_area_level_2']]
    city_score = 0.0
    for term in city_terms:
        if term and term.lower() in candidate_lower:
            city_score = max(city_score, 1.0)
        elif term:
            city_score = max(city_score, calculate_similarity(candidate_lower, term))
    scores['city'] = city_score
    
    # State matching
    if google_components['administrative_area_level_1']:
        state_in_address = google_components['administrative_area_level_1'].lower() in candidate_lower
        scores['state'] = 1.0 if state_in_address else calculate_similarity(candidate_lower, google_components['administrative_area_level_1'])
    else:
        scores['state'] = 0.5
    
    # Pincode matching
    candidate_pincodes = re.findall(r'\b\d{6}\b', candidate_address)
    if candidate_pincodes and google_components['postal_code']:
        scores['pincode'] = 1.0 if google_components['postal_code'] in candidate_pincodes else 0.0
    else:
        scores['pincode'] = 0.5
    
    return scores


def calculate_overall_score(component_scores: Dict[str, float]) -> float:
    """
    Calculate weighted overall similarity score
    """
    weights = {
        'street_number': 0.15,
        'route': 0.25,
        'locality': 0.20,
        'city': 0.15,
        'state': 0.10,
        'pincode': 0.15
    }
    
    total_score = 0.0
    for component, score in component_scores.items():
        weight = weights.get(component, 0.0)
        total_score += score * weight
    
    return min(total_score, 1.0)  # Cap at 1.0


def get_verification_status(overall_score: float) -> Tuple[str, str]:
    """
    Determine verification status based on overall score
    """
    if overall_score >= 0.90:
        return "VERIFIED", "HIGH_CONFIDENCE"
    elif overall_score >= 0.75:
        return "VERIFIED", "MEDIUM_CONFIDENCE"
    elif overall_score >= 0.60:
        return "REQUIRES_REVIEW", "LOW_CONFIDENCE"
    else:
        return "NOT_VERIFIED", "VERY_LOW_CONFIDENCE"


async def verify_address(candidate_address: str) -> Dict:
    """
    Main function to verify address using Google Maps Geocoding API
    
    Args:
        candidate_address: Address provided by candidate
    
    Returns:
        Dictionary with verification results
    """
    if not gmaps:
        return {
            "status": "ERROR",
            "message": "Google Maps API not configured",
            "confidence": "NONE",
            "overall_score": 0.0
        }
    
    if not candidate_address or len(candidate_address.strip()) < 10:
        return {
            "status": "ERROR",
            "message": "Address too short or empty",
            "confidence": "NONE",
            "overall_score": 0.0
        }
    
    try:
        # Geocode the address
        geocode_result = gmaps.geocode(candidate_address)
        
        if not geocode_result:
            return {
                "status": "NOT_FOUND",
                "message": "Address not found in Google Maps",
                "confidence": "NONE",
                "overall_score": 0.0,
                "candidate_address": candidate_address
            }
        
        # Get the best result (first one)
        best_result = geocode_result[0]
        
        # Extract components
        google_components = extract_address_components(best_result)
        
        # Get standardized address from Google
        google_formatted_address = best_result.get('formatted_address', '')
        
        # Calculate component scores
        component_scores = calculate_component_scores(candidate_address, google_components)
        
        # Calculate overall score
        overall_score = calculate_overall_score(component_scores)
        
        # Get verification status
        status, confidence = get_verification_status(overall_score)
        
        # Get coordinates
        location = best_result.get('geometry', {}).get('location', {})
        
        return {
            "status": status,
            "confidence": confidence,
            "overall_score": round(overall_score, 3),
            "candidate_address": candidate_address,
            "google_formatted_address": google_formatted_address,
            "coordinates": {
                "latitude": location.get('lat'),
                "longitude": location.get('lng')
            },
            "component_scores": {k: round(v, 3) for k, v in component_scores.items()},
            "google_components": google_components,
            "place_id": best_result.get('place_id'),
            "address_type": best_result.get('types', [])
        }
        
    except googlemaps.exceptions.ApiError as e:
        return {
            "status": "API_ERROR",
            "message": f"Google Maps API error: {str(e)}",
            "confidence": "NONE",
            "overall_score": 0.0
        }
    
    except Exception as e:
        return {
            "status": "ERROR",
            "message": f"Verification error: {str(e)}",
            "confidence": "NONE",
            "overall_score": 0.0
        }


# Test function
async def test_address_verification():
    """
    Test function to verify the address verification works
    """
    test_addresses = [
        "123, MG Road, Koramangala, Bangalore, Karnataka 560034",
        "Flat 301, Green Valley Apartments, Whitefield, Bangalore 560066",
        "Invalid address that doesn't exist"
    ]
    
    print("🧪 Testing Address Verification")
    print("=" * 50)
    
    for address in test_addresses:
        print(f"\n📍 Testing: {address}")
        result = await verify_address(address)
        
        print(f"Status: {result['status']}")
        print(f"Confidence: {result['confidence']}")
        print(f"Score: {result['overall_score']}")
        
        if result['status'] in ['VERIFIED', 'REQUIRES_REVIEW']:
            print(f"Google Address: {result.get('google_formatted_address', 'N/A')}")
            print(f"Component Scores: {result.get('component_scores', {})}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_address_verification())