import pandas as pd
import structlog
from app.db.snowflake_utils import get_snowflake_connection
from app.db.neo4j_utils import Neo4jConnection, load_claim_to_graph, create_graph_constraints

log = structlog.get_logger()

def load_csv_to_snowflake(csv_path: str):
    """Load CSV file into Snowflake table"""
    try:
        log.info("📂 Reading CSV file", path=csv_path)
        df = pd.read_csv(csv_path)
        
        # Replace NaN with None for SQL compatibility
        df = df.where(pd.notnull(df), None)
        
        rows = len(df)
        log.info(f"📊 CSV loaded: {rows} rows, {len(df.columns)} columns")
        
        conn = get_snowflake_connection()
        if not conn:
            return False, 0, "Snowflake connection failed"
        
        cursor = conn.cursor()
        
        # Create table
        create_table_query = """
        CREATE TABLE IF NOT EXISTS claims_raw (
            txn_date_time VARCHAR(50),
            transaction_id VARCHAR(100),
            customer_id VARCHAR(100),
            policy_number VARCHAR(100),
            policy_eff_dt VARCHAR(50),
            loss_dt VARCHAR(50),
            report_dt VARCHAR(50),
            insurance_type VARCHAR(50),
            premium_amount VARCHAR(50),
            claim_amount VARCHAR(50),
            customer_name VARCHAR(500),
            address_line1 VARCHAR(500),
            address_line2 VARCHAR(500),
            city VARCHAR(100),
            state VARCHAR(10),
            postal_code VARCHAR(20),
            ssn VARCHAR(20),
            marital_status VARCHAR(5),
            age VARCHAR(10),
            tenure VARCHAR(10),
            employment_status VARCHAR(5),
            no_of_family_members VARCHAR(10),
            risk_segmentation VARCHAR(10),
            house_type VARCHAR(50),
            social_class VARCHAR(10),
            routing_number VARCHAR(50),
            acct_number VARCHAR(100),
            customer_education_level VARCHAR(50),
            claim_status VARCHAR(10),
            incident_severity VARCHAR(50),
            authority_contacted VARCHAR(50),
            any_injury VARCHAR(10),
            police_report_available VARCHAR(10),
            incident_state VARCHAR(10),
            incident_city VARCHAR(100),
            incident_hour_of_the_day VARCHAR(10),
            agent_id VARCHAR(100),
            vendor_id VARCHAR(100)
        )
        """
        
        cursor.execute(create_table_query)
        log.info("✅ Table claims_raw created/verified")
        
        # Prepare insert query
        cols = df.columns.tolist()
        placeholders = ', '.join(['%s'] * len(cols))
        insert_query = f"INSERT INTO claims_raw VALUES ({placeholders})"
        
        # Insert in batches
        inserted = 0
        batch_size = 100
        
        for i in range(0, len(df), batch_size):
            batch = df.iloc[i:i+batch_size]
            try:
                for _, row in batch.iterrows():
                    cursor.execute(insert_query, tuple(row))
                    inserted += 1
                conn.commit()
                log.info(f"⏳ Inserted {inserted}/{rows} rows...")
            except Exception as e:
                log.warning(f"⚠️ Batch {i} partial failure", error=str(e))
                conn.rollback()
        
        cursor.close()
        conn.close()
        
        log.info(f"💾 Loaded {inserted}/{rows} rows to Snowflake")
        return True, inserted, None
        
    except Exception as e:
        log.error("❌ CSV load failed", error=str(e))
        return False, 0, str(e)

def build_graph_from_snowflake(limit: int = None):
    """Read claims from Snowflake and build Neo4j graph"""
    try:
        log.info("🔧 Creating Neo4j constraints...")
        create_graph_constraints()
        
        conn = get_snowflake_connection()
        if not conn:
            return False, 0, "Snowflake connection failed"
        
        cursor = conn.cursor()
        
        query = "SELECT * FROM claims_raw"
        if limit:
            query += f" LIMIT {limit}"
        
        log.info("📊 Reading claims from Snowflake", limit=limit or "ALL")
        cursor.execute(query)
        
        columns = [desc[0].lower() for desc in cursor.description]
        
        loaded = 0
        for row in cursor:
            claim_data = dict(zip(columns, row))
            
            # Convert to uppercase keys for compatibility
            claim_data = {k.upper(): v for k, v in claim_data.items()}
            
            if load_claim_to_graph(claim_data):
                loaded += 1
            
            if loaded % 10 == 0:
                log.info(f"⏳ Processed {loaded} claims...")
        
        cursor.close()
        conn.close()
        
        log.info(f"🎉 Graph built! {loaded} claims loaded to Neo4j")
        return True, loaded, None
        
    except Exception as e:
        log.error("❌ Graph build failed", error=str(e))
        return False, 0, str(e)

def quick_fraud_check(customer_id: str = None):
    """Quick fraud check for a customer"""
    neo4j = Neo4jConnection()
    if not neo4j.connect():
        return {"error": "Neo4j connection failed"}
    
    if customer_id:
        query = """
        MATCH (p:Person {customer_id: $customer_id})-[:FILED]->(c:Claim)
        WITH p, COUNT(c) as claims, SUM(toFloat(COALESCE(c.amount, '0'))) as total
        MATCH (p)-[:LIVES_AT]->(addr:Address)
        OPTIONAL MATCH (other:Person)-[:LIVES_AT]->(addr)
        WHERE other.customer_id <> p.customer_id
        RETURN p.name as name,
               claims,
               total,
               addr.line1 + ', ' + addr.city as address,
               COUNT(DISTINCT other) as others_at_address
        """
        
        result = neo4j.execute_query(query, {'customer_id': customer_id})
    else:
        query = """
        MATCH (p:Person)-[:FILED]->(c:Claim)
        WITH p, COUNT(c) as claims
        WHERE claims > 1
        RETURN COUNT(p) as people_with_multiple_claims,
               AVG(claims) as avg_claims_per_person,
               MAX(claims) as max_claims_by_person
        """
        result = neo4j.execute_query(query)
    
    neo4j.close()
    return result[0] if result else {}