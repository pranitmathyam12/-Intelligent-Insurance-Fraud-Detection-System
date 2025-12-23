from neo4j import GraphDatabase
from app.config import settings
import structlog

log = structlog.get_logger()

class Neo4jDriver:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.driver = None
        return cls._instance
    
    def connect(self):
        if self.driver is None:
            uri = settings.NEO4J_URI
            user = settings.NEO4J_USER
            password = settings.NEO4J_PASSWORD
            self.driver = GraphDatabase.driver(uri, auth=(user, password))
            log.info("neo4j.connected", uri=uri)
        return self.driver
    
    def close(self):
        if self.driver:
            self.driver.close()
            self.driver = None
            log.info("neo4j.disconnected")
    
    def execute_query(self, query: str, parameters: dict = None):
        """Execute a Cypher query and return results"""
        driver = self.connect()
        with driver.session() as session:
            result = session.run(query, parameters or {})
            return [record.data() for record in result]

# Singleton instance
neo4j_driver = Neo4jDriver()
