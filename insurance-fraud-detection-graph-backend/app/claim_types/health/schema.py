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

class MedicalDetails(BaseModel):
    provider_name: Optional[str] = None
    diagnosis_code: Optional[str] = None
    procedure_code: Optional[str] = None
    treatment_date: Optional[str] = None

class RequiredDocuments(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    Medical_Bills: Optional[bool] = Field(default=None, alias="Medical Bills")
    Prescription_Receipts: Optional[bool] = Field(default=None, alias="Prescription Receipts")
    Doctors_Certificate: Optional[bool] = Field(default=None, alias="Doctor's Certificate")
    Diagnostic_Reports: Optional[bool] = Field(default=None, alias="Diagnostic Reports")
    Insurance_Card: Optional[bool] = Field(default=None, alias="Insurance Card")

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
    medical_details: MedicalDetails
    required_documents: RequiredDocuments
    event_details: EventDetails

    notes: Optional[str] = None
    summary: Optional[str] = None