"""
app/routes/evaluation.py - Model evaluation endpoint
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
import pandas as pd
import structlog
from pathlib import Path
from app.db.neo4j_utils import check_claim_fraud_risk, detect_fraud_patterns

router = APIRouter(prefix="/v1", tags=["Evaluation"])
log = structlog.get_logger()

class EvaluationResponse(BaseModel):
    """Evaluation results"""
    total_claims_evaluated: int
    fraud_detected: int
    fraud_rate: float
    avg_fraud_score: float
    score_distribution: Dict[str, int]
    pattern_summary: List[Dict[str, Any]]
    top_risk_claims: List[Dict[str, Any]]
    risk_level_distribution: Dict[str, int]

@router.post("/evaluate")
async def evaluate_model(sample_size: int = 500):
    """
    Run evaluation on sample claims from the database
    
    Args:
        sample_size: Number of claims to evaluate (default 500, max 1000)
    
    Returns:
        EvaluationResponse with comprehensive statistics
    """
    try:
        log.info("evaluation.start", sample_size=sample_size)
        
        # Limit sample size
        sample_size = min(sample_size, 1000)
        
        # Load claims from CSV
        csv_path = Path("/Users/aakashbelide/Aakash/Higher Studies/Course/Sem-3/DAMG 7374/insurance-fraud-detection-graph-backend/Data_Prep_Code/Data/insurance_data_enriched.csv")
        if not csv_path.exists():
            raise HTTPException(status_code=404, detail="CSV file not found")
        
        df = pd.read_csv(csv_path)
        
        # Random sample
        sample_df = df.sample(n=min(sample_size, len(df)), random_state=42)
        
        log.info("evaluation.sample_loaded", size=len(sample_df))
        
        # Run fraud detection on each claim
        results = []
        fraud_count = 0
        total_score = 0
        score_ranges = {"0-20": 0, "20-40": 0, "40-60": 0, "60-80": 0, "80-100": 0}
        risk_levels = {"Low": 0, "Medium": 0, "High": 0}
        
        for idx, row in sample_df.iterrows():
            try:
                # Prepare claim data
                claim_data = {
                    'transaction_id': row.get('TRANSACTION_ID'),
                    'customer_id': row.get('CUSTOMER_ID'),
                    'ssn': row.get('SSN'),
                    'claim_amount': float(row.get('CLAIM_AMOUNT', 0)),
                    'insurance_type': row.get('INSURANCE_TYPE'),
                    'agent_id': row.get('AGENT_ID'),
                    'vendor_id': row.get('VENDOR_ID')
                }
                
                # Skip if missing critical fields
                if not claim_data['customer_id']:
                    continue
                
                # Run fraud check
                fraud_result = check_claim_fraud_risk(claim_data)
                
                score = fraud_result['fraud_score']
                is_fraud = fraud_result['is_fraudulent']
                
                # Collect statistics
                if is_fraud:
                    fraud_count += 1
                
                total_score += score
                
                # Score distribution
                if score < 20:
                    score_ranges["0-20"] += 1
                    risk_levels["Low"] += 1
                elif score < 40:
                    score_ranges["20-40"] += 1
                    risk_levels["Low"] += 1
                elif score < 60:
                    score_ranges["40-60"] += 1
                    risk_levels["Medium"] += 1
                elif score < 80:
                    score_ranges["60-80"] += 1
                    risk_levels["Medium"] += 1
                else:
                    score_ranges["80-100"] += 1
                    risk_levels["High"] += 1
                
                # Store result
                results.append({
                    'claim_id': claim_data['transaction_id'],
                    'customer_name': row.get('CUSTOMER_NAME'),
                    'amount': claim_data['claim_amount'],
                    'fraud_score': score,
                    'is_fraudulent': is_fraud,
                    'patterns': fraud_result.get('rules_triggered', []),
                    'recommendation': fraud_result.get('recommendation')
                })
                
            except Exception as e:
                log.warning("evaluation.claim_failed", claim_id=row.get('TRANSACTION_ID'), error=str(e))
                continue
        
        # Sort by fraud score
        results.sort(key=lambda x: x['fraud_score'], reverse=True)
        
        # Get global patterns from graph
        global_patterns = detect_fraud_patterns()
        
        # Format pattern summary
        pattern_summary = []
        for pattern in global_patterns:
            pattern_summary.append({
                'pattern_name': pattern['pattern'],
                'risk_level': pattern['risk'],
                'description': pattern['description'],
                'cases_found': len(pattern['cases'])
            })
        
        # Calculate metrics
        evaluated_count = len(results)
        avg_score = total_score / evaluated_count if evaluated_count > 0 else 0
        fraud_rate = (fraud_count / evaluated_count * 100) if evaluated_count > 0 else 0
        
        log.info("evaluation.complete", 
                 evaluated=evaluated_count,
                 fraud_detected=fraud_count,
                 fraud_rate=fraud_rate)
        
        return EvaluationResponse(
            total_claims_evaluated=evaluated_count,
            fraud_detected=fraud_count,
            fraud_rate=round(fraud_rate, 2),
            avg_fraud_score=round(avg_score, 2),
            score_distribution=score_ranges,
            pattern_summary=pattern_summary,
            top_risk_claims=results[:20],  # Top 20
            risk_level_distribution=risk_levels
        )
        
    except Exception as e:
        log.error("evaluation.error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")