from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class FraudPattern(BaseModel):
    """Represents a detected fraud pattern"""
    pattern_type: str = Field(..., description="Type of fraud pattern (e.g., 'Shared SSN', 'Asset Recycling')")
    confidence: str = Field(..., description="Confidence level: HIGH, MEDIUM, LOW")
    evidence: List[str] = Field(..., description="List of evidence supporting this pattern")
    related_entities: Dict[str, Any] = Field(default_factory=dict, description="Related entities (e.g., SSN value, VIN, Agent ID)")

class GraphIngestResponse(BaseModel):
    """Response from graph ingestion and fraud detection"""
    success: bool
    claim_id: str
    nodes_created: int
    relationships_created: int
    is_fraudulent: bool
    fraud_score: float = Field(..., ge=0.0, le=100.0, description="Fraud probability score 0-100")
    detected_patterns: List[Any] = Field(default_factory=list, description="List of detected fraud patterns")
    graph_summary: Dict[str, Any] = Field(default_factory=dict, description="Summary of graph state after ingestion")
    fraud_graph_output: Dict[str, Any] = Field(default_factory=dict, description="Full graph visualization data (nodes and edges)")
    original_claim_data: Dict[str, Any] = Field(default_factory=dict, description="Original claim data for downstream analysis")

class FraudAnalysisRequest(BaseModel):
    """Request for LLM-based fraud analysis"""
    claim_data: Dict[str, Any] = Field(..., description="Original extracted claim data")
    graph_results: GraphIngestResponse = Field(..., description="Results from graph fraud detection")

class FraudAnalysisResponse(BaseModel):
    """LLM analysis of fraud detection results"""
    is_fraudulent: bool
    confidence_level: str = Field(..., description="Overall confidence: HIGH, MEDIUM, LOW")
    risk_score: float = Field(..., ge=0.0, le=100.0, description="Risk score 0-100")
    summary: str = Field(..., description="Brief summary of the analysis")
    detailed_reasoning: str = Field(..., description="Detailed explanation of why this is/isn't fraud")
    recommendations: List[str] = Field(..., description="Recommended actions")
    red_flags: List[str] = Field(default_factory=list, description="Specific red flags identified")
    mitigating_factors: List[str] = Field(default_factory=list, description="Factors that reduce fraud likelihood")
