"""
Load insurance_data_enriched.csv directly into Neo4j Aura
Matches the structure from your friend's standalone script
"""

import os
import pandas as pd
import logging
from dotenv import load_dotenv
from neo4j import GraphDatabase

# Configuration
CSV_PATH = "Data_Prep_Code/Data/insurance_data_enriched.csv"
EMPLOYEE_CSV = "Data_Prep_Code/Data/employee_data.csv"
VENDOR_CSV = "Data_Prep_Code/Data/vendor_data.csv"

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def load_reference_data():
    """Load agent and vendor reference data"""
    agents = {}
    vendors = {}
    
    try:
        df_agents = pd.read_csv(EMPLOYEE_CSV)
        for _, row in df_agents.iterrows():
            agents[row['AGENT_ID']] = row.to_dict()
        logger.info(f"Loaded {len(agents)} agents")
    except Exception as e:
        logger.warning(f"Could not load agents: {e}")
    
    try:
        df_vendors = pd.read_csv(VENDOR_CSV)
        for _, row in df_vendors.iterrows():
            vendors[row['VENDOR_ID']] = row.to_dict()
        logger.info(f"Loaded {len(vendors)} vendors")
    except Exception as e:
        logger.warning(f"Could not load vendors: {e}")
    
    return agents, vendors


def main():
    print("=" * 60)
    print("CSV to Neo4j Bulk Loader")
    print("=" * 60)
    
    # Load CSV
    logger.info(f"Reading CSV: {CSV_PATH}")
    df = pd.read_csv(CSV_PATH)
    logger.info(f"✅ Loaded {len(df)} rows")
    logger.info(f"Columns: {df.columns.tolist()[:10]}...")
    
    # Load reference data
    agents, vendors = load_reference_data()
    
    # Connect to Neo4j
    logger.info("Connecting to Neo4j Aura...")
    uri = os.getenv('NEO4J_URI')
    user = os.getenv('NEO4J_USER', 'neo4j')
    password = os.getenv('NEO4J_PASSWORD')
    
    driver = GraphDatabase.driver(uri, auth=(user, password))
    
    try:
        driver.verify_connectivity()
        logger.info("✅ Connected to Neo4j Aura")
    except Exception as e:
        logger.error(f"❌ Connection failed: {e}")
        return
    
    # Create constraints
    logger.info("Creating constraints...")
    with driver.session() as session:
        constraints = [
            "CREATE CONSTRAINT claim_id_unique IF NOT EXISTS FOR (c:Claim) REQUIRE c.claim_id IS UNIQUE",
            "CREATE CONSTRAINT person_id_unique IF NOT EXISTS FOR (p:Person) REQUIRE p.customer_id IS UNIQUE",
            "CREATE CONSTRAINT ssn_unique IF NOT EXISTS FOR (s:SSN) REQUIRE s.value IS UNIQUE",
            "CREATE CONSTRAINT agent_id_unique IF NOT EXISTS FOR (a:Agent) REQUIRE a.agent_id IS UNIQUE",
            "CREATE CONSTRAINT vendor_id_unique IF NOT EXISTS FOR (v:Vendor) REQUIRE v.vendor_id IS UNIQUE",
            "CREATE CONSTRAINT asset_unique IF NOT EXISTS FOR (a:Asset) REQUIRE a.value IS UNIQUE",
            "CREATE CONSTRAINT policy_unique IF NOT EXISTS FOR (p:Policy) REQUIRE p.policy_number IS UNIQUE"
        ]
        
        for c in constraints:
            try:
                session.run(c)
            except:
                pass
        logger.info("✅ Constraints created")
    
    # Load data (matching friend's script query structure)
    logger.info("Loading data...")
    
    query = """
    UNWIND $batch AS row
    
    // 1. Create Claim
    MERGE (c:Claim {claim_id: row.TRANSACTION_ID})
    SET c.date_of_loss = date(row.LOSS_DT),
        c.report_date = date(row.REPORT_DT),
        c.amount = toFloat(row.CLAIM_AMOUNT),
        c.type = row.INSURANCE_TYPE,
        c.status = row.CLAIM_STATUS
    
    // 2. Create Person
    MERGE (p:Person {customer_id: row.CUSTOMER_ID})
    SET p.name = row.CUSTOMER_NAME,
        p.age = toInteger(row.AGE),
        p.marital_status = row.MARITAL_STATUS
    MERGE (p)-[:FILED]->(c)
    
    // 3. Create SSN (if exists)
    FOREACH (_ IN CASE WHEN row.SSN IS NOT NULL THEN [1] ELSE [] END |
        MERGE (s:SSN {value: row.SSN})
        MERGE (p)-[:HAS_SSN]->(s)
    )
    
    // 4. Create Policy
    MERGE (pol:Policy {policy_number: row.POLICY_NUMBER})
    SET pol.start_date = date(row.POLICY_EFF_DT),
        pol.premium = toFloat(row.PREMIUM_AMOUNT)
    MERGE (c)-[:COVERED_BY]->(pol)
    MERGE (p)-[:OWNS_POLICY]->(pol)
    
    // 5. Create Agent (if exists)
    FOREACH (_ IN CASE WHEN row.AGENT_ID IS NOT NULL THEN [1] ELSE [] END |
        MERGE (a:Agent {agent_id: row.AGENT_ID})
        SET a.name = row.AGENT_NAME,
            a.city = row.AGENT_CITY,
            a.state = row.AGENT_STATE
        MERGE (c)-[:FACILITATED_BY]->(a)
    )
    
    // 6. Create Vendor (if exists)
    FOREACH (_ IN CASE WHEN row.VENDOR_ID IS NOT NULL THEN [1] ELSE [] END |
        MERGE (v:Vendor {vendor_id: row.VENDOR_ID})
        SET v.name = row.VENDOR_NAME,
            v.city = row.VENDOR_CITY,
            v.state = row.VENDOR_STATE
        MERGE (c)-[:REPAIRED_BY]->(v)
    )
    
    // 7. Track Agent-Vendor Collusion
    FOREACH (_ IN CASE WHEN row.AGENT_ID IS NOT NULL AND row.VENDOR_ID IS NOT NULL THEN [1] ELSE [] END |
        MERGE (a:Agent {agent_id: row.AGENT_ID})
        MERGE (v:Vendor {vendor_id: row.VENDOR_ID})
        MERGE (a)-[r:WORKS_WITH]->(v)
        SET r.count = coalesce(r.count, 0) + 1
    )
    
    // 8. Create Asset (VIN, IMEI, or Property)
    WITH row, c
    CALL {
        WITH row, c
        WITH row, c,
             CASE row.INSURANCE_TYPE
                WHEN 'Motor' THEN row.VIN
                WHEN 'Mobile' THEN row.IMEI
                WHEN 'Property' THEN row.PROPERTY_ADDRESS
                ELSE null
             END as asset_value,
             CASE row.INSURANCE_TYPE
                WHEN 'Motor' THEN 'Vehicle'
                WHEN 'Mobile' THEN 'Device'
                WHEN 'Property' THEN 'RealEstate'
                ELSE null
             END as asset_type
        
        WHERE asset_value IS NOT NULL
        MERGE (ast:Asset {value: asset_value})
        SET ast.type = asset_type
        MERGE (c)-[:INVOLVES]->(ast)
    }
    """
    
    # Process in batches
    batch_size = 1000
    total = len(df)
    success = 0
    
    for i in range(0, total, batch_size):
        batch_df = df.iloc[i:i+batch_size]
        batch = []
        
        for _, row in batch_df.iterrows():
            # Clean NaN values properly - convert to None
            record = {}
            for k, v in row.items():
                if pd.isna(v):
                    record[k] = None
                elif isinstance(v, float) and pd.isna(v):
                    record[k] = None
                else:
                    record[k] = v
            
            # Enrich with agent details
            agent_id = record.get('AGENT_ID')
            if agent_id and not pd.isna(agent_id) and agent_id in agents:
                record['AGENT_NAME'] = agents[agent_id].get('AGENT_NAME')
                record['AGENT_CITY'] = agents[agent_id].get('CITY')
                record['AGENT_STATE'] = agents[agent_id].get('STATE')
            
            # Enrich with vendor details
            vendor_id = record.get('VENDOR_ID')
            if vendor_id and not pd.isna(vendor_id) and vendor_id in vendors:
                record['VENDOR_NAME'] = vendors[vendor_id].get('VENDOR_NAME')
                record['VENDOR_CITY'] = vendors[vendor_id].get('CITY')
                record['VENDOR_STATE'] = vendors[vendor_id].get('STATE')
            
            batch.append(record)
        
        try:
            with driver.session() as session:
                session.run(query, {'batch': batch})
            
            success += len(batch)
            logger.info(f"Progress: {min(i+batch_size, total)}/{total} ({min(i+batch_size, total)/total*100:.1f}%)")
            
        except Exception as e:
            logger.error(f"Batch failed: {e}")
    
    # Final stats
    print("\n" + "=" * 60)
    print("LOADING COMPLETE")
    print("=" * 60)
    print(f"✅ Loaded: {success}/{total}")
    
    with driver.session() as session:
        stats = session.run("""
            MATCH (n)
            RETURN labels(n)[0] as label, count(n) as count
            ORDER BY count DESC
        """).data()
        
        print("\n📊 Graph Statistics:")
        for stat in stats:
            print(f"  {stat['label']}: {stat['count']}")
    
    driver.close()
    print("\n✅ Done! View at: https://console.neo4j.io")


if __name__ == "__main__":
    main()