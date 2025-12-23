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
    severity: Optional[str] = None

class PropertyDetails(BaseModel):
    property_type: Optional[str] = None
    property_address: Optional[str] = None
    damage_type: Optional[str] = None
    estimated_repair_cost: Optional[str] = None

class RequiredDocuments(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    Proof_of_Ownership: Optional[bool] = Field(default=None, alias="Proof of Ownership")
    Photos_of_Damage: Optional[bool] = Field(default=None, alias="Photos of Damage")
    Repair_Estimates: Optional[bool] = Field(default=None, alias="Repair Estimates")
    Police_Report: Optional[bool] = Field(default=None, alias="Police Report")

class PropertyClaim(BaseModel):
    company_name: Optional[str] = None
    transaction_id: Optional[str] = None
    policyholder_info: PolicyholderInfo
    claim_summary: ClaimSummary
    property_details: PropertyDetails
    required_documents: RequiredDocuments
    notes: Optional[str] = None
    summary: Optional[str] = None