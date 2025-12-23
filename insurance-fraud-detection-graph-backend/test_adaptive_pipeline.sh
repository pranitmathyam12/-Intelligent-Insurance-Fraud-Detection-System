#!/bin/bash

# Test the new adaptive endpoints with full response chaining

echo "=== Testing Adaptive Fraud Detection Pipeline ==="
echo ""

# Simulate a full /v1/extract response
EXTRACT_RESPONSE='{
  "doc_type": "health",
  "classification_source": "auto",
  "model": "gemini-2.5-flash",
  "result": {
    "company_name": "PREMIER INSURANCE GROUP",
    "transaction_id": "TEST_ADAPTIVE_001",
    "policyholder_info": {
      "policy_number": "TEST_POL_001",
      "customer_name": "Test Fraudster",
      "insurance_type": "Health",
      "customer_id": "TEST_CUST_001"
    },
    "claim_summary": {
      "amount": "$5,000.00",
      "reported_date": "2025-01-20",
      "severity": "Major Loss"
    },
    "medical_details": {
      "diagnosis_code": "I10",
      "procedure_code": "99214",
      "provider_name": "Urgent Care Plus"
    }
  },
  "ssn": "999-01-1111",
  "agent_id": "AGENT_BAD_007",
  "vendor_id": "VNDR_BAD_666"
}'

echo "Step 1: Simulating /v1/extract output"
echo "$EXTRACT_RESPONSE" | jq .
echo ""

echo "Step 2: Passing FULL extract response to /v1/fraud/ingest_to_graph"
INGEST_RESPONSE=$(curl -s -X POST http://localhost:8080/v1/fraud/ingest_to_graph \
  -H "Content-Type: application/json" \
  -d "$EXTRACT_RESPONSE")

echo "Ingest Response:"
echo "$INGEST_RESPONSE" | jq .
echo ""

IS_FRAUD=$(echo "$INGEST_RESPONSE" | jq -r '.is_fraudulent')
echo "✓ Fraud Detected: $IS_FRAUD"
echo ""

if [ "$IS_FRAUD" = "true" ]; then
  echo "Step 3: Passing FULL ingest response to /v1/fraud/analyze"
  
  ANALYSIS_RESPONSE=$(curl -s -X POST http://localhost:8080/v1/fraud/analyze \
    -H "Content-Type: application/json" \
    -d "$INGEST_RESPONSE")
  
  echo "Analysis Response:"
  echo "$ANALYSIS_RESPONSE" | jq .
  echo ""
  
  RISK_SCORE=$(echo "$ANALYSIS_RESPONSE" | jq -r '.risk_score')
  echo "✓ Risk Score: $RISK_SCORE/100"
  echo ""
  
  echo "=== ✅ Adaptive Pipeline Test Complete ==="
else
  echo "✗ No fraud detected (unexpected)"
fi
