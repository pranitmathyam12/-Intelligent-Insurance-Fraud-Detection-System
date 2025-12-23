#!/bin/bash

# Test script for fraud detection endpoints

echo "=== Testing Fraud Detection Pipeline ==="
echo ""

# Test data (simplified health claim with fraud indicators)
TEST_CLAIM='{
  "transaction_id": "TEST_FRAUD_001",
  "policyholder_info": {
    "customer_id": "TEST_CUST_001",
    "customer_name": "Test Fraudster",
    "policy_number": "TEST_POL_001",
    "insurance_type": "Health"
  },
  "claim_summary": {
    "amount": "$5000.00",
    "reported_date": "2025-01-20"
  },
  "ssn": "999-01-1111",
  "agent_id": "AGENT_BAD_007",
  "vendor_id": "VNDR_BAD_666"
}'

echo "Step 1: Testing /v1/fraud/ingest_to_graph"
echo "Request:"
echo "$TEST_CLAIM" | jq .
echo ""

GRAPH_RESULT=$(curl -s -X POST http://localhost:8080/v1/fraud/ingest_to_graph \
  -H "Content-Type: application/json" \
  -d "$TEST_CLAIM")

echo "Response:"
echo "$GRAPH_RESULT" | jq .
echo ""

# Check if fraud was detected
IS_FRAUD=$(echo "$GRAPH_RESULT" | jq -r '.is_fraudulent')
echo "Fraud Detected: $IS_FRAUD"
echo ""

if [ "$IS_FRAUD" = "true" ]; then
  echo "✓ Fraud patterns detected successfully!"
  echo ""
  
  # Now test LLM analysis
  echo "Step 2: Testing /v1/fraud/analyze"
  
  ANALYSIS_REQUEST=$(jq -n \
    --argjson claim "$TEST_CLAIM" \
    --argjson graph "$GRAPH_RESULT" \
    '{claim_data: $claim, graph_results: $graph}')
  
  echo "Request:"
  echo "$ANALYSIS_REQUEST" | jq .
  echo ""
  
  ANALYSIS_RESULT=$(curl -s -X POST http://localhost:8080/v1/fraud/analyze \
    -H "Content-Type: application/json" \
    -d "$ANALYSIS_REQUEST")
  
  echo "Response:"
  echo "$ANALYSIS_RESULT" | jq .
  echo ""
  
  RISK_SCORE=$(echo "$ANALYSIS_RESULT" | jq -r '.risk_score')
  echo "Risk Score: $RISK_SCORE/100"
  echo ""
  
  echo "✓ LLM analysis completed successfully!"
else
  echo "✗ No fraud detected (unexpected for this test case)"
fi

echo ""
echo "=== Test Complete ==="
