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

class VehicleDetails(BaseModel):
    vehicle_type: Optional[str] = None
    license_plate: Optional[str] = None
    vin: Optional[str] = None
    make_model: Optional[str] = None

class IncidentDetails(BaseModel):
    date_of_loss: Optional[str] = None
    incident_city: Optional[str] = None
    incident_state: Optional[str] = None
    incident_hour: Optional[str] = None
    description: Optional[str] = None

class RequiredDocuments(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    Drivers_License: Optional[bool] = Field(default=None, alias="Driver's License")
    Vehicle_Registration: Optional[bool] = Field(default=None, alias="Vehicle Registration Certificate")
    Police_Report: Optional[bool] = Field(default=None, alias="Police Report (FIR copy)")
    Photos: Optional[bool] = Field(default=None, alias="Photos of vehicle damage")
    Repair_Estimates: Optional[bool] = Field(default=None, alias="Repair Estimates")

class MotorClaim(BaseModel):
    company_name: Optional[str] = None
    transaction_id: Optional[str] = None
    policyholder_info: PolicyholderInfo
    claim_summary: ClaimSummary
    vehicle_details: VehicleDetails
    incident_details: IncidentDetails
    required_documents: RequiredDocuments
    notes: Optional[str] = None
    summary: Optional[str] = None
