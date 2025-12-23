# Fraud Detection Pipeline - Updated Usage Guide

## Overview
The fraud detection pipeline now has **intelligent, adaptive endpoints** that work with any claim type:

1. **`POST /v1/extract`** - Classifies and extracts claim data from PDF
2. **`POST /v1/fraud/ingest_to_graph`** - **NEW**: Accepts FULL `/v1/extract` output, intelligently extracts required fields, loads to Neo4j, detects fraud
3. **`POST /v1/fraud/analyze`** - **NEW**: Accepts FULL `/v1/fraud/ingest_to_graph` output, uses LLM to analyze and explain

## Key Features

### ✨ Fully Adaptive
- **No manual field mapping required** - Just pass the entire response from one endpoint to the next
- **Works with ALL claim types** - Health, Life, Motor, Mobile, Property, Travel
- **Intelligent field extraction** - Automatically finds SSN, Agent ID, VIN, IMEI, etc. regardless of where they appear

### 🔄 Simple Workflow
```
PDF → /v1/extract → /v1/fraud/ingest_to_graph → /v1/fraud/analyze
```

## Complete Workflow Example (Postman)

### Step 1: Extract Claim Data from PDF
**Endpoint**: `POST http://localhost:8080/v1/extract`

**Body** (form-data):
- `file`: Upload PDF
- `doc_type`: (optional) Auto-detected if not provided

**Response**:
```json
{
  "doc_type": "health",
  "classification_source": "auto",
  "model": "gemini-2.5-flash",
  "result": {
    "company_name": "PREMIER INSURANCE GROUP",
    "transaction_id": "TXN00000001",
    "policyholder_info": {
      "policy_number": "PLC00008468",
      "customer_name": "Christopher Demarest",
      "insurance_type": "Health",
      "customer_id": "A00003822"
    },
    "claim_summary": {
      "amount": "$9,000.00",
      "reported_date": "May 21, 2020",
      "severity": "Major Loss"
    },
    "medical_details": {
      "diagnosis_code": "I10",
      "procedure_code": "99214",
      "provider_name": "Urgent Care Plus"
    }
  }
}
```

### Step 2: Ingest to Graph and Detect Fraud
**Endpoint**: `POST http://localhost:8080/v1/fraud/ingest_to_graph`

**Body** (raw JSON): **Copy the ENTIRE response from Step 1**
```json
{
  "doc_type": "health",
  "classification_source": "auto",
  "model": "gemini-2.5-flash",
  "result": {
    "company_name": "PREMIER INSURANCE GROUP",
    "transaction_id": "TXN00000001",
    ...
  }
}
```

**Response**:
```json
{
  "success": true,
  "claim_id": "TXN00000001",
  "nodes_created": 5,
  "relationships_created": 6,
  "is_fraudulent": true,
  "fraud_score": 0.6,
  "detected_patterns": [
    {
      "pattern_type": "Shared SSN (Identity Fraud)",
      "confidence": "HIGH",
      "evidence": [
        "SSN 999-01-1111 is shared with 20 other people",
        "Other claimants: John Doe, Jane Smith, Bob Johnson"
      ],
      "related_entities": {
        "ssn": "999-01-1111",
        "count": 20
      }
    },
    {
      "pattern_type": "Collusive Provider Ring",
      "confidence": "HIGH",
      "evidence": [
        "Agent Bad Agent and Vendor Bad Vendor have worked together on 100 claims",
        "This pair is flagged as a known fraud ring"
      ],
      "related_entities": {
        "agent_id": "AGENT_BAD_007",
        "vendor_id": "VNDR_BAD_666",
        "shared_claims": 100
      }
    }
  ],
  "graph_summary": {
    "total_claims": 10001,
    "connected_entities": {
      "Person": 1,
      "Policy": 1,
      "Agent": 1,
      "Vendor": 1
    }
  },
  "original_claim_data": {
    "doc_type": "health",
    "result": {...}
  }
}
```

### Step 3: Get LLM Analysis
**Endpoint**: `POST http://localhost:8080/v1/fraud/analyze`

**Body** (raw JSON): **Copy the ENTIRE response from Step 2**
```json
{
  "success": true,
  "claim_id": "TXN00000001",
  "nodes_created": 5,
  "relationships_created": 6,
  "is_fraudulent": true,
  "fraud_score": 0.6,
  "detected_patterns": [...],
  "graph_summary": {...},
  "original_claim_data": {...}
}
```

**Response**:
```json
{
  "is_fraudulent": true,
  "confidence_level": "HIGH",
  "risk_score": 85.0,
  "summary": "This claim exhibits multiple high-confidence fraud indicators including identity fraud and collusive provider patterns.",
  "detailed_reasoning": "The claim shows two critical fraud patterns: 1) The SSN 999-01-1111 is shared among 20 unrelated individuals, indicating potential identity theft or synthetic identity fraud. 2) The agent-vendor pair (AGENT_BAD_007 and VNDR_BAD_666) has an abnormally high collaboration rate of 100+ claims, suggesting organized fraud.",
  "recommendations": [
    "Immediately flag this claim for Special Investigation Unit (SIU) review",
    "Verify the claimant's identity through independent sources",
    "Investigate all claims involving AGENT_BAD_007 and VNDR_BAD_666",
    "Consider freezing payments pending investigation"
  ],
  "red_flags": [
    "Shared SSN across 20 claimants",
    "Known fraudulent agent-vendor pair",
    "High claim amount for reported incident"
  ],
  "mitigating_factors": []
}
```

## Fraud Score Calculation

The `fraud_score` (0.0 to 1.0) is calculated as:
```
fraud_score = min(number_of_patterns * 0.3, 1.0)
```

Examples:
- 0 patterns detected → 0.0 (clean)
- 1 pattern detected → 0.3 (suspicious)
- 2 patterns detected → 0.6 (likely fraud)
- 3+ patterns detected → 0.9-1.0 (definite fraud)

You can customize this in `app/services/fraud_detection.py` to weight patterns differently (e.g., Shared SSN = 0.5, Collusive Ring = 0.4).

## Supported Claim Types & Fields

The system intelligently extracts type-specific fields:

| Claim Type | Extracted Fields |
|------------|------------------|
| **Health** | `diagnosis_code`, `procedure_code`, `provider_name` |
| **Motor** | `vin`, `license_plate` |
| **Mobile** | `imei` |
| **Property** | `property_address`, `damage_type` |
| **Life** | `date_of_death`, `cause_of_death` |
| **Travel** | `destination`, `flight_ref` |

All types also extract: `ssn`, `agent_id`, `vendor_id` (if present in the extraction)

## Fraud Patterns Detected

1. **Shared SSN (Identity Fraud)**: Multiple people using the same SSN
2. **Collusive Provider Ring**: Agent-Vendor pairs with >10 shared claims
3. **Asset Recycling**: Same VIN/IMEI/Address claimed multiple times
4. **Velocity Fraud**: Person filing 4+ claims

## Configuration

Add to `.env`:
```
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password_here
```

## Notes

- The endpoints are **fully backward compatible** - you can still pass structured data if needed
- The system automatically handles missing fields (e.g., if SSN isn't extracted, it's simply not used for fraud detection)
- Agent/Vendor names are automatically looked up from `Data_Prep_Code/Data/employee_data.csv` and `vendor_data.csv`
