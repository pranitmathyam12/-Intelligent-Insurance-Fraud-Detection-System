from app.llm.client import call_model
from app.models.fraud import FraudAnalysisRequest, FraudAnalysisResponse
from app.config import settings
from google.genai import types
import json
import structlog

log = structlog.get_logger()

FRAUD_ANALYSIS_PROMPT = """You are an expert insurance fraud analyst. Analyze the following claim and fraud detection results to provide a comprehensive assessment.

## Claim Information:
{claim_data}

## Graph-Based Fraud Detection Results:
- Is Fraudulent: {is_fraudulent}
- Fraud Score: {fraud_score}
- Detected Patterns: {patterns}

## Your Task:
Provide a detailed fraud analysis including:
1. Overall assessment (fraudulent or legitimate)
2. Confidence level (HIGH/MEDIUM/LOW)
3. Risk score (0-100)
4. Brief summary
5. Detailed reasoning explaining your conclusion
6. Specific recommendations for the claims adjuster
7. Red flags identified (if any)
8. Mitigating factors that reduce fraud likelihood (if any)

Be thorough but concise. Focus on actionable insights.
"""

def _response_schema():
    return types.Schema(
        type=types.Type.OBJECT,
        required=["is_fraudulent", "confidence_level", "risk_score", "summary", "detailed_reasoning", "recommendations"],
        properties={
            "is_fraudulent": types.Schema(type=types.Type.BOOLEAN),
            "confidence_level": types.Schema(type=types.Type.STRING, enum=["HIGH", "MEDIUM", "LOW"]),
            "risk_score": types.Schema(type=types.Type.NUMBER),
            "summary": types.Schema(type=types.Type.STRING),
            "detailed_reasoning": types.Schema(type=types.Type.STRING),
            "recommendations": types.Schema(
                type=types.Type.ARRAY,
                items=types.Schema(type=types.Type.STRING)
            ),
            "red_flags": types.Schema(
                type=types.Type.ARRAY,
                items=types.Schema(type=types.Type.STRING)
            ),
            "mitigating_factors": types.Schema(
                type=types.Type.ARRAY,
                items=types.Schema(type=types.Type.STRING)
            )
        }
    )

async def analyze_fraud_with_llm(request: FraudAnalysisRequest) -> FraudAnalysisResponse:
    """
    Use LLM to analyze fraud detection results and provide detailed reasoning
    
    Args:
        request: FraudAnalysisRequest containing claim data and graph results
    
    Returns:
        FraudAnalysisResponse with LLM analysis
    """
    try:
        # Format patterns for prompt
        patterns_text = "\n".join([
            f"  - {p.get('pattern_type', 'Unknown')} (Confidence: {p.get('confidence', 'Unknown')})\n    Evidence: {', '.join(p.get('evidence', []))}"
            if isinstance(p, dict) else
            f"  - {p.pattern_type} (Confidence: {p.confidence})\n    Evidence: {', '.join(p.evidence)}"
            for p in request.graph_results.detected_patterns
        ]) if request.graph_results.detected_patterns else "  None detected"
        
        # Build prompt
        prompt_text = FRAUD_ANALYSIS_PROMPT.format(
            claim_data=json.dumps(request.claim_data, indent=2),
            is_fraudulent=request.graph_results.is_fraudulent,
            fraud_score=request.graph_results.fraud_score,
            patterns=patterns_text
        )
        
        # Call LLM with correct signature
        from google.genai import types
        text, in_tok, out_tok, cost = call_model(
            parts=[types.Part(text=prompt_text)],
            response_schema=_response_schema(),
            model=settings.GENAI_MODEL
        )
        
        # Parse response
        result = json.loads(text)
        
        return FraudAnalysisResponse(
            is_fraudulent=result['is_fraudulent'],
            confidence_level=result['confidence_level'],
            risk_score=min(max(result['risk_score'], 0), 100),  # Clamp to 0-100
            summary=result['summary'],
            detailed_reasoning=result['detailed_reasoning'],
            recommendations=result['recommendations'],
            red_flags=result.get('red_flags', []),
            mitigating_factors=result.get('mitigating_factors', [])
        )
    
    except Exception as e:
        log.error("llm_analysis.failed", error=str(e))
        raise
