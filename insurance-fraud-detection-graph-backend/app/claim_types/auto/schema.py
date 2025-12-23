from typing import Optional
from pydantic import BaseModel, Field, ConfigDict

class PolicyholderInfo(BaseModel):
    policy_number: Optional[str] = None
    customer_name: Optional[str] = None
    insurance_type: Optional[str] = None
    customer_id: Optional[str] = None

class ClaimSummary(BaseModel):
    amount: Optional[str] = None
    reported_date: Optional[str] = None
    severity: Optional[str] = None

class DeceasedDetails(BaseModel):
    deceased_name: Optional[str] = None
    date_of_death: Optional[str] = None
    cause_of_death: Optional[str] = None

class PaymentDetails(BaseModel):
    claim_amount_usd: Optional[str] = None
    payout_method: Optional[str] = None
    account_last4: Optional[str] = None

class BeneficiaryDetails(BaseModel):
    primary_beneficiary: Optional[str] = None
    relationship: Optional[str] = None

class RequiredDocuments(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    Death_Certificate: Optional[bool] = Field(default=None, alias="Death Certificate")
    Medical_Certificate: Optional[bool] = Field(default=None, alias="Medical Certificate")
    ID_Proof_of_Claimant: Optional[bool] = Field(default=None, alias="ID Proof of Claimant")
    Policy_Document: Optional[bool] = Field(default=None, alias="Policy Document")

class EventDetails(BaseModel):
    date_of_loss: Optional[str] = None
    incident_city: Optional[str] = None
    incident_state: Optional[str] = None

class HealthClaim(BaseModel):
    company_name: Optional[str] = None
    company_address: Optional[str] = None
    company_phone: Optional[str] = None
    company_email: Optional[str] = None
    transaction_id: Optional[str] = None

    policyholder_info: PolicyholderInfo
    claim_summary: ClaimSummary
    deceased_details: DeceasedDetails
    payment_details: PaymentDetails
    beneficiary_details: BeneficiaryDetails
    required_documents: RequiredDocuments
    event_details: EventDetails

    notes: Optional[str] = None
    summary: Optional[str] = None