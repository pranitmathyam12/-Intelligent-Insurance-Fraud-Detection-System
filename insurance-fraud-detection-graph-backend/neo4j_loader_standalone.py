import os
import pandas as pd
from neo4j import GraphDatabase
import logging

# --- CONFIGURATION ---
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "password"  # <--- UPDATE THIS
CSV_PATH = "Data_Prep_Code/insurance_data_enriched.csv"  # <--- UPDATE IF NEEDED

# --- LOGGING SETUP ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FraudGraphLoader:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def run_query(self, query, parameters=None):
        with self.driver.session() as session:
            result = session.run(query, parameters)
            return [record.data() for record in result]

    def clear_database(self):
        logger.warning("Clearing existing database...")
        self.run_query("MATCH (n) DETACH DELETE n")
        logger.info("Database cleared.")

    def create_constraints(self):
        logger.info("Creating constraints...")
        queries = [
            "CREATE CONSTRAINT claim_id_unique IF NOT EXISTS FOR (c:Claim) REQUIRE c.claim_id IS UNIQUE",
            "CREATE CONSTRAINT person_id_unique IF NOT EXISTS FOR (p:Person) REQUIRE p.customer_id IS UNIQUE",
            "CREATE CONSTRAINT ssn_unique IF NOT EXISTS FOR (s:SSN) REQUIRE s.value IS UNIQUE",
            "CREATE CONSTRAINT agent_id_unique IF NOT EXISTS FOR (a:Agent) REQUIRE a.agent_id IS UNIQUE",
            "CREATE CONSTRAINT vendor_id_unique IF NOT EXISTS FOR (v:Vendor) REQUIRE v.vendor_id IS UNIQUE",
            "CREATE CONSTRAINT asset_unique IF NOT EXISTS FOR (a:Asset) REQUIRE a.value IS UNIQUE",
            "CREATE CONSTRAINT policy_unique IF NOT EXISTS FOR (p:Policy) REQUIRE p.policy_number IS UNIQUE",
            "CREATE INDEX person_name_index IF NOT EXISTS FOR (p:Person) ON (p.name)"
        ]
        for q in queries:
            self.run_query(q)
        logger.info("Constraints created.")

    def load_reference_data(self):
        logger.info("Loading reference data (Agents & Vendors)...")
        self.agents = {}
        self.vendors = {}
        
        try:
            # Load Agents
            df_agents = pd.read_csv("Data_Prep_Code/Data/employee_data.csv")
            for _, row in df_agents.iterrows():
                self.agents[row['AGENT_ID']] = row.to_dict()
                
            # Load Vendors
            df_vendors = pd.read_csv("Data_Prep_Code/Data/vendor_data.csv")
            for _, row in df_vendors.iterrows():
                self.vendors[row['VENDOR_ID']] = row.to_dict()
                
            logger.info(f"Loaded {len(self.agents)} agents and {len(self.vendors)} vendors.")
        except Exception as e:
            logger.warning(f"Could not load reference data: {e}")

    def load_data(self, csv_path):
        self.load_reference_data()
        
        logger.info(f"Loading data from {csv_path}...")
        df = pd.read_csv(csv_path)
        total_rows = len(df)
        
        # Debug: Print column names from the first batch
        if total_rows > 0:
            logger.info(f"CSV Columns: {df.columns.tolist()}")

        # Pre-process batch to inject Agent/Vendor details
        # We do this in Python to keep Cypher simple
        
        query = """
        UNWIND $batch AS row
        
        // 1. Create Central Claim Node
        MERGE (c:Claim {claim_id: row.TRANSACTION_ID})
        SET c.date_of_loss = date(row.LOSS_DT),
            c.report_date = date(row.REPORT_DT),
            c.amount = toFloat(row.CLAIM_AMOUNT),
            c.type = row.INSURANCE_TYPE,
            c.status = row.CLAIM_STATUS

        // 2. Create Person (Policyholder)
        MERGE (p:Person {customer_id: row.CUSTOMER_ID})
        SET p.name = row.CUSTOMER_NAME,
            p.age = toInteger(row.AGE),
            p.marital_status = row.MARITAL_STATUS
        MERGE (p)-[:FILED]->(c)

        // 3. Create SSN Node
        MERGE (s:SSN {value: row.SSN})
        MERGE (p)-[:HAS_SSN]->(s)

        // 4. Create Policy Node
        MERGE (pol:Policy {policy_number: row.POLICY_NUMBER})
        SET pol.start_date = date(row.POLICY_EFF_DT),
            pol.premium = toFloat(row.PREMIUM_AMOUNT)
        MERGE (c)-[:COVERED_BY]->(pol)
        MERGE (p)-[:OWNS_POLICY]->(pol)

        // 5. Create Agent Node (Conditional)
        FOREACH (_ IN CASE WHEN row.AGENT_ID IS NOT NULL THEN [1] ELSE [] END |
            MERGE (a:Agent {agent_id: row.AGENT_ID})
            SET a.name = row.AGENT_NAME,
                a.city = row.AGENT_CITY,
                a.state = row.AGENT_STATE
            MERGE (c)-[:FACILITATED_BY]->(a)
        )

        // 6. Create Vendor Node (Conditional)
        FOREACH (_ IN CASE WHEN row.VENDOR_ID IS NOT NULL THEN [1] ELSE [] END |
            MERGE (v:Vendor {vendor_id: row.VENDOR_ID})
            SET v.name = row.VENDOR_NAME,
                v.city = row.VENDOR_CITY,
                v.state = row.VENDOR_STATE
            MERGE (c)-[:REPAIRED_BY]->(v)
        )

        // 7. Create "Collusion" Edge (Conditional)
        FOREACH (_ IN CASE WHEN row.AGENT_ID IS NOT NULL AND row.VENDOR_ID IS NOT NULL THEN [1] ELSE [] END |
            MERGE (a:Agent {agent_id: row.AGENT_ID})
            MERGE (v:Vendor {vendor_id: row.VENDOR_ID})
            MERGE (a)-[r:WORKS_WITH]->(v)
            SET r.count = coalesce(r.count, 0) + 1
        )

        // 8. Create Asset Node (Conditional)
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
        
        batch_size = 1000
        for i in range(0, total_rows, batch_size):
            batch = df.iloc[i:i+batch_size].to_dict('records')
            cleaned_batch = []
            for record in batch:
                if pd.isna(record.get('TRANSACTION_ID')):
                    continue
                
                # Enrich with Agent details
                agent_id = record.get('AGENT_ID')
                if not pd.isna(agent_id) and agent_id in self.agents:
                    adata = self.agents[agent_id]
                    record['AGENT_NAME'] = adata.get('AGENT_NAME')
                    record['AGENT_CITY'] = adata.get('CITY')
                    record['AGENT_STATE'] = adata.get('STATE')
                
                # Enrich with Vendor details
                vendor_id = record.get('VENDOR_ID')
                if not pd.isna(vendor_id) and vendor_id in self.vendors:
                    vdata = self.vendors[vendor_id]
                    record['VENDOR_NAME'] = vdata.get('VENDOR_NAME')
                    record['VENDOR_CITY'] = vdata.get('CITY')
                    record['VENDOR_STATE'] = vdata.get('STATE')

                # Handle NaNs
                for k, v in record.items():
                    if pd.isna(v):
                        record[k] = None
                cleaned_batch.append(record)
            
            if not cleaned_batch:
                continue

            self.run_query(query, {"batch": cleaned_batch})
            logger.info(f"Processed rows {i} to {min(i+batch_size, total_rows)}")

        logger.info("Data ingestion complete.")
        
        # Verify counts
        counts = self.run_query("MATCH (n) RETURN labels(n) as Label, count(n) as Count")
        logger.info(f"Node Counts: {counts}")

    def run_fraud_checks(self):
        logger.info("Running fraud detection queries...")
        
        # 1. Shared PII
        logger.info("--- Scenario 1: Shared PII Rings ---")
        q1 = """
        MATCH (p1:Person)-[:HAS_SSN]->(s:SSN)<-[:HAS_SSN]-(p2:Person)
        WHERE p1.customer_id < p2.customer_id
        RETURN s.value as Shared_SSN, collect(distinct p1.name) as Fraudsters, count(distinct p1) as Ring_Size
        ORDER BY Ring_Size DESC LIMIT 5
        """
        results = self.run_query(q1)
        for r in results:
            logger.info(r)

        # 2. Collusive Provider Rings
        logger.info("--- Scenario 2: Collusive Provider Rings ---")
        q2 = """
        MATCH (a:Agent)-[r:WORKS_WITH]->(v:Vendor)
        WHERE r.count > 10
        RETURN a.name as Agent, v.name as Vendor, r.count as Shared_Claims
        ORDER BY Shared_Claims DESC LIMIT 5
        """
        results = self.run_query(q2)
        for r in results:
            logger.info(r)

        # 3. Asset Recycling
        logger.info("--- Scenario 3: Asset Recycling ---")
        q3 = """
        MATCH (c:Claim)-[:INVOLVES]->(a:Asset)
        WITH a, count(c) as Claim_Count
        WHERE Claim_Count > 1
        RETURN a.type as Asset_Type, a.value as Asset_ID, Claim_Count
        ORDER BY Claim_Count DESC LIMIT 5
        """
        results = self.run_query(q3)
        for r in results:
            logger.info(r)

        # 4. Velocity Fraud
        logger.info("--- Scenario 4: Velocity Fraud ---")
        q4 = """
        MATCH (p:Person)-[:FILED]->(c:Claim)
        WITH p, count(c) as Claim_Count
        WHERE Claim_Count >= 4
        RETURN p.name, Claim_Count
        ORDER BY Claim_Count DESC LIMIT 5
        """
        results = self.run_query(q4)
        for r in results:
            logger.info(r)

        # 5. Double Dipping
        logger.info("--- Scenario 5: Double Dipping ---")
        q5 = """
        MATCH (c1:Claim), (c2:Claim)
        WHERE c1.claim_id < c2.claim_id
          AND c1.amount = c2.amount
          AND c1.date_of_loss = c2.date_of_loss
          AND c1.type = c2.type
        RETURN c1.claim_id, c2.claim_id, c1.amount
        LIMIT 5
        """
        results = self.run_query(q5)
        for r in results:
            logger.info(r)

if __name__ == "__main__":
    loader = FraudGraphLoader(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    try:
        loader.clear_database() # Optional: Start fresh
        loader.create_constraints()
        loader.load_data(CSV_PATH)
        loader.run_fraud_checks()
    except Exception as e:
        logger.error(f"An error occurred: {e}")
    finally:
        loader.close()
