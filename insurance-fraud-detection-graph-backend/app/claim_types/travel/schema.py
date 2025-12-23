from typing import Optional
from pydantic import BaseModel, Field, ConfigDict

class PolicyholderInfo(BaseModel):
    policy_number: Optional[str] = None
    customer_name: Optional[str] = None
    insurance_type: Optional[str] = None
    customer_id: Optional[str] = None
    ssn: Optional[str] = None

class ClaimSummary(BaseModel):
    amount: Optional[str] = None
    reported_date: Optional[str] = None

class TripDetails(BaseModel):
    trip_start_date: Optional[str] = None
    trip_end_date: Optional[str] = None
    destination: Optional[str] = None
    flight_ref: Optional[str] = None
    covered_perils: Optional[str] = None

class RequiredDocuments(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    Boarding_Pass: Optional[bool] = Field(default=None, alias="Boarding Pass")
    Ticket_Copy: Optional[bool] = Field(default=None, alias="Ticket Copy")
    Medical_Bills: Optional[bool] = Field(default=None, alias="Medical Bills")
    Police_Report: Optional[bool] = Field(default=None, alias="Police Report")

class TravelClaim(BaseModel):
    company_name: Optional[str] = None
    transaction_id: Optional[str] = None
    policyholder_info: PolicyholderInfo
    claim_summary: ClaimSummary
    trip_details: TripDetails
    required_documents: RequiredDocuments
    notes: Optional[str] = None
    summary: Optional[str] = None
