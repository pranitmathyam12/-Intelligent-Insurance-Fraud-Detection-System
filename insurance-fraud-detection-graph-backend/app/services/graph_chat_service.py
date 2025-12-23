"""
Graph Chat Service - Natural language interface to Neo4j fraud detection graph

Uses Gemini LLM to:
1. Convert natural language questions to Cypher queries
2. Execute queries on Neo4j
3. Interpret results and provide natural language responses
"""

import os
import time
import structlog
from typing import Dict, Any, List, Optional
from google import genai
from google.genai import types
from app.db.neo4j_utils import Neo4jConnection

log = structlog.get_logger()


class GraphChatService:
    """Service for natural language querying of the Neo4j fraud detection graph"""
    
    def __init__(self):
        """Initialize the Graph Chat service"""
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables")
        
        self.client = genai.Client(api_key=api_key)
        self.model = os.getenv('GENAI_MODEL', 'gemini-2.5-flash')
        
        # Graph schema documentation for LLM context
        self.schema_context = self._get_schema_context()
        
        # Session storage (in-memory for now)
        self._sessions = {}
    
    def _get_schema_context(self) -> str:
        """
        Get comprehensive schema context for the LLM to generate accurate Cypher queries
        """
        return """
# Neo4j Insurance Fraud Detection Graph Schema

## Node Types

### Person
Properties: customer_id, name, age, marital_status, employment_status, education, social_class, family_members

### SSN
Properties: value (masked SSN for privacy)

### Address
Properties: address_key, line1, line2, city, state, postal_code

### Policy
Properties: policy_number, type (insurance type), premium, effective_date, risk_segment, house_type

### Claim
Properties: transaction_id, amount, loss_date, report_date, severity, status, incident_city, incident_state, 
           incident_hour, authority_contacted, any_injury, police_report, type (insurance type)

### Agent
Properties: agent_id

### Vendor  
Properties: vendor_id

### Asset
Properties: value (VIN for vehicles, IMEI for mobile devices, address for property), type (Vehicle, Device, RealEstate)

## Relationships

- Person -[:HAS_SSN]-> SSN
- Person -[:LIVES_AT]-> Address
- Person -[:OWNS_POLICY]-> Policy
- Person -[:FILED]-> Claim
- Claim -[:COVERED_BY]-> Policy
- Agent -[:HANDLED]-> Claim
- Claim -[:REPAIRED_BY]-> Vendor
- Agent -[:WORKS_WITH {count: integer}]-> Vendor
- Claim -[:INVOLVES]-> Asset

## Fraud Detection Patterns

### 1. Shared PII Rings (CRITICAL)
Multiple people sharing the same SSN indicates identity theft.
Query Pattern:
```cypher
MATCH (p1:Person)-[:HAS_SSN]->(s:SSN)<-[:HAS_SSN]-(p2:Person)
WHERE p1.customer_id < p2.customer_id
```

### 2. Collusive Provider Rings (HIGH)
Agents and vendors working together on many claims suggests collusion.
Query Pattern:
```cypher
MATCH (a:Agent)-[r:WORKS_WITH]->(v:Vendor)
WHERE r.count > 5
```

### 3. Asset Recycling (HIGH)
Same asset (VIN, IMEI, property) claimed multiple times.
Query Pattern:
```cypher
MATCH (c:Claim)-[:INVOLVES]->(a:Asset)
WITH a, count(c) as claim_count
WHERE claim_count > 1
```

### 4. Velocity Fraud (HIGH)
Person filing multiple claims rapidly.
Query Pattern:
```cypher
MATCH (p:Person)-[:FILED]->(c:Claim)
WITH p, count(c) as claim_count
WHERE claim_count >= 3
```

### 5. Double Dipping (HIGH)
Duplicate or nearly identical claims.
Query Pattern:
```cypher
MATCH (c1:Claim), (c2:Claim)
WHERE c1.transaction_id < c2.transaction_id
  AND c1.amount = c2.amount
  AND c1.loss_date = c2.loss_date
```

### 6. Multiple Claimants at Same Address (MEDIUM)
Multiple people from same address filing many claims.
Query Pattern:
```cypher
MATCH (p:Person)-[:LIVES_AT]->(addr:Address)
MATCH (p)-[:FILED]->(c:Claim)
WITH addr, count(DISTINCT p) as person_count, count(c) as claim_count
WHERE person_count > 1 AND claim_count > 2
```

## Query Guidelines

1. Always use `LIMIT` to prevent excessive results (default 50, max 100)
2. Use `ORDER BY` for ranking results (e.g., by fraud score, claim count, amount)
3. Return descriptive field names for clarity
4. For counts, use `count()` or `size()`
5. For aggregations, use `WITH` clauses
6. Convert amounts to float for calculations: `toFloat(c.amount)`
7. Date comparisons should use string comparison for YYYY-MM-DD format
8. Always handle NULL values with `coalesce()` or WHERE IS NOT NULL

## Example Queries

**Q: How many claims were filed by John Doe?**
```cypher
MATCH (p:Person {name: 'John Doe'})-[:FILED]->(c:Claim)
RETURN count(c) as claim_count
```

**Q: How many claims are there for each insurance type?**
```cypher
MATCH (c:Claim)
RETURN c.type as insurance_type, count(c) as count
ORDER BY count DESC
```

**Q: Get me the top 10 high-risk claims by amount**
```cypher
MATCH (c:Claim)
WHERE c.severity IN ['Major Loss', 'Total Loss']
RETURN c.transaction_id, toFloat(c.amount) as amount, c.severity, c.status
ORDER BY amount DESC
LIMIT 10
```

**Q: Get me the details of potential fraud rings linked to claim TXN12345**
```cypher
MATCH (c:Claim {transaction_id: 'TXN12345'})<-[:FILED]-(p:Person)
// Find other people linked via shared SSN or Address
OPTIONAL MATCH (p)-[:HAS_SSN]->(s:SSN)<-[:HAS_SSN]-(p2:Person)
OPTIONAL MATCH (p)-[:LIVES_AT]->(a:Address)<-[:LIVES_AT]-(p3:Person)
RETURN p.name as claimant, 
       collect(DISTINCT p2.name) as shared_ssn_links,
       collect(DISTINCT p3.name) as shared_address_links
```

**Q: How many high-severity claims for Motor insurance?**
```cypher
MATCH (c:Claim)
WHERE c.type = 'Motor' AND c.severity IN ['Major Loss', 'Total Loss']
RETURN count(c) as high_severity_motor_claims
```

**Q: Who are the most frequent claimants?**
```cypher
MATCH (p:Person)-[:FILED]->(c:Claim)
WITH p, count(c) as claim_count, sum(toFloat(c.amount)) as total_claimed
WHERE claim_count >= 2
RETURN p.customer_id, p.name, claim_count, total_claimed
ORDER BY claim_count DESC
LIMIT 20
```

**Q: Find claims with shared SSNs**
```cypher
MATCH (p:Person)-[:HAS_SSN]->(s:SSN)<-[:HAS_SSN]-(p2:Person)
WHERE p.customer_id < p2.customer_id
MATCH (p)-[:FILED]->(c:Claim)
RETURN s.value as ssn, 
       collect(DISTINCT p.name) as people,
       collect(DISTINCT c.transaction_id) as claims
LIMIT 20
```

**Q: Which agents handle the most claims?**
```cypher
MATCH (a:Agent)-[:HANDLED]->(c:Claim)
RETURN a.agent_id, count(c) as claims_handled
ORDER BY claims_handled DESC
LIMIT 10
```

**Q: Which vendors are involved in the most claims?**
```cypher
MATCH (v:Vendor)<-[:REPAIRED_BY]-(c:Claim)
RETURN v.vendor_id, count(c) as claims_repaired
ORDER BY claims_repaired DESC
LIMIT 10
```

**Q: Check for collusion between Agent X and Vendor Y**
```cypher
MATCH (a:Agent {agent_id: 'X'})-[r:WORKS_WITH]->(v:Vendor {vendor_id: 'Y'})
RETURN a.agent_id, v.vendor_id, r.count as collaboration_count
```
"""

    def generate_cypher_query(self, user_question: str, conversation_history: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """
        Use Gemini LLM to generate a Cypher query from natural language
        
        Args:
            user_question: User's natural language question
            conversation_history: Previous conversation messages
            
        Returns:
            Dict with generated query and explanation
        """
        try:
            log.info("graph_chat.generating_cypher", question=user_question[:100])
            
            # Build the prompt
            system_prompt = f"""You are an expert Neo4j Cypher query generator for an insurance fraud detection system.

{self.schema_context}

Your task is to convert natural language questions into valid Cypher queries.

**IMPORTANT RULES:**
1. Generate ONLY the Cypher query, nothing else
2. Always use LIMIT (max 100, default 50)
3. Return descriptive field names
4. Handle NULLs appropriately
5. Use ORDER BY for rankings
6. Convert amounts to float: toFloat(c.amount)
7. DO NOT use markdown code blocks or formatting
8. DO NOT include explanations in the query
9. The query should be executable as-is

**OUTPUT FORMAT:**
Just output the raw Cypher query text. Example:

MATCH (c:Claim) WHERE toFloat(c.amount) > 50000 RETURN c.transaction_id, c.amount LIMIT 20

That's it. No markdown, no code blocks, no explanations.
"""
            
            # Build conversation context
            contents = []
            
            if conversation_history:
                for msg in conversation_history:
                    role = 'user' if msg.get('role') == 'user' else 'model'
                    content = msg.get('content', '')
                    contents.append(types.Content(
                        role=role,
                        parts=[types.Part(text=content)]
                    ))
            
            # Add current question with system context
            user_prompt = f"{system_prompt}\n\n**User Question:** {user_question}\n\n**Cypher Query:**"
            contents.append(types.Content(
                role='user',
                parts=[types.Part(text=user_prompt)]
            ))
            
            # Generate Cypher query
            response = self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    temperature=0.1,  # Low temperature for precise query generation
                    top_p=0.95,
                    top_k=40,
                )
            )
            
            cypher_query = response.text.strip() if response.text else ""
            
            # Clean up the query (remove markdown code blocks if present)
            if cypher_query.startswith('```'):
                lines = cypher_query.split('\n')
                cypher_query = '\n'.join(line for line in lines if not line.startswith('```'))
                cypher_query = cypher_query.strip()
            
            # Remove any "cypher" language identifier
            if cypher_query.lower().startswith('cypher'):
                cypher_query = cypher_query[6:].strip()
            
            log.info("graph_chat.cypher_generated", query_preview=cypher_query[:200])
            
            return {
                'success': True,
                'cypher_query': cypher_query,
                'original_question': user_question
            }
            
        except Exception as e:
            log.error("graph_chat.cypher_generation_failed", error=str(e))
            return {
                'success': False,
                'error': f"Failed to generate Cypher query: {str(e)}"
            }
    
    def execute_cypher_query(self, cypher_query: str) -> Dict[str, Any]:
        """
        Execute a Cypher query on Neo4j
        
        Args:
            cypher_query: The Cypher query to execute
            
        Returns:
            Dict with query results
        """
        try:
            log.info("graph_chat.executing_cypher", query_preview=cypher_query[:200])
            
            neo4j = Neo4jConnection()
            if not neo4j.connect():
                return {
                    'success': False,
                    'error': 'Neo4j connection failed'
                }
            
            query_start = time.time()
            results = neo4j.execute_query(cypher_query)
            query_time_ms = (time.time() - query_start) * 1000
            
            neo4j.close()
            
            log.info("graph_chat.query_executed", 
                    rows_returned=len(results) if results else 0,
                    query_time_ms=query_time_ms)
            
            return {
                'success': True,
                'results': results or [],
                'row_count': len(results) if results else 0,
                'query_time_ms': query_time_ms
            }
            
        except Exception as e:
            log.error("graph_chat.query_execution_failed", error=str(e))
            return {
                'success': False,
                'error': f"Query execution failed: {str(e)}",
                'results': [],
                'row_count': 0
            }
    
    def interpret_results(self, 
                         user_question: str,
                         cypher_query: str,
                         results: List[Dict],
                         conversation_history: Optional[List[Dict]] = None) -> str:
        """
        Use Gemini LLM to interpret query results and generate natural language response
        
        Args:
            user_question: Original user question
            cypher_query: Executed Cypher query
            results: Query results from Neo4j
            conversation_history: Previous conversation
            
        Returns:
            Natural language interpretation of results
        """
        try:
            log.info("graph_chat.interpreting_results", result_count=len(results))
            
            # Build interpretation prompt
            interpretation_prompt = f"""You are analyzing results from a Neo4j graph database query for insurance fraud detection.

**User's Question:** {user_question}

**Cypher Query Executed:**
{cypher_query}

**Query Results ({len(results)} rows):**
{self._format_results_for_llm(results)}

**Task:**
Provide a clear, concise natural language answer to the user's question based on these results.

**Guidelines:**
1. Be specific - mention actual numbers, names, IDs from the results
2. Highlight fraud patterns or suspicious activities if found
3. If no results, explain that clearly
4. Use business-friendly language, not technical jargon
5. Keep response under 300 words
6. If results show fraud patterns, explain the risk level and implications

**Response:**
"""
            
            # Build conversation context
            contents = []
            
            if conversation_history:
                for msg in conversation_history[-6:]:  # Last 3 exchanges
                    role = 'user' if msg.get('role') == 'user' else 'model'
                    content = msg.get('content', '')
                    contents.append(types.Content(
                        role=role,
                        parts=[types.Part(text=content)]
                    ))
            
            contents.append(types.Content(
                role='user',
                parts=[types.Part(text=interpretation_prompt)]
            ))
            
            # Generate interpretation
            response = self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    temperature=0.3,  # Slightly higher for natural responses
                    top_p=0.95,
                )
            )
            
            interpretation = response.text.strip() if response.text else "Unable to interpret results."
            
            log.info("graph_chat.interpretation_complete", response_length=len(interpretation))
            
            return interpretation
            
        except Exception as e:
            log.error("graph_chat.interpretation_failed", error=str(e))
            return f"I found {len(results)} result(s), but encountered an error interpreting them: {str(e)}"
    
    def _format_results_for_llm(self, results: List[Dict], max_rows: int = 50) -> str:
        """
        Format query results for LLM consumption
        
        Args:
            results: Query results
            max_rows: Maximum rows to include
            
        Returns:
            Formatted results string
        """
        if not results:
            return "No results found."
        
        # Limit results to prevent token overflow
        limited_results = results[:max_rows]
        
        # Convert to readable format
        import json
        formatted = json.dumps(limited_results, indent=2, default=str)
        
        if len(results) > max_rows:
            formatted += f"\n\n... and {len(results) - max_rows} more rows"
        
        return formatted
    
    def query(self,
             user_message: str,
             session_id: Optional[str] = None,
             include_history: bool = True) -> Dict[str, Any]:
        """
        Main query method - handles the complete flow
        
        Args:
            user_message: User's natural language question
            session_id: Optional session ID for conversation context
            include_history: Whether to include conversation history
            
        Returns:
            Dict with answer, cypher query, results, and metadata
        """
        try:
            query_start = time.time()
            
            # Generate session ID if not provided
            if not session_id:
                import uuid
                session_id = str(uuid.uuid4())
            
            # Get conversation history
            chat_history = []
            if include_history and session_id in self._sessions:
                chat_history = self._sessions[session_id][-10:]  # Last 10 messages
            
            log.info("graph_chat.query_start",
                    session_id=session_id,
                    message_length=len(user_message))
            
            # Step 1: Generate Cypher query
            cypher_result = self.generate_cypher_query(user_message, chat_history)
            
            if not cypher_result.get('success'):
                return {
                    'success': False,
                    'session_id': session_id,
                    'answer': f"I couldn't understand your question. {cypher_result.get('error', '')}",
                    'cypher_query': None,
                    'results': [],
                    'query_time_ms': (time.time() - query_start) * 1000
                }
            
            cypher_query = cypher_result['cypher_query']
            
            # Step 2: Execute query on Neo4j
            exec_result = self.execute_cypher_query(cypher_query)
            
            if not exec_result.get('success'):
                return {
                    'success': False,
                    'session_id': session_id,
                    'answer': f"Query execution failed: {exec_result.get('error', 'Unknown error')}",
                    'cypher_query': cypher_query,
                    'results': [],
                    'query_time_ms': (time.time() - query_start) * 1000
                }
            
            results = exec_result['results']
            
            # Step 3: Interpret results
            interpretation = self.interpret_results(
                user_question=user_message,
                cypher_query=cypher_query,
                results=results,
                conversation_history=chat_history
            )
            
            query_time_ms = (time.time() - query_start) * 1000
            
            # Store in session history
            if session_id not in self._sessions:
                self._sessions[session_id] = []
            
            self._sessions[session_id].append({
                'role': 'user',
                'content': user_message
            })
            self._sessions[session_id].append({
                'role': 'model',
                'content': interpretation
            })
            
            # Limit session size
            if len(self._sessions[session_id]) > 20:
                self._sessions[session_id] = self._sessions[session_id][-20:]
            
            log.info("graph_chat.query_complete",
                    session_id=session_id,
                    query_time_ms=query_time_ms,
                    results_count=len(results))
            
            return {
                'success': True,
                'session_id': session_id,
                'answer': interpretation,
                'cypher_query': cypher_query,
                'results': results,
                'result_count': len(results),
                'query_time_ms': query_time_ms,
                'model': self.model
            }
            
        except Exception as e:
            log.error("graph_chat.query_failed", error=str(e))
            return {
                'success': False,
                'session_id': session_id,
                'answer': f"An error occurred: {str(e)}",
                'cypher_query': None,
                'results': [],
                'query_time_ms': (time.time() - query_start) * 1000 if 'query_start' in locals() else 0
            }
    
    def get_session_history(self, session_id: str) -> List[Dict]:
        """Get conversation history for a session"""
        return self._sessions.get(session_id, [])
    
    def clear_session(self, session_id: str) -> bool:
        """Clear conversation history for a session"""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False


# Singleton instance
_graph_chat_service: Optional[GraphChatService] = None


def get_graph_chat_service() -> GraphChatService:
    """
    Get or create the singleton GraphChatService instance
    
    Returns:
        GraphChatService instance
    """
    global _graph_chat_service
    
    if _graph_chat_service is None:
        _graph_chat_service = GraphChatService()
    
    return _graph_chat_service
