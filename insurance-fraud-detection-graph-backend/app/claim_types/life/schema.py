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

class DeceasedDetails(BaseModel):
    deceased_name: Optional[str] = None
    date_of_death: Optional[str] = None
    cause_of_death: Optional[str] = None

class BeneficiaryDetails(BaseModel):
    primary_beneficiary: Optional[str] = None
    relationship: Optional[str] = None
    payout_method: Optional[str] = None

class RequiredDocuments(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    Death_Certificate: Optional[bool] = Field(default=None, alias="Death Certificate")
    Medical_Certificate: Optional[bool] = Field(default=None, alias="Medical Certificate")
    ID_Proof: Optional[bool] = Field(default=None, alias="ID Proof")
    Policy_Document: Optional[bool] = Field(default=None, alias="Policy Document")

class LifeClaim(BaseModel):
    company_name: Optional[str] = None
    transaction_id: Optional[str] = None
    policyholder_info: PolicyholderInfo
    claim_summary: ClaimSummary
    deceased_details: DeceasedDetails
    beneficiary_details: BeneficiaryDetails
    required_documents: RequiredDocuments
    notes: Optional[str] = None
    summary: Optional[str] = None
