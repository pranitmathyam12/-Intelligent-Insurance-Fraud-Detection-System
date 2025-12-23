import snowflake.connector
import os
import json
import structlog
from datetime import datetime

log = structlog.get_logger()

def get_snowflake_connection():
    """Create connection to Snowflake"""
    try:
        conn = snowflake.connector.connect(
            account=os.getenv('SNOWFLAKE_ACCOUNT'),
            user=os.getenv('SNOWFLAKE_USER'),
            password=os.getenv('SNOWFLAKE_PASSWORD'),
            warehouse=os.getenv('SNOWFLAKE_WAREHOUSE'),
            database=os.getenv('SNOWFLAKE_DATABASE'),
            schema=os.getenv('SNOWFLAKE_SCHEMA')
        )
        # log.info("✅ Connected to Snowflake!")
        return conn
    except Exception as e:
        log.error("❌ Snowflake connection failed", error=str(e))
        return None

def save_claim_to_snowflake(extraction_result: dict, doc_type: str, model: str, total_tokens: int, cost_usd: float, timings: dict = None, upload_timestamp: str = None, fraud_data: dict = None, pdf_base64: str = None):
    """Save extracted claim to Snowflake database"""
    
    conn = get_snowflake_connection()
    if not conn:
        log.warning("⚠️ Skipping Snowflake save - no connection")
        return False
    
    try:
        cursor = conn.cursor()
        
        # Extract important fields from the result
        result = extraction_result or {}
        transaction_id = result.get('transaction_id', 'UNKNOWN')
        company_name = result.get('company_name', '')
        
        # Get policyholder info
        policyholder = result.get('policyholder_info', {})
        policy_number = policyholder.get('policy_number', '')
        customer_name = policyholder.get('customer_name', '')
        customer_id = policyholder.get('customer_id', '')
        insurance_type = policyholder.get('insurance_type', '')
        
        # Get claim details
        claim_summary = result.get('claim_summary', {})
        claim_amount = claim_summary.get('amount', '')
        reported_date = claim_summary.get('reported_date', '')
        severity = claim_summary.get('severity', '')
        
        # Create unique ID for this claim
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        claim_id = f"{transaction_id}_{timestamp}"
        
        # Convert result to JSON string
        json_data = json.dumps(result)
        
        # Convert fraud data to JSON string
        fraud_json = json.dumps(fraud_data) if fraud_data else None
        
        # Timings
        timings = timings or {}
        
        # Insert into Snowflake - use TO_VARIANT instead of PARSE_JSON
        insert_query = """
        INSERT INTO extracted_claims (
            claim_id, transaction_id, doc_type, company_name,
            policy_number, customer_name, customer_id, insurance_type,
            claim_amount, reported_date, severity,
            extracted_data, model_used, total_tokens, cost_usd,
            upload_timestamp, classification_ms, extraction_ms, 
            graph_save_ms, fraud_check_ms, total_ms,
            fraud_data, file_content
        ) 
        SELECT 
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 
            TO_VARIANT(PARSE_JSON(%s)), %s, %s, %s,
            %s, %s, %s, %s, %s, %s,
            TO_VARIANT(PARSE_JSON(%s)), %s
        """
        
        cursor.execute(insert_query, (
            claim_id,
            transaction_id,
            doc_type,
            company_name,
            policy_number,
            customer_name,
            customer_id,
            insurance_type,
            claim_amount,
            reported_date,
            severity,
            json_data,
            model,
            total_tokens,
            cost_usd,
            upload_timestamp,
            float(timings.get('classification_ms', 0.0)),
            float(timings.get('extraction_ms', 0.0)),
            float(timings.get('graph_save_ms', 0.0)),
            float(timings.get('fraud_check_ms', 0.0)),
            float(timings.get('total_ms', 0.0)),
            fraud_json,
            pdf_base64
        ))
        
        conn.commit()
        log.info("💾 Saved to Snowflake!", claim_id=claim_id, doc_type=doc_type)
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        error_msg = f"❌ Failed to save to Snowflake - Error: {str(e)} | Type: {type(e).__name__} | Transaction: {transaction_id}"
        log.error(error_msg)
        print(error_msg)  # Also print to console for visibility
        if conn:
            conn.close()
        return False

def get_recent_claims(limit: int = 10):
    """Get recent claims from Snowflake"""
    conn = get_snowflake_connection()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor()
        query = f"""
        SELECT 
            claim_id, doc_type, customer_name, 
            claim_amount, severity, created_at
        FROM extracted_claims
        ORDER BY created_at DESC
        LIMIT {limit}
        """
        cursor.execute(query)
        results = cursor.fetchall()
        
        claims = []
        for row in results:
            claims.append({
                'claim_id': row[0],
                'doc_type': row[1],
                'customer_name': row[2],
                'claim_amount': row[3],
                'severity': row[4],
                'created_at': str(row[5])
            })
        
        cursor.close()
        conn.close()
        return claims
        
    except Exception as e:
        log.error("❌ Failed to query Snowflake", error=str(e))
        if conn:
            conn.close()
        return [] 

def get_avg_processing_time():
    """Get average processing time from Snowflake"""
    conn = get_snowflake_connection()
    if not conn:
        return 0.0
    
    try:
        cursor = conn.cursor()
        query = """
        SELECT AVG(total_ms) as avg_time
        FROM extracted_claims
        WHERE total_ms IS NOT NULL
        """
        cursor.execute(query)
        result = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        # Convert milliseconds to seconds
        return round(result[0] / 1000, 2) if result and result[0] else 0.0
        
    except Exception as e:
        log.error("❌ Failed to get avg processing time", error=str(e), error_type=type(e).__name__)
        if conn:
            conn.close()
        return 0.0

def get_risk_distribution():
    """Get risk distribution from Snowflake fraud data"""
    conn = get_snowflake_connection()
    if not conn:
        return {'low': 0, 'medium': 0, 'high': 0}
    
    try:
        cursor = conn.cursor()
        query = """
        SELECT 
            CASE 
                WHEN fraud_data:fraud_score::FLOAT < 40 THEN 'low'
                WHEN fraud_data:fraud_score::FLOAT >= 40 AND fraud_data:fraud_score::FLOAT < 75 THEN 'medium'
                ELSE 'high'
            END as risk_level,
            COUNT(*) as count
        FROM extracted_claims
        WHERE fraud_data IS NOT NULL
        GROUP BY risk_level
        """
        cursor.execute(query)
        results = cursor.fetchall()
        
        print(f"DEBUG: Risk distribution raw results: {results}")
        
        distribution = {'low': 0, 'medium': 0, 'high': 0}
        for row in results:
            if row[0]:
                distribution[row[0]] = row[1]
        
        cursor.close()
        conn.close()
        return distribution
        
    except Exception as e:
        log.error("❌ Failed to get risk distribution", error=str(e), error_type=type(e).__name__)
        if conn:
            conn.close()
        return {'low': 0, 'medium': 0, 'high': 0}

def get_claims_timeline(days: int = 30):
    """Get claims timeline for the last N days"""
    conn = get_snowflake_connection()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor()
        query = f"""
        SELECT 
            DATE(upload_timestamp) as claim_date,
            COUNT(CASE WHEN fraud_data:is_fraudulent::BOOLEAN = TRUE THEN 1 END) as fraudulent,
            COUNT(CASE WHEN fraud_data:is_fraudulent::BOOLEAN = FALSE OR fraud_data IS NULL THEN 1 END) as legitimate
        FROM extracted_claims
        WHERE upload_timestamp >= DATEADD(day, -{days}, CURRENT_DATE())
        GROUP BY DATE(upload_timestamp)
        ORDER BY claim_date ASC
        """
        cursor.execute(query)
        results = cursor.fetchall()
        
        timeline = []
        for row in results:
            timeline.append({
                'date': str(row[0]),
                'fraudulent': row[1] or 0,
                'legitimate': row[2] or 0
            })
        
        cursor.close()
        conn.close()
        return timeline
        
    except Exception as e:
        error_msg = f"❌ Failed to get claims timeline - Error: {str(e)} | Type: {type(e).__name__}"
        log.error(error_msg)
        print(error_msg)
        if conn:
            conn.close()
        return []

def get_high_risk_alerts(limit: int = 10):
    """Get recent claims for the alerts table (all claims, sorted by timestamp)"""
    conn = get_snowflake_connection()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor()
        query = f"""
        SELECT 
            transaction_id,
            insurance_type,
            COALESCE(fraud_data:fraud_score::FLOAT, 0.0) / 100.0 as risk_score,
            DATE(upload_timestamp) as date,
            CASE 
                WHEN fraud_data IS NULL THEN 'Pending'
                WHEN fraud_data:recommendation::STRING = 'REJECT' THEN 'Critical'
                WHEN fraud_data:recommendation::STRING = 'MANUAL_REVIEW' THEN 'Review'
                ELSE 'Approved'
            END as status
        FROM extracted_claims
        ORDER BY upload_timestamp DESC
        LIMIT {limit}
        """
        cursor.execute(query)
        results = cursor.fetchall()
        
        print(f"DEBUG: High risk alerts raw results (first 3): {results[:3]}")
        
        alerts = []
        for row in results:
            alerts.append({
                'claim_id': row[0],
                'type': row[1],
                'risk_score': round(row[2], 2) if row[2] else 0.0,
                'date': str(row[3]),
                'status': row[4]
            })
        
        cursor.close()
        conn.close()
        return alerts
        
    except Exception as e:
        error_msg = f"❌ Failed to get high risk alerts - Error: {str(e)} | Type: {type(e).__name__}"
        log.error(error_msg)
        print(error_msg)
        if conn:
            conn.close()
        return []

def get_monitoring_metrics():
    """Get monitoring metrics for top-level dashboard stats"""
    conn = get_snowflake_connection()
    if not conn:
        return {
            'total_tokens': 0,
            'total_cost': 0.0,
            'avg_time': 0.0,
            'total_requests': 0
        }
    
    try:
        cursor = conn.cursor()
        query = """
        SELECT 
            COALESCE(SUM(total_tokens), 0) as total_tokens,
            COALESCE(SUM(cost_usd), 0.0) as total_cost,
            COALESCE(AVG(total_ms), 0.0) as avg_time_ms,
            COUNT(*) as total_requests
        FROM extracted_claims
        """
        cursor.execute(query)
        result = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if result:
            return {
                'total_tokens': int(result[0]) if result[0] else 0,
                'total_cost': float(result[1]) if result[1] else 0.0,
                'avg_time': round(float(result[2]) / 1000, 2) if result[2] else 0.0,  # Convert ms to seconds
                'total_requests': int(result[3]) if result[3] else 0
            }
        
        return {
            'total_tokens': 0,
            'total_cost': 0.0,
            'avg_time': 0.0,
            'total_requests': 0
        }
        
    except Exception as e:
        error_msg = f"❌ Failed to get monitoring metrics - Error: {str(e)} | Type: {type(e).__name__}"
        log.error(error_msg)
        print(error_msg)
        if conn:
            conn.close()
        return {
            'total_tokens': 0,
            'total_cost': 0.0,
            'avg_time': 0.0,
            'total_requests': 0
        }

def get_token_usage_timeline(days: int = 7):
    """Get token usage and cost timeline for graph visualization"""
    conn = get_snowflake_connection()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor()
        
        # Get hourly aggregated data for better granularity
        query = f"""
        SELECT 
            DATE_TRUNC('HOUR', upload_timestamp) as time_bucket,
            COALESCE(SUM(total_tokens), 0) as tokens,
            COALESCE(SUM(cost_usd), 0.0) as cost
        FROM extracted_claims
        WHERE upload_timestamp >= DATEADD(day, -{days}, CURRENT_TIMESTAMP())
        GROUP BY DATE_TRUNC('HOUR', upload_timestamp)
        ORDER BY time_bucket ASC
        """
        
        cursor.execute(query)
        results = cursor.fetchall()
        
        timeline = []
        for row in results:
            timeline.append({
                'timestamp': str(row[0]),
                'tokens': int(row[1]) if row[1] else 0,
                'cost': round(float(row[2]), 4) if row[2] else 0.0
            })
        
        cursor.close()
        conn.close()
        return timeline
        
    except Exception as e:
        error_msg = f"❌ Failed to get token usage timeline - Error: {str(e)} | Type: {type(e).__name__}"
        log.error(error_msg)
        print(error_msg)
        if conn:
            conn.close()
        return []