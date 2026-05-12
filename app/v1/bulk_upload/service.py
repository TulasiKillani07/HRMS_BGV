"""
Business logic for bulk candidate upload
"""
import csv
import io
from typing import List, Dict, Tuple
from datetime import datetime, timezone

# Import from core
from core.database import candidatesCol


class BulkUploadService:
    """Service for handling bulk candidate uploads via CSV"""
    
    # Required CSV columns
    REQUIRED_COLUMNS = [
        "firstName", "lastName", "phone", "email", "aadhaarNumber", "panNumber",
        "fatherName", "dob", "gender", "address", "district", "state", "pincode"
    ]
    
    # Optional CSV columns
    OPTIONAL_COLUMNS = [
        "middleName", "uanNumber",
        # Supervisory Check 1
        "supervisory1_name", "supervisory1_phone", "supervisory1_email",
        "supervisory1_relationship", "supervisory1_company", "supervisory1_designation",
        "supervisory1_workingPeriod",
        # Supervisory Check 2
        "supervisory2_name", "supervisory2_phone", "supervisory2_email",
        "supervisory2_relationship", "supervisory2_company", "supervisory2_designation",
        "supervisory2_workingPeriod",
        # Employment History 1
        "employment1_company", "employment1_designation", "employment1_joiningDate",
        "employment1_relievingDate", "employment1_hrContact", "employment1_hrEmail",
        "employment1_hrName", "employment1_address",
        # Employment History 2
        "employment2_company", "employment2_designation", "employment2_joiningDate",
        "employment2_relievingDate", "employment2_hrContact", "employment2_hrEmail",
        "employment2_hrName", "employment2_address",
        # Education
        "education_degree", "education_specialization", "education_universityName",
        "education_collegeName", "education_yearOfPassing", "education_cgpa",
        "education_universityContact", "education_universityEmail", "education_universityAddress",
        "education_collegeContact", "education_collegeEmail", "education_collegeAddress"
    ]
    
    MAX_ROWS = 1000
    
    def parse_csv(self, file_content: bytes) -> Tuple[List[str], List[Dict]]:
        """
        Parse CSV file content
        
        Args:
            file_content: Raw CSV file bytes
            
        Returns:
            Tuple of (headers, rows)
            
        Raises:
            ValueError: If CSV is invalid
        """
        try:
            decoded = file_content.decode('utf-8')
            csv_reader = csv.DictReader(io.StringIO(decoded))
            
            headers = csv_reader.fieldnames
            if not headers:
                raise ValueError("CSV file is empty or has no headers")
            
            rows = list(csv_reader)
            
            if len(rows) == 0:
                raise ValueError("CSV file has no data rows")
            
            if len(rows) > self.MAX_ROWS:
                raise ValueError(f"Maximum {self.MAX_ROWS} candidates allowed per upload")
            
            return headers, rows
            
        except UnicodeDecodeError:
            raise ValueError("Invalid CSV file encoding. Please use UTF-8")
        except Exception as e:
            raise ValueError(f"Error reading CSV file: {str(e)}")
    
    def validate_headers(self, headers: List[str]) -> List[str]:
        """
        Validate CSV headers
        
        Args:
            headers: List of column names from CSV
            
        Returns:
            List of missing required columns (empty if valid)
        """
        missing_columns = [col for col in self.REQUIRED_COLUMNS if col not in headers]
        return missing_columns
    
    def validate_row(self, row: Dict, row_number: int) -> Tuple[bool, str]:
        """
        Validate a single CSV row
        
        Args:
            row: Dictionary of row data
            row_number: Row number for error reporting
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        missing_fields = []
        for field in self.REQUIRED_COLUMNS:
            if not row.get(field) or not row.get(field).strip():
                missing_fields.append(field)
        
        if missing_fields:
            return False, f"Missing required fields: {', '.join(missing_fields)}"
        
        return True, ""
    
    async def check_duplicate(self, email: str, pan: str, aadhaar: str) -> bool:
        """
        Check if candidate already exists
        
        Args:
            email: Candidate email
            pan: PAN number
            aadhaar: Aadhaar number
            
        Returns:
            True if duplicate exists, False otherwise
        """
        existing = await candidatesCol.find_one({
            "$or": [
                {"email": email},
                {"panNumber": pan},
                {"aadhaarNumber": aadhaar}
            ]
        })
        return existing is not None
    
    def build_candidate_document(
        self,
        row: Dict,
        org_id: str,
        org_name: str,
        creator_email: str
    ) -> Dict:
        """
        Build candidate document from CSV row
        
        Args:
            row: CSV row data
            org_id: Organization ID
            org_name: Organization name
            creator_email: Email of user creating the candidate
            
        Returns:
            Candidate document ready for MongoDB insertion
        """
        now = datetime.now(timezone.utc)
        
        # Build base document with required fields
        candidate_doc = {
            "firstName": row.get("firstName").strip(),
            "middleName": row.get("middleName", "").strip() or None,
            "lastName": row.get("lastName").strip(),
            "phone": row.get("phone").strip(),
            "aadhaarNumber": row.get("aadhaarNumber").strip(),
            "panNumber": row.get("panNumber").strip(),
            "address": row.get("address").strip(),
            "email": row.get("email").strip(),
            "fatherName": row.get("fatherName").strip(),
            "dob": row.get("dob").strip(),
            "gender": row.get("gender").strip(),
            "uanNumber": row.get("uanNumber", "").strip() or None,
            "district": row.get("district").strip(),
            "state": row.get("state").strip(),
            "pincode": row.get("pincode").strip(),
            "organizationId": org_id,
            "organizationName": org_name,
            "status": "PENDING",
            "createdAt": now,
            "createdBy": creator_email
        }
        
        # Add optional fields if present
        # Supervisory Check 1
        if row.get("supervisory1_name") or row.get("supervisory1_phone"):
            candidate_doc["supervisoryCheck1"] = {
                "name": row.get("supervisory1_name", "").strip() or None,
                "phone": row.get("supervisory1_phone", "").strip() or None,
                "email": row.get("supervisory1_email", "").strip() or None,
                "relationship": row.get("supervisory1_relationship", "").strip() or None,
                "company": row.get("supervisory1_company", "").strip() or None,
                "designation": row.get("supervisory1_designation", "").strip() or None,
                "workingPeriod": row.get("supervisory1_workingPeriod", "").strip() or None
            }
        
        # Supervisory Check 2
        if row.get("supervisory2_name") or row.get("supervisory2_phone"):
            candidate_doc["supervisoryCheck2"] = {
                "name": row.get("supervisory2_name", "").strip() or None,
                "phone": row.get("supervisory2_phone", "").strip() or None,
                "email": row.get("supervisory2_email", "").strip() or None,
                "relationship": row.get("supervisory2_relationship", "").strip() or None,
                "company": row.get("supervisory2_company", "").strip() or None,
                "designation": row.get("supervisory2_designation", "").strip() or None,
                "workingPeriod": row.get("supervisory2_workingPeriod", "").strip() or None
            }
        
        # Employment History 1
        if row.get("employment1_company"):
            candidate_doc["employmentHistory1"] = {
                "company": row.get("employment1_company", "").strip() or None,
                "designation": row.get("employment1_designation", "").strip() or None,
                "joiningDate": row.get("employment1_joiningDate", "").strip() or None,
                "relievingDate": row.get("employment1_relievingDate", "").strip() or None,
                "hrContact": row.get("employment1_hrContact", "").strip() or None,
                "hrEmail": row.get("employment1_hrEmail", "").strip() or None,
                "hrName": row.get("employment1_hrName", "").strip() or None,
                "address": row.get("employment1_address", "").strip() or None
            }
        
        # Employment History 2
        if row.get("employment2_company"):
            candidate_doc["employmentHistory2"] = {
                "company": row.get("employment2_company", "").strip() or None,
                "designation": row.get("employment2_designation", "").strip() or None,
                "joiningDate": row.get("employment2_joiningDate", "").strip() or None,
                "relievingDate": row.get("employment2_relievingDate", "").strip() or None,
                "hrContact": row.get("employment2_hrContact", "").strip() or None,
                "hrEmail": row.get("employment2_hrEmail", "").strip() or None,
                "hrName": row.get("employment2_hrName", "").strip() or None,
                "address": row.get("employment2_address", "").strip() or None
            }
        
        # Education
        if row.get("education_degree"):
            candidate_doc["educationCheck"] = {
                "degree": row.get("education_degree", "").strip() or None,
                "specialization": row.get("education_specialization", "").strip() or None,
                "universityName": row.get("education_universityName", "").strip() or None,
                "collegeName": row.get("education_collegeName", "").strip() or None,
                "yearOfPassing": row.get("education_yearOfPassing", "").strip() or None,
                "cgpa": row.get("education_cgpa", "").strip() or None,
                "universityContact": row.get("education_universityContact", "").strip() or None,
                "universityEmail": row.get("education_universityEmail", "").strip() or None,
                "universityAddress": row.get("education_universityAddress", "").strip() or None,
                "collegeContact": row.get("education_collegeContact", "").strip() or None,
                "collegeEmail": row.get("education_collegeEmail", "").strip() or None,
                "collegeAddress": row.get("education_collegeAddress", "").strip() or None
            }
        
        return candidate_doc
    
    async def process_csv_upload(
        self,
        file_content: bytes,
        org_id: str,
        org_name: str,
        creator_email: str
    ) -> Dict:
        """
        Process CSV file and upload candidates
        
        Args:
            file_content: Raw CSV file bytes
            org_id: Organization ID
            org_name: Organization name
            creator_email: Email of user uploading
            
        Returns:
            Dictionary with upload results
        """
        # Parse CSV
        headers, rows = self.parse_csv(file_content)
        
        # Validate headers
        missing_columns = self.validate_headers(headers)
        if missing_columns:
            raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")
        
        # Process each row
        successful_candidates = []
        failed_rows = []
        
        for idx, row in enumerate(rows, start=2):  # Start from 2 (row 1 is header)
            try:
                # Validate row
                is_valid, error_msg = self.validate_row(row, idx)
                if not is_valid:
                    failed_rows.append({
                        "row": idx,
                        "data": row,
                        "error": error_msg
                    })
                    continue
                
                # Check for duplicates
                email = row.get("email").strip()
                pan = row.get("panNumber").strip()
                aadhaar = row.get("aadhaarNumber").strip()
                
                is_duplicate = await self.check_duplicate(email, pan, aadhaar)
                if is_duplicate:
                    failed_rows.append({
                        "row": idx,
                        "data": row,
                        "error": "Duplicate candidate - email, PAN, or Aadhaar already exists"
                    })
                    continue
                
                # Build and insert candidate document
                candidate_doc = self.build_candidate_document(row, org_id, org_name, creator_email)
                result = await candidatesCol.insert_one(candidate_doc)
                
                successful_candidates.append({
                    "row": idx,
                    "candidateId": str(result.inserted_id),
                    "name": f"{row.get('firstName')} {row.get('lastName')}",
                    "email": email
                })
                
            except Exception as e:
                failed_rows.append({
                    "row": idx,
                    "data": row,
                    "error": str(e)
                })
        
        # Return results
        return {
            "status": "completed",
            "summary": {
                "totalRows": len(rows),
                "successful": len(successful_candidates),
                "failed": len(failed_rows)
            },
            "successfulCandidates": successful_candidates,
            "failedRows": failed_rows
        }
    
    def generate_csv_template(self) -> str:
        """
        Generate CSV template with REQUIRED fields only and sample data
        
        Returns:
            CSV content as string
        """
        # Only required columns
        columns = self.REQUIRED_COLUMNS
        
        # Sample data row (only required fields)
        sample_data = {
            "firstName": "John",
            "lastName": "Doe",
            "phone": "9876543210",
            "email": "john.doe@example.com",
            "aadhaarNumber": "123456789012",
            "panNumber": "ABCDE1234F",
            "fatherName": "Robert Doe",
            "dob": "1990-01-15",
            "gender": "Male",
            "address": "123 Main Street, Apartment 4B",
            "district": "Mumbai",
            "state": "Maharashtra",
            "pincode": "400001"
        }
        
        # Create CSV
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=columns)
        writer.writeheader()
        writer.writerow(sample_data)
        
        csv_content = output.getvalue()
        output.close()
        
        return csv_content
