"""
Pydantic schemas for bulk upload feature
Used for request/response validation
"""
from pydantic import BaseModel
from typing import List, Dict, Any


class BulkUploadSummary(BaseModel):
    """Summary of bulk upload operation"""
    totalRows: int
    successful: int
    failed: int


class SuccessfulCandidate(BaseModel):
    """Successfully uploaded candidate info"""
    row: int
    candidateId: str
    name: str
    email: str


class FailedRow(BaseModel):
    """Failed row info"""
    row: int
    data: Dict[str, Any]
    error: str


class BulkUploadResponse(BaseModel):
    """Response for bulk upload operation"""
    status: str
    summary: BulkUploadSummary
    successfulCandidates: List[SuccessfulCandidate]
    failedRows: List[FailedRow]
