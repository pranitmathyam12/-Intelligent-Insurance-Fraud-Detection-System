import os
from dotenv import load_dotenv
load_dotenv()

from neo4j import GraphDatabase

uri = os.getenv('NEO4J_URI')
user = os.getenv('NEO4J_USER')
password = os.getenv('NEO4J_PASSWORD')

print(f"Connecting to: {uri}")
print(f"User: {user}")
print(f"Password length: {len(password)}")

# Create driver exactly as in the class
driver = GraphDatabase.driver(uri, auth=(user, password))

try:
    driver.verify_connectivity()
    print("✅ Connection successful!")
    
    # Test query
    with driver.session(database='neo4j') as session:
        result = session.run('RETURN 1 as test')
        print(f"Query result: {result.single()['test']}")
    
    driver.close()
    print("✅ All operations successful!")
    
except Exception as e:
    print(f"❌ Failed: {e}")
    driver.close()
