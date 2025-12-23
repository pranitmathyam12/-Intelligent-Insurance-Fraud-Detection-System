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

class DeviceDetails(BaseModel):
    device_model: Optional[str] = None
    imei: Optional[str] = None
    loss_type: Optional[str] = None

class RequiredDocuments(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    Proof_of_Purchase: Optional[bool] = Field(default=None, alias="Proof of Purchase")
    Photos_of_Damage: Optional[bool] = Field(default=None, alias="Photos of Damage")
    Police_Report: Optional[bool] = Field(default=None, alias="Police Report")

class MobileClaim(BaseModel):
    company_name: Optional[str] = None
    transaction_id: Optional[str] = None
    policyholder_info: PolicyholderInfo
    claim_summary: ClaimSummary
    device_details: DeviceDetails
    required_documents: RequiredDocuments
    notes: Optional[str] = None
    summary: Optional[str] = None
