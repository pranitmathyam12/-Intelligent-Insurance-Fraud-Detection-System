# Intelligent Insurance Fraud Detection System

A comprehensive backend system for detecting insurance fraud using Graph Databases (Neo4j), Large Language Models (Google Gemini), and Data Warehousing (Snowflake).

## 🏗️ Architecture

The system is built using a modern tech stack:
- **Backend Framework**: FastAPI (Python)
- **Graph Database**: Neo4j (for relationship analysis and fraud pattern detection)
- **LLM**: Google Gemini 2.0 Flash (for document extraction, reasoning, and natural language interfaces)
- **Data Warehouse**: Snowflake (for historical data and analytics)
- **Logging**: Structlog

### Key Components
1.  **Intelligent Extraction**: Extracts structured data from insurance claim PDFs using LLMs.
2.  **Graph Ingestion**: Maps claims, customers, policies, and addresses into a Neo4j graph.
3.  **Fraud Detection**:
    *   **Pattern Matching**: Cypher queries to detect rings, recycling, and velocity fraud.
    *   **LLM Reasoning**: AI analysis of graph patterns to provide a verdict and explanation.
4.  **RAG & Graph Chat**:
    *   **RAG**: Chat with claim documents using vector search.
    *   **Graph Chat**: "Talk to your data" - converts natural language to Cypher queries.
5.  **Dashboard & Monitoring**: Real-time metrics and system health monitoring.

## 🚀 Setup & Installation

### Prerequisites
- Python 3.12+
- Neo4j Database (AuraDB or Local)
- Snowflake Account
- Google Cloud Project with Gemini API enabled

### Installation

1.  **Clone the repository**
    ```bash
    git clone <repository-url>
    cd insurance-fraud-detection-graph-backend
    ```

2.  **Install dependencies**
    Using `uv` (recommended):
    ```bash
    uv sync
    ```
    Or using `pip`:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Environment Configuration**
    Create a `.env` file in the root directory with the following variables:

    ```env
    # Google Gemini
    GEMINI_API_KEY=your_api_key
    GENAI_MODEL=gemini-2.0-flash-exp
    
    # Neo4j
    NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io
    NEO4J_USER=neo4j
    NEO4J_PASSWORD=your_password
    NEO4J_DATABASE=neo4j
    
    # Snowflake
    SNOWFLAKE_ACCOUNT=your_account
    SNOWFLAKE_USER=your_user
    SNOWFLAKE_PASSWORD=your_password
    SNOWFLAKE_WAREHOUSE=COMPUTE_WH
    SNOWFLAKE_DATABASE=INSURANCE_DB
    SNOWFLAKE_SCHEMA=PUBLIC
    ```

## 🏃‍♂️ Running the Application

Start the FastAPI server:

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

The API will be available at `http://localhost:8080`.
API Documentation (Swagger UI) is available at `http://localhost:8080/docs`.

## 📚 API Documentation

### 1. Extraction & Ingestion (`/v1`)

#### `POST /v1/extract`
Extracts data from an insurance claim PDF.
- **Input**: `file` (PDF), `enable_fraud_check` (bool), `save_to_graph` (bool)
- **Output**: Extracted JSON data, classification info, and optional fraud analysis.

#### `POST /v1/fraud/ingest_to_graph`
Ingests extracted claim data into Neo4j and runs initial fraud checks.
- **Input**: JSON payload from `/v1/extract`.
- **Output**: Graph creation stats, fraud score, and detected patterns.

### 2. Fraud Analysis (`/v1/fraud`)

#### `POST /v1/fraud/analyze`
Performs deep-dive fraud analysis using LLM reasoning on top of graph data.
- **Input**: Output from `ingest_to_graph`.
- **Output**: Detailed fraud reasoning, risk score (0-100), and recommendation (APPROVE/REVIEW/REJECT).

#### `GET /v1/fraud/graph/{claim_id}`
Retrieves graph visualization data (nodes & edges) for a specific claim.

### 3. Graph Chat (`/v1/graph-chat`)

#### `POST /v1/graph-chat/query`
Natural language interface to query the Neo4j database.
- **Input**: `{"query": "Show me all claims by John Doe"}`
- **Output**: Natural language answer and generated Cypher query.

### 4. RAG (Document Q&A) (`/v1/rag`)

#### `POST /v1/rag/query`
Ask questions about uploaded claim documents.
- **Input**: `{"user_message": "What is the cause of death?"}`
- **Output**: Answer with citations from the document.

### 5. Evaluation (`/v1/evaluate`)

#### `POST /v1/evaluate`
Runs a batch evaluation on sample claims to test system performance.
- **Input**: `sample_size` (int)
- **Output**: Fraud rate, average scores, and distribution metrics.

### 6. Batch Operations (`/v1`)

#### `POST /v1/upload-csv`
Uploads a CSV file of claims to Snowflake.
- **Input**: `file` (CSV)
- **Output**: Status and row count.

#### `POST /v1/build-graph`
Builds the Neo4j graph from data in Snowflake.
- **Input**: `limit` (optional int)
- **Output**: Number of nodes created.

#### `POST /v1/detect-fraud`
Runs fraud detection algorithms across the entire graph.
- **Input**: None
- **Output**: List of detected fraud patterns.

### 7. Dashboard & Monitoring

- `GET /v1/dashboard`: Aggregated metrics for the frontend dashboard.
- `GET /v1/monitoring/metrics`: System performance metrics (latency, token usage).
- `GET /v1/monitoring/logs`: Real-time log stream (SSE).

## 📂 Project Structure

```
app/
├── classifiers/       # Document classification logic
├── db/               # Database utilities (Neo4j, Snowflake)
├── extractors/       # PDF extraction logic using Gemini
├── llm/              # LLM interaction helpers
├── models/           # Pydantic data models
├── pipelines/        # Batch processing pipelines
├── routes/           # API endpoints (Controllers)
│   ├── extract.py    # Extraction endpoints
│   ├── fraud.py      # Fraud detection endpoints
│   ├── graph_chat.py # Graph Chat endpoints
│   ├── rag.py        # RAG endpoints
│   └── ...
├── services/         # Business logic services
└── main.py           # Application entry point
```