from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from dotenv import load_dotenv

# Force load .env from project root
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # which API to use
    USE_VERTEXAI: bool = False          # set True only if you intend to use Vertex AI

    # Developer API (Gemini API) credentials
    GEMINI_API_KEY: str | None = None   # read from .env

    # Vertex AI credentials (if USE_VERTEXAI=True)
    VERTEX_PROJECT: str | None = None
    VERTEX_LOCATION: str | None = None  # e.g. "us-central1"

    GENAI_MODEL: str = "gemini-2.5-flash"
    MAX_OUTPUT_TOKENS: int = 4096

    # pricing
    PRICING_INPUT_PER_M: float = 0.30
    PRICING_OUTPUT_PER_M: float = 2.50

    MAX_UPLOAD_MB: int = 20
    
    # Snowflake Configuration
    SNOWFLAKE_ACCOUNT: str | None = None
    SNOWFLAKE_USER: str | None = None
    SNOWFLAKE_PASSWORD: str | None = None
    SNOWFLAKE_WAREHOUSE: str | None = None
    SNOWFLAKE_DATABASE: str | None = None
    SNOWFLAKE_SCHEMA: str | None = None
    

    # Neo4j Configuration
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"
    NEO4J_DATABASE: str = "neo4j"
settings = Settings()