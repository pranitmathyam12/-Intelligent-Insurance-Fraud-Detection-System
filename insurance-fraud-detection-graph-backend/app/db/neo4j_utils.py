"""
Enhanced Neo4j utilities with comprehensive fraud detection
Combines existing functionality with advanced fraud scenarios
"""

import os
import logging
import time
from neo4j import GraphDatabase
from typing import List, Dict, Any, Optional

# Use standard logging instead of structlog for Neo4j module
logger = logging.getLogger(__name__)


class Neo4jConnection:
    """Neo4j database connection handler"""
    
    def __init__(self):
        self.uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
        self.user = os.getenv('NEO4J_USER', 'neo4j')
        self.password = os.getenv('NEO4J_PASSWORD', 'password')
        self.database = os.getenv('NEO4J_DATABASE', 'neo4j')
        self.driver = None
    
    def connect(self):
        """Establish connection to Neo4j"""
        try:
            self.driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password)
            )
            self.driver.verify_connectivity()
            # logger.info(f"✅ Connected to Neo4j! URI: {self.uri}")
            return True
        except Exception as e:
            logger.error(f"❌ Neo4j connection failed: {e}")
            return False
    
    def close(self):
        """Close connection"""
        if self.driver:
            self.driver.close()
    
    def execute_query(self, query: str, parameters: dict = None):
        """Execute a Cypher query"""
        if not self.driver:
            if not self.connect():
                return None
        
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run(query, parameters or {})
                return [record.data() for record in result]
        except Exception as e:
            logger.error(f"❌ Query failed: {e}")
            self.driver = None
            return None


def create_graph_constraints():
    """Create constraints and indexes for the graph - ENHANCED with SSN and Asset nodes"""
    neo4j = Neo4jConnection()
    if not neo4j.connect():
        return False
    
    constraints = [
        # Original constraints
        "CREATE CONSTRAINT person_id IF NOT EXISTS FOR (p:Person) REQUIRE p.customer_id IS UNIQUE",
        "CREATE CONSTRAINT policy_number IF NOT EXISTS FOR (pol:Policy) REQUIRE pol.policy_number IS UNIQUE",
        "CREATE CONSTRAINT claim_id IF NOT EXISTS FOR (c:Claim) REQUIRE c.transaction_id IS UNIQUE",
        "CREATE CONSTRAINT agent_id IF NOT EXISTS FOR (a:Agent) REQUIRE a.agent_id IS UNIQUE",
        "CREATE CONSTRAINT vendor_id IF NOT EXISTS FOR (v:Vendor) REQUIRE v.vendor_id IS UNIQUE",
        "CREATE CONSTRAINT address_key IF NOT EXISTS FOR (addr:Address) REQUIRE addr.address_key IS UNIQUE",
        
        # NEW: Enhanced constraints for fraud detection
        "CREATE CONSTRAINT ssn_unique IF NOT EXISTS FOR (s:SSN) REQUIRE s.value IS UNIQUE",
        "CREATE CONSTRAINT asset_unique IF NOT EXISTS FOR (a:Asset) REQUIRE a.value IS UNIQUE",
        
        # Indexes for performance
        "CREATE INDEX person_name_idx IF NOT EXISTS FOR (p:Person) ON (p.name)",
        "CREATE INDEX claim_amount_idx IF NOT EXISTS FOR (c:Claim) ON (c.amount)",
        "CREATE INDEX claim_date_idx IF NOT EXISTS FOR (c:Claim) ON (c.loss_date)"
    ]
    
    for constraint in constraints:
        try:
            neo4j.execute_query(constraint)
            logger.info(f"✅ Constraint created: {constraint[:70]}")
        except Exception as e:
            logger.warning(f"Constraint already exists or failed: {e}")
    
    neo4j.close()
    return True


def load_claim_to_graph(claim_data: Dict[str, Any]):
    """
    ENHANCED: Load a single claim record into Neo4j graph with advanced fraud detection support
    """
    start_time = time.time()
    neo4j = Neo4jConnection()
    if not neo4j.connect():
        logger.warning("⚠️ Skipping Neo4j save - no connection")
        return False
    
    try:
        # Enhanced Cypher query with SSN, Asset, and Collusion tracking
        query = """
        // 1. Create Person node
        MERGE (person:Person {customer_id: $customer_id})
        SET person.name = $customer_name,
            person.age = $age,
            person.marital_status = $marital_status,
            person.employment_status = $employment_status,
            person.education = $education,
            person.social_class = $social_class,
            person.family_members = $family_members
        
        // 2. Create SSN node (separate for shared PII detection) - ONLY if SSN exists
        WITH person
        FOREACH (_ IN CASE WHEN $ssn IS NOT NULL THEN [1] ELSE [] END |
            MERGE (ssn:SSN {value: $ssn})
            MERGE (person)-[:HAS_SSN]->(ssn)
        )
        
        // 3. Create Address node
        MERGE (addr:Address {address_key: $address_key})
        SET addr.line1 = $address_line1,
            addr.line2 = $address_line2,
            addr.city = $city,
            addr.state = $state,
            addr.postal_code = $postal_code
        MERGE (person)-[:LIVES_AT]->(addr)
        
        // 4. Create Policy node
        MERGE (policy:Policy {policy_number: $policy_number})
        SET policy.type = $insurance_type,
            policy.premium = $premium_amount,
            policy.effective_date = $policy_eff_dt,
            policy.risk_segment = $risk_segment,
            policy.house_type = $house_type
        MERGE (person)-[:OWNS_POLICY]->(policy)
        
        // 5. Create Claim node
        MERGE (claim:Claim {transaction_id: $transaction_id})
        SET claim.amount = $claim_amount,
            claim.loss_date = $loss_dt,
            claim.report_date = $report_dt,
            claim.severity = $incident_severity,
            claim.status = $claim_status,
            claim.incident_city = $incident_city,
            claim.incident_state = $incident_state,
            claim.incident_hour = $incident_hour,
            claim.authority_contacted = $authority_contacted,
            claim.any_injury = $any_injury,
            claim.police_report = $police_report,
            claim.type = $insurance_type
        MERGE (person)-[:FILED]->(claim)
        MERGE (claim)-[:COVERED_BY]->(policy)
        
        // 6. Create Agent node (if exists)
        WITH person, addr, policy, claim
        FOREACH (agent_id IN CASE WHEN $agent_id IS NOT NULL THEN [$agent_id] ELSE [] END |
            MERGE (agent:Agent {agent_id: agent_id})
            MERGE (agent)-[:HANDLED]->(claim)
        )
        
        // 7. Create Vendor node (if exists)
        WITH person, addr, policy, claim
        FOREACH (vendor_id IN CASE WHEN $vendor_id IS NOT NULL THEN [$vendor_id] ELSE [] END |
            MERGE (vendor:Vendor {vendor_id: vendor_id})
            MERGE (claim)-[:REPAIRED_BY]->(vendor)
        )
        
        // 8. NEW: Track Agent-Vendor Collusion
        WITH person, addr, policy, claim
        FOREACH (_ IN CASE WHEN $agent_id IS NOT NULL AND $vendor_id IS NOT NULL THEN [1] ELSE [] END |
            MERGE (agent:Agent {agent_id: $agent_id})
            MERGE (vendor:Vendor {vendor_id: $vendor_id})
            MERGE (agent)-[r:WORKS_WITH]->(vendor)
            SET r.count = coalesce(r.count, 0) + 1
        )
        
        // 9. NEW: Create Asset node (conditional based on insurance type)
        WITH person, addr, policy, claim
        CALL {
            WITH claim
            WITH claim,
                 CASE $insurance_type
                    WHEN 'Motor' THEN $vin
                    WHEN 'Auto' THEN $vin
                    WHEN 'Mobile' THEN $imei
                    WHEN 'Property' THEN $property_address
                    ELSE null
                 END as asset_value,
                 CASE $insurance_type
                    WHEN 'Motor' THEN 'Vehicle'
                    WHEN 'Auto' THEN 'Vehicle'
                    WHEN 'Mobile' THEN 'Device'
                    WHEN 'Property' THEN 'RealEstate'
                    ELSE null
                 END as asset_type
            
            WHERE asset_value IS NOT NULL
            MERGE (asset:Asset {value: asset_value})
            SET asset.type = asset_type
            MERGE (claim)-[:INVOLVES]->(asset)
        }
        
        RETURN person, claim, policy
        """
        
        # Ensure customer_id is not null to prevent Neo4j SemanticError
        cust_id = claim_data.get('CUSTOMER_ID') or claim_data.get('customer_id')
        txn_id = claim_data.get('TRANSACTION_ID') or claim_data.get('transaction_id')
        
        # STRICT VALIDATION: Fail if customer_id is missing
        if not cust_id:
            error_msg = f"❌ Missing customer_id for transaction {txn_id}. Cannot load to graph."
            logger.error(error_msg)
            raise ValueError(error_msg)

        # Prepare parameters (enhanced with asset info)
        params = {
            # Person info
            'customer_id': cust_id,
            'customer_name': claim_data.get('CUSTOMER_NAME') or claim_data.get('customer_name') or 'Unknown',
            'ssn': claim_data.get('SSN') or claim_data.get('ssn_masked') or claim_data.get('ssn'),
            'age': claim_data.get('AGE') or claim_data.get('age'),
            'marital_status': claim_data.get('MARITAL_STATUS') or claim_data.get('marital'),
            'employment_status': claim_data.get('EMPLOYMENT_STATUS') or claim_data.get('employed'),
            'education': claim_data.get('CUSTOMER_EDUCATION_LEVEL') or claim_data.get('education'),
            'social_class': claim_data.get('SOCIAL_CLASS') or claim_data.get('social_class'),
            'family_members': claim_data.get('NO_OF_FAMILY_MEMBERS') or claim_data.get('family_members'),
            
            # Address info
            'address_key': f"{claim_data.get('ADDRESS_LINE1', '') or claim_data.get('address_line1', '')}_{claim_data.get('CITY', '') or claim_data.get('city', '')}_{claim_data.get('POSTAL_CODE', '') or claim_data.get('postal_code', '')}",
            'address_line1': claim_data.get('ADDRESS_LINE1') or claim_data.get('address_line1'),
            'address_line2': claim_data.get('ADDRESS_LINE2') or claim_data.get('address_line2'),
            'city': claim_data.get('CITY') or claim_data.get('city'),
            'state': claim_data.get('STATE') or claim_data.get('state'),
            'postal_code': claim_data.get('POSTAL_CODE') or claim_data.get('postal_code'),
            
            # Policy info
            'policy_number': claim_data.get('POLICY_NUMBER') or claim_data.get('policy_number'),
            'insurance_type': claim_data.get('INSURANCE_TYPE') or claim_data.get('insurance_type'),
            'premium_amount': claim_data.get('PREMIUM_AMOUNT') or claim_data.get('premium_amount'),
            'policy_eff_dt': claim_data.get('POLICY_EFF_DT') or claim_data.get('policy_effective_date'),
            'risk_segment': claim_data.get('RISK_SEGMENTATION') or claim_data.get('risk_segment'),
            'house_type': claim_data.get('HOUSE_TYPE') or claim_data.get('house_type'),
            
            # Claim info
            'transaction_id': txn_id,
            'claim_amount': claim_data.get('CLAIM_AMOUNT') or claim_data.get('claim_amount'),
            'loss_dt': claim_data.get('LOSS_DT') or claim_data.get('loss_date'),
            'report_dt': claim_data.get('REPORT_DT') or claim_data.get('report_date'),
            'incident_severity': claim_data.get('INCIDENT_SEVERITY') or claim_data.get('severity'),
            'claim_status': claim_data.get('CLAIM_STATUS', 'PENDING'),
            'incident_city': claim_data.get('INCIDENT_CITY') or claim_data.get('incident_city'),
            'incident_state': claim_data.get('INCIDENT_STATE') or claim_data.get('incident_state'),
            'incident_hour': claim_data.get('INCIDENT_HOUR_OF_THE_DAY') or claim_data.get('incident_hour'),
            'authority_contacted': claim_data.get('AUTHORITY_CONTACTED') or claim_data.get('authority_contacted'),
            'any_injury': claim_data.get('ANY_INJURY') or claim_data.get('any_injury'),
            'police_report': claim_data.get('POLICE_REPORT_AVAILABLE') or claim_data.get('police_report'),
            
            # Agent & Vendor
            'agent_id': claim_data.get('AGENT_ID') or claim_data.get('agent_id'),
            'vendor_id': claim_data.get('VENDOR_ID') or claim_data.get('vendor_id'),
            
            # NEW: Asset info for fraud detection
            'vin': claim_data.get('VIN') or claim_data.get('vin'),
            'imei': claim_data.get('IMEI') or claim_data.get('imei'),
            'property_address': claim_data.get('PROPERTY_ADDRESS') or claim_data.get('property_address') or claim_data.get('ADDRESS_LINE1')
        }
        
        result = neo4j.execute_query(query, params)
        duration = (time.time() - start_time) * 1000
        logger.info(f"🕸️ Loaded to Neo4j graph! Transaction: {params['transaction_id']} in {duration:.2f}ms")
        neo4j.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to load to Neo4j: {e}")
        neo4j.close()
        # Propagate error instead of returning False
        raise e


# ============================================================================
# ENHANCED FRAUD DETECTION - All 5 Scenarios
# ============================================================================

def detect_fraud_patterns():
    """
    ENHANCED: Run comprehensive fraud detection queries (all 5 scenarios)
    Returns list of suspicious patterns found
    """
    neo4j = Neo4jConnection()
    if not neo4j.connect():
        return []
    
    patterns = []
    
    # Scenario 1: SHARED PII RINGS (Same SSN used by multiple people)
    logger.info("Running Scenario 1: Shared PII Rings...")
    query1 = """
    MATCH (p1:Person)-[:HAS_SSN]->(s:SSN)<-[:HAS_SSN]-(p2:Person)
    WHERE p1.customer_id < p2.customer_id
    WITH s, collect(DISTINCT p1.name) + collect(DISTINCT p2.name) as names, count(DISTINCT p1) + count(DISTINCT p2) as ring_size
    WHERE ring_size > 1
    RETURN s.value as shared_ssn,
           names as fraudsters,
           ring_size
    ORDER BY ring_size DESC
    LIMIT 10
    """
    results = neo4j.execute_query(query1)
    if results and len(results) > 0:
        patterns.append({
            'pattern': 'Shared PII Rings (Same SSN)',
            'risk': 'CRITICAL',
            'description': 'Multiple people using the same SSN (identity theft)',
            'cases': results
        })
    
    # Scenario 2: COLLUSIVE PROVIDER RINGS (Agent-Vendor collusion)
    logger.info("Running Scenario 2: Collusive Provider Rings...")
    query2 = """
    MATCH (a:Agent)-[r:WORKS_WITH]->(v:Vendor)
    WHERE r.count > 5
    RETURN a.agent_id as agent_id,
           v.vendor_id as vendor_id,
           r.count as shared_claims
    ORDER BY shared_claims DESC
    LIMIT 10
    """
    results = neo4j.execute_query(query2)
    if results and len(results) > 0:
        patterns.append({
            'pattern': 'Collusive Provider Rings',
            'risk': 'HIGH',
            'description': 'Agent and Vendor working together on many claims',
            'cases': results
        })
    
    # Scenario 3: ASSET RECYCLING (Same VIN/IMEI claimed multiple times)
    logger.info("Running Scenario 3: Asset Recycling...")
    query3 = """
    MATCH (c:Claim)-[:INVOLVES]->(a:Asset)
    WITH a, count(c) as claim_count, collect(c.transaction_id) as claim_ids
    WHERE claim_count > 1
    RETURN a.type as asset_type,
           a.value as asset_id,
           claim_count,
           claim_ids
    ORDER BY claim_count DESC
    LIMIT 10
    """
    results = neo4j.execute_query(query3)
    if results and len(results) > 0:
        patterns.append({
            'pattern': 'Asset Recycling',
            'risk': 'HIGH',
            'description': 'Same asset (VIN/IMEI) claimed multiple times',
            'cases': results
        })
    
    # Scenario 4: VELOCITY FRAUD (Multiple rapid claims by same person)
    logger.info("Running Scenario 4: Velocity Fraud...")
    query4 = """
    MATCH (p:Person)-[:FILED]->(c:Claim)
    WITH p, COUNT(c) as claim_count, SUM(toFloat(c.amount)) as total_claimed, collect(c.transaction_id) as claims
    WHERE claim_count >= 3
    RETURN p.customer_id as customer_id,
           p.name as customer_name,
           claim_count,
           total_claimed,
           claims
    ORDER BY claim_count DESC
    LIMIT 10
    """
    results = neo4j.execute_query(query4)
    if results and len(results) > 0:
        patterns.append({
            'pattern': 'Velocity Fraud',
            'risk': 'HIGH',
            'description': 'Person filed multiple claims rapidly',
            'cases': results
        })
    
    # Scenario 5: DOUBLE DIPPING (Duplicate claims)
    logger.info("Running Scenario 5: Double Dipping...")
    query5 = """
    MATCH (c1:Claim), (c2:Claim)
    WHERE c1.transaction_id < c2.transaction_id
      AND c1.amount = c2.amount
      AND c1.loss_date = c2.loss_date
      AND c1.type = c2.type
    RETURN c1.transaction_id as claim1,
           c2.transaction_id as claim2,
           c1.amount as amount,
           c1.type as type
    LIMIT 5
    """
    results = neo4j.execute_query(query5)
    if results and len(results) > 0:
        patterns.append({
            'pattern': 'Double Dipping',
            'risk': 'HIGH',
            'description': 'Duplicate or nearly identical claims',
            'cases': results
        })
    
    # BONUS: Multiple people at same address (original pattern - still useful)
    logger.info("Running Bonus: Multiple Claimants Same Address...")
    query_bonus = """
    MATCH (p:Person)-[:LIVES_AT]->(addr:Address)
    MATCH (p)-[:FILED]->(c:Claim)
    WITH addr, COUNT(DISTINCT p) as person_count, COLLECT(DISTINCT p.name) as people, COUNT(c) as claim_count
    WHERE person_count > 1 AND claim_count > 2
    RETURN addr.line1 as address,
           addr.city as city,
           addr.state as state,
           person_count,
           claim_count,
           people
    ORDER BY claim_count DESC
    LIMIT 10
    """
    results = neo4j.execute_query(query_bonus)
    if results and len(results) > 0:
        patterns.append({
            'pattern': 'Multiple Claimants at Same Address',
            'risk': 'MEDIUM',
            'description': 'Multiple people from same address filing claims',
            'cases': results
        })
    
    neo4j.close()
    logger.info(f"✅ Fraud detection complete! Found {len(patterns)} suspicious patterns")
    return patterns


def check_claim_fraud_risk(claim_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    ENHANCED: Real-time fraud check for a single claim
    Returns fraud assessment with score, recommendation, AND graph visualization data
    """
    start_time = time.time()
    neo4j = Neo4jConnection()
    if not neo4j.connect():
        raise Exception("Neo4j not available")
    
    flags = []
    fraud_score = 0
    graph_nodes = []
    graph_edges = []
    
    # Ensure customer_id is present (use fallback if needed, same logic as load)
    customer_id = claim_data.get('customer_id') or claim_data.get('CUSTOMER_ID')
    transaction_id = claim_data.get('transaction_id') or claim_data.get('TRANSACTION_ID')
    
    # STRICT VALIDATION: Fail if customer_id is missing
    if not customer_id:
        error_msg = f"❌ Missing customer_id for transaction {transaction_id}. Cannot check fraud."
        logger.error(error_msg)
        raise ValueError(error_msg)
        
    ssn = claim_data.get('ssn_masked') or claim_data.get('ssn') or claim_data.get('SSN')
    agent_id = claim_data.get('agent_id') or claim_data.get('AGENT_ID')
    vendor_id = claim_data.get('vendor_id') or claim_data.get('VENDOR_ID')
    
    try:
        # Helper to add nodes/edges to graph response
        def add_graph_element(nodes, edges):
            for n in nodes:
                if n not in graph_nodes:
                    graph_nodes.append(n)
            for e in edges:
                if e not in graph_edges:
                    graph_edges.append(e)

        # 0. Always fetch the current claim and person for the graph
        query_base = """
        MATCH (c:Claim {transaction_id: $tid})
        MATCH (p:Person)-[:FILED]->(c)
        RETURN p, c
        """
        base_res = neo4j.execute_query(query_base, {'tid': transaction_id})
        if base_res:
            p_node = {'id': base_res[0]['p']['customer_id'], 'label': 'Person', 'data': base_res[0]['p']}
            c_node = {'id': base_res[0]['c']['transaction_id'], 'label': 'Claim', 'data': base_res[0]['c']}
            add_graph_element([p_node, c_node], [{'source': p_node['id'], 'target': c_node['id'], 'label': 'FILED'}])

        # Check 1: Velocity Fraud
        query_velocity = """
        MATCH (p:Person {customer_id: $customer_id})-[:FILED]->(c:Claim)
        RETURN count(c) as claim_count, collect(c.transaction_id) as claim_ids
        """
        result = neo4j.execute_query(query_velocity, {'customer_id': customer_id})
        if result and result[0]['claim_count'] > 2:
            flags.append({
                'rule': 'VELOCITY_FRAUD',
                'severity': 'HIGH',
                'message': f"Customer has {result[0]['claim_count']} claims on record"
            })
            fraud_score += 25
            # Add other claims to graph
            for cid in result[0]['claim_ids']:
                if cid != transaction_id:
                     add_graph_element([{'id': cid, 'label': 'Claim'}], [{'source': customer_id, 'target': cid, 'label': 'FILED'}])
        
        # Check 2: Shared SSN
        query_ssn = """
        MATCH (p:Person)-[:HAS_SSN]->(s:SSN {value: $ssn})
        RETURN count(DISTINCT p) as person_count, collect(DISTINCT p.customer_id) as other_customers
        """
        result = neo4j.execute_query(query_ssn, {'ssn': ssn})
        if result and result[0]['person_count'] > 1:
            flags.append({
                'rule': 'SHARED_PII',
                'severity': 'CRITICAL',
                'message': f"SSN shared by {result[0]['person_count']} people"
            })
            fraud_score += 40
            # Add SSN and other people to graph
            ssn_node = {'id': ssn, 'label': 'SSN'}
            add_graph_element([ssn_node], [{'source': customer_id, 'target': ssn, 'label': 'HAS_SSN'}])
            for other_id in result[0]['other_customers']:
                if other_id != customer_id:
                    other_node = {'id': other_id, 'label': 'Person'}
                    add_graph_element([other_node], [{'source': other_id, 'target': ssn, 'label': 'HAS_SSN'}])
        
        # Check 3: Agent-Vendor Collusion
        if agent_id and vendor_id:
            query_collusion = """
            MATCH (a:Agent {agent_id: $agent_id})-[r:WORKS_WITH]->(v:Vendor {vendor_id: $vendor_id})
            RETURN r.count as shared_claims
            """
            result = neo4j.execute_query(query_collusion, {'agent_id': agent_id, 'vendor_id': vendor_id})
            if result and result[0].get('shared_claims', 0) > 10:
                flags.append({
                    'rule': 'COLLUSION',
                    'severity': 'HIGH',
                    'message': f"Agent-Vendor worked on {result[0]['shared_claims']} claims together"
                })
                fraud_score += 25
                # Add Agent/Vendor to graph
                a_node = {'id': agent_id, 'label': 'Agent'}
                v_node = {'id': vendor_id, 'label': 'Vendor'}
                add_graph_element([a_node, v_node], [{'source': agent_id, 'target': vendor_id, 'label': 'WORKS_WITH', 'count': result[0]['shared_claims']}])
        
        # Check 4: High Value
        claim_amount = float(claim_data.get('claim_amount', 0) or claim_data.get('CLAIM_AMOUNT', 0))
        if claim_amount > 50000:
            flags.append({
                'rule': 'HIGH_VALUE',
                'severity': 'MEDIUM',
                'message': f"High value claim: ${claim_amount:,.2f}"
            })
            fraud_score += 15

        # Check 5: Asset Recycling (Real-time)
        # Determine asset value based on type
        asset_value = None
        insurance_type = claim_data.get('insurance_type') or claim_data.get('INSURANCE_TYPE')
        if insurance_type in ['Motor', 'Auto']:
            asset_value = claim_data.get('vin') or claim_data.get('VIN')
        elif insurance_type == 'Mobile':
            asset_value = claim_data.get('imei') or claim_data.get('IMEI')
        elif insurance_type == 'Property':
            asset_value = claim_data.get('property_address') or claim_data.get('PROPERTY_ADDRESS') or claim_data.get('address_line1') or claim_data.get('ADDRESS_LINE1')

        if asset_value:
            logger.info(f"🔍 Checking Asset Recycling for {insurance_type} asset: {asset_value}")
            # Check if this asset is already involved in OTHER claims
            # We exclude the current transaction_id to see if it was used BEFORE
            query_asset = """
            MATCH (c:Claim)-[:INVOLVES]->(a:Asset {value: $asset_value})
            WHERE c.transaction_id <> $current_id
            RETURN count(c) as claim_count, collect(c.transaction_id) as claim_ids
            """
            result = neo4j.execute_query(query_asset, {'asset_value': asset_value, 'current_id': transaction_id})
            logger.info(f"🔍 Asset Recycling Result: {result}")
            
            if result and result[0]['claim_count'] > 0:
                flags.append({
                    'rule': 'ASSET_RECYCLING',
                    'severity': 'HIGH',
                    'message': f"Asset {asset_value} used in {result[0]['claim_count']} previous claims: {result[0]['claim_ids']}"
                })
                fraud_score += 30
                # Add asset and other claims to graph
                asset_node = {'id': asset_value, 'label': 'Asset'}
                add_graph_element([asset_node], [{'source': transaction_id, 'target': asset_value, 'label': 'INVOLVES'}])
                for cid in result[0]['claim_ids']:
                    add_graph_element([{'id': cid, 'label': 'Claim'}], [{'source': cid, 'target': asset_value, 'label': 'INVOLVES'}])

        # Check 6: Double Dipping (Real-time)
        loss_date = claim_data.get('loss_date') or claim_data.get('LOSS_DT')
        if loss_date and claim_amount > 0:
            query_double = """
            MATCH (c:Claim)
            WHERE c.amount = $amount 
              AND c.loss_date = $loss_date 
              AND c.type = $type
              AND c.transaction_id <> $current_id
            RETURN count(c) as match_count, collect(c.transaction_id) as claim_ids
            """
            result = neo4j.execute_query(query_double, {
                'amount': claim_amount, 
                'loss_date': loss_date, 
                'type': insurance_type,
                'current_id': transaction_id
            })
            if result and result[0]['match_count'] > 0:
                flags.append({
                    'rule': 'DOUBLE_DIPPING',
                    'severity': 'HIGH',
                    'message': f"Potential duplicate claim found: {result[0]['claim_ids'][0]}"
                })
                fraud_score += 45
                # Add duplicate claims to graph
                for cid in result[0]['claim_ids']:
                     add_graph_element([{'id': cid, 'label': 'Claim'}], []) # Just add node, edge might be inferred or no direct link

        
        fraud_score = min(fraud_score, 100)
        
        neo4j.close()
        
        duration = (time.time() - start_time) * 1000
        
        return {
            'is_fraudulent': fraud_score >= 40,
            'fraud_score': fraud_score,
            'flags': flags,
            'rules_triggered': [f['rule'] for f in flags],
            'messages': [f['message'] for f in flags],
            'recommendation': 'REJECT' if fraud_score >= 75 else 'MANUAL_REVIEW' if fraud_score >= 40 else 'APPROVE',
            'graph_visualization': {
                'nodes': graph_nodes,
                'edges': graph_edges
            },
            'check_duration_ms': duration
        }
        
    except Exception as e:
        logger.error(f"Fraud check failed: {e}")
        neo4j.close()
        # Propagate error instead of returning default
        raise e


def get_graph_stats():
    """Get statistics about the graph - ENHANCED"""
    neo4j = Neo4jConnection()
    if not neo4j.connect():
        return {}
    
    query = """
    RETURN 
        COUNT{(p:Person)} as total_persons,
        COUNT{(c:Claim)} as total_claims,
        COUNT{(pol:Policy)} as total_policies,
        COUNT{(addr:Address)} as total_addresses,
        COUNT{(a:Agent)} as total_agents,
        COUNT{(v:Vendor)} as total_vendors,
        COUNT{(s:SSN)} as total_ssns,
        COUNT{(ast:Asset)} as total_assets
    """
    
    result = neo4j.execute_query(query)
    neo4j.close()
    
    return result[0] if result else {}


def get_dashboard_stats():
    """Get dashboard statistics from Neo4j graph"""
    neo4j = Neo4jConnection()
    if not neo4j.connect():
        return {
            'total_claims': 0,
            'fraud_detected': 0,
            'estimated_fraud_value': 0.0
        }
    
    try:
        # Get total claims and fraud statistics
        query = """
        MATCH (c:Claim)
        WITH count(c) as total_claims, collect(c) as all_claims
        
        // Count fraudulent claims (those with fraud score >= 40 or involved in fraud patterns)
        UNWIND all_claims as claim
        OPTIONAL MATCH (claim)<-[:FILED]-(p:Person)-[:HAS_SSN]->(s:SSN)<-[:HAS_SSN]-(p2:Person)
        WHERE p <> p2
        WITH total_claims, claim, count(p2) > 0 as has_shared_ssn
        
        OPTIONAL MATCH (claim)-[:INVOLVES]->(a:Asset)<-[:INVOLVES]-(c2:Claim)
        WHERE c2 <> claim
        WITH total_claims, claim, has_shared_ssn, count(c2) > 0 as has_asset_recycling
        
        OPTIONAL MATCH (claim)<-[:FILED]-(person:Person)-[:FILED]->(other_claim:Claim)
        WHERE other_claim <> claim
        WITH total_claims, claim, has_shared_ssn, has_asset_recycling, count(other_claim) >= 2 as has_velocity
        
        WITH total_claims,
             sum(CASE WHEN has_shared_ssn OR has_asset_recycling OR has_velocity OR toFloat(claim.amount) > 50000 THEN 1 ELSE 0 END) as fraud_count,
             sum(CASE WHEN has_shared_ssn OR has_asset_recycling OR has_velocity OR toFloat(claim.amount) > 50000 THEN toFloat(claim.amount) ELSE 0 END) as fraud_value
        
        RETURN total_claims, fraud_count, fraud_value
        """
        
        result = neo4j.execute_query(query)
        neo4j.close()
        
        if result and len(result) > 0:
            return {
                'total_claims': result[0].get('total_claims', 0),
                'fraud_detected': result[0].get('fraud_count', 0),
                'estimated_fraud_value': round(result[0].get('fraud_value', 0.0), 2)
            }
        
        return {
            'total_claims': 0,
            'fraud_detected': 0,
            'estimated_fraud_value': 0.0
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to get dashboard stats: {e}")
        neo4j.close()
        return {
            'total_claims': 0,
            'fraud_detected': 0,
            'estimated_fraud_value': 0.0
        }



def get_claim_graph_data(claim_id: str) -> Dict[str, Any]:
    """
    Fetch the graph neighborhood for a specific claim for visualization.
    Includes:
    - The Claim itself
    - Related Person, Policy, Agent, Vendor, Asset
    - Person's Address and SSN
    - Potential fraud rings (Shared SSN, Shared Address)
    - Other claims by the same person (Velocity)
    """
    neo4j = Neo4jConnection()
    if not neo4j.connect():
        raise Exception("Neo4j not available")
    
    try:
        query = """
        MATCH (c:Claim {transaction_id: $claim_id})
        
        // 1. Direct relationships (Person, Policy, Agent, Vendor, Asset)
        OPTIONAL MATCH (c)-[r1]-(n)
        
        // 2. Person details (Address, SSN)
        OPTIONAL MATCH (n:Person)-[r2]-(n2)
        WHERE n2:Address OR n2:SSN
        
        // 3. Fraud Rings (Shared SSN)
        OPTIONAL MATCH (n:Person)-[:HAS_SSN]->(ssn:SSN)<-[:HAS_SSN]-(p2:Person)
        
        // 4. Velocity (Other claims by same person)
        OPTIONAL MATCH (n:Person)-[:FILED]->(c2:Claim)
        WHERE c2 <> c
        
        RETURN 
            c, 
            collect(distinct r1) as r1s, 
            collect(distinct n) as neighbors,
            collect(distinct r2) as r2s,
            collect(distinct n2) as person_details,
            collect(distinct ssn) as shared_ssns,
            collect(distinct p2) as other_fraudsters,
            collect(distinct c2) as other_claims
        """
        
        results = neo4j.execute_query(query, {'claim_id': claim_id})
        
        nodes = []
        edges = []
        node_ids = set()
        edge_ids = set()
        
        def add_node(node_obj, label_override=None):
            if not node_obj: return
            # Neo4j node object handling might differ based on driver version/response format
            # Here we assume standard dict-like structure from execute_query serialization
            
            # Determine ID and Label
            # Note: execute_query returns .data() which is a dict of properties
            # It doesn't preserve elementId or labels directly in the dict usually, 
            # unless we explicitly return them in Cypher. 
            # However, our execute_query implementation returns [record.data() for record in result].
            # record.data() returns a dict where keys are return variables.
            # If a variable is a Node, it returns the properties.
            # It DOES NOT return the internal ID or labels by default in the dict.
            
            # To fix this, we need to adjust the query to return properties + labels + id, 
            # OR we infer them. 
            # Since we can't easily change the query structure dynamically, let's infer based on properties we know.
            
            # Actually, let's rewrite the query to return explicit maps to be safe.
            pass

        # RE-WRITING QUERY TO RETURN EXPLICIT MAPS FOR EASIER PARSING
        # RE-WRITING QUERY TO RETURN EXPLICIT MAPS FOR EASIER PARSING
        query_explicit = """
        MATCH (c:Claim {transaction_id: $claim_id})
        
        // 1. Direct neighbors (Person, Policy, Agent, Vendor, Asset)
        OPTIONAL MATCH (c)-[r1]-(n)
        WITH c, collect(distinct n) as neighbors, collect(distinct r1) as r1s
        
        // 2. Person details (Address, SSN)
        OPTIONAL MATCH (p:Person)-[r2]-(n2)
        WHERE p IN neighbors AND (n2:Address OR n2:SSN)
        WITH c, neighbors, r1s, collect(distinct n2) as person_details, collect(distinct r2) as r2s
        
        // 3. Fraud Rings (Shared SSN)
        OPTIONAL MATCH (p:Person)-[r3:HAS_SSN]->(ssn:SSN)<-[r4:HAS_SSN]-(p2:Person)
        WHERE p IN neighbors
        WITH c, neighbors, r1s, person_details, r2s, 
             collect(distinct p2) as other_fraudsters, 
             collect(distinct ssn) as shared_ssns,
             collect(distinct r3) as r3s,
             collect(distinct r4) as r4s
        
        // 4. Velocity (Other claims by same person)
        OPTIONAL MATCH (p:Person)-[r5:FILED]->(c2:Claim)
        WHERE p IN neighbors AND c2 <> c
        WITH c, neighbors, r1s, person_details, r2s, other_fraudsters, shared_ssns, r3s, r4s,
             collect(distinct c2) as other_claims,
             collect(distinct r5) as r5s
             
        // 5. Collusion (Agent-Vendor)
        OPTIONAL MATCH (a:Agent)-[r6:WORKS_WITH]->(v:Vendor)
        WHERE a IN neighbors AND v IN neighbors
        WITH c, neighbors, r1s, person_details, r2s, other_fraudsters, shared_ssns, r3s, r4s, other_claims, r5s,
             collect(distinct r6) as r6s
        
        // Return everything as a list of maps with 'id', 'label', 'properties'
        WITH 
            [c] + neighbors + person_details + other_fraudsters + shared_ssns + other_claims as all_nodes,
            r1s + r2s + r3s + r4s + r5s + r6s as all_rels
            
        // Process Nodes
        WITH all_nodes, all_rels
        UNWIND (CASE WHEN size(all_nodes) > 0 THEN all_nodes ELSE [null] END) as n
        WITH all_rels, collect(DISTINCT
            CASE WHEN n IS NOT NULL THEN {
                id: coalesce(n.transaction_id, n.customer_id, n.agent_id, n.vendor_id, n.value, n.address_key, elementId(n)), 
                labels: labels(n), 
                properties: properties(n)
            } ELSE null END
        ) as nodes_data
        
        // Process Relationships
        WITH nodes_data, all_rels
        UNWIND (CASE WHEN size(all_rels) > 0 THEN all_rels ELSE [null] END) as r
        WITH nodes_data, collect(DISTINCT
            CASE WHEN r IS NOT NULL THEN {
                source: coalesce(startNode(r).transaction_id, startNode(r).customer_id, startNode(r).agent_id, startNode(r).vendor_id, startNode(r).value, startNode(r).address_key, elementId(startNode(r))),
                target: coalesce(endNode(r).transaction_id, endNode(r).customer_id, endNode(r).agent_id, endNode(r).vendor_id, endNode(r).value, endNode(r).address_key, elementId(endNode(r))),
                type: type(r),
                properties: properties(r)
            } ELSE null END
        ) as rels_data
        
        RETURN 
            [node in nodes_data WHERE node IS NOT NULL] as nodes_data, 
            [rel in rels_data WHERE rel IS NOT NULL] as rels_data
        """
        
        results = neo4j.execute_query(query_explicit, {'claim_id': claim_id})
        
        if not results:
            return {'nodes': [], 'edges': []}
            
        data = results[0]
        final_nodes = []
        final_edges = []
        
        for n in data.get('nodes_data', []):
            # Determine primary label for visualization
            lbl = n['labels'][0] if n['labels'] else 'Unknown'
            # Assign a color/type based on label
            final_nodes.append({
                'id': n['id'],
                'label': lbl,
                'data': n['properties'],
                'group': 'nodes'
            })

        for r in data.get('rels_data', []):
            final_edges.append({
                'source': r['source'],
                'target': r['target'],
                'label': r['type'],
                'data': r['properties'],
                'group': 'edges'
            })
            
        def _make_serializable(obj):
            if isinstance(obj, (str, int, float, bool, type(None))):
                return obj
            if isinstance(obj, dict):
                return {k: _make_serializable(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [_make_serializable(v) for v in obj]
            return str(obj)

        return {
            'nodes': _make_serializable(final_nodes),
            'edges': _make_serializable(final_edges)
        }

    except Exception as e:
        logger.error(f"❌ Failed to fetch graph data: {e}")
        neo4j.close()
        raise e
    finally:
        neo4j.close()