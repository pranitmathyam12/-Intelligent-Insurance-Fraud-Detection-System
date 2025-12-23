# Insurance Fraud Detection - Frontend (Flask)

This is the web-based user interface for the Insurance Fraud Detection system. It provides an intuitive interface to upload claim documents, view real-time fraud analysis, and explore graph-based fraud patterns.

Built with:
- **Flask** (Python 3.11+)
- **Tailwind CSS** for modern UI
- **Font Awesome** for icons
- **Vanilla JavaScript** for interactive components

---

## Features

- 📄 **Document Upload & Analysis** - Upload PDF claim documents for automated processing
- 🔍 **Real-time Fraud Detection** - 3-step pipeline (Extract → Graph Ingestion → LLM Analysis)
- 📊 **Interactive Dashboard** - View fraud statistics and trends
- 💬 **AI Chatbot** - Ask questions about the fraud detection system
- 📈 **System Monitoring** - Track LLM usage, costs, and performance metrics
- ✅ **Evaluation Tools** - Assess model performance and accuracy

---

## Folder Overview

```
app/
├── main.py                 # Flask application and API routes
├── templates/              # HTML templates
│   ├── base.html          # Base layout with navigation
│   ├── upload.html        # Document upload and analysis page
│   ├── dashboard.html     # Analytics dashboard
│   ├── chat.html          # AI chatbot interface
│   ├── monitoring.html    # System monitoring
│   └── evaluation.html    # Model evaluation
├── static/                 # Static assets (if any)
├── utils/                  # Utility functions (optional)
└── .env                    # Environment variables
```

---

## 1. Environment Setup

### Required Environment Variables (`.env`)

Create a `.env` file in the project root:

```bash
# Backend API URL (FastAPI)
BACKEND_URL=http://localhost:8080
```

> The frontend communicates with the FastAPI backend for all fraud detection operations.

---

## 2. Installation

### Prerequisites

- Python 3.11 or higher
- Backend API running on `http://localhost:8080` (see backend README)
- Neo4j database running (required for fraud detection)

### Option A — Using **venv** (Recommended)

```bash
# Navigate to frontend folder
cd path/to/frontend/folder

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate        # macOS/Linux
# OR
venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt
# OR install manually:
pip install flask python-dotenv requests
```

---

## 3. Running the Frontend

Once installed, start the Flask development server:

```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Run the application
python3 main.py
```

You'll see:
```
 * Running on http://127.0.0.1:5001 (Press CTRL+C to quit)
 * Restarting with stat
 * Debugger is active!
```

---

## 4. Access the Application

Open your browser and navigate to:

```
http://localhost:5001
```

### Available Pages:

| Page | URL | Description |
|------|-----|-------------|
| **Dashboard** | `/` | View fraud statistics and trends |
| **Upload & Detect** | `/upload` | Upload PDFs and run fraud detection |
| **Chatbot** | `/chat` | Ask questions about fraud patterns |
| **Monitoring** | `/monitoring` | Track system performance and LLM usage |
| **Evaluation** | `/evaluation` | View model performance metrics |

---

## 5. Using the Fraud Detection Pipeline

### Upload & Detect Page

1. **Navigate to:** http://localhost:5001/upload
2. **Upload a PDF** - Click to upload an insurance claim document
3. **Click "Analyze Document"** - The system will automatically:
   - **Step 1:** Extract and classify the document (using LLM)
   - **Step 2:** Ingest data into Neo4j graph and detect fraud patterns
   - **Step 3:** Generate LLM-based fraud analysis and recommendations

### View Results

After analysis, explore the tabs:

- **Classify** - Document type and classification confidence
- **Extract** - Raw extracted JSON data
- **Map** - Graph ingestion results (nodes, relationships, fraud patterns)
- **Graph** - LLM's detailed fraud analysis with risk score
- **Result** - Final fraud verdict and summary

---

## 6. Sample Outputs

### 6.1 Dashboard Overview

![Dashboard Overview](/Outputs/Dashboard.png)

The main dashboard provides real-time fraud analytics and claim statistics

### 6.2 Upload & Detect Page

**Live Document Processing Interface**

![Upload & Detect Page](/Outputs/Upload.png)

This screenshot captures the system actively analyzing a life insurance claim for fraud detection

### 6.3 Fraud Detection Result - High Risk Case

![Fraud Detection Result](/Outputs/Fruad_Result.png)

### 6.4 AI Chatbot Interface

![AI Chatbot Interface](/Outputs/Chatbot.png)

The chatbot provides an intelligent interface to query the Neo4j knowledge graph using natural language.

### 6.5 System Monitoring

![System Monitoring](/Outputs/Monitoring.png)

The monitoring page provides real-time system performance metrics and LLM usage statistics.

### 6.6 Model Evaluation

![Model Evaluation](/Outputs/Evaluation_1.png)
![Model Evaluation](/Outputs/Evaluation_2.png)

The evaluation page provides detailed metrics and visualizations for model performance and accuracy.



## 7. API Routes

The frontend proxies requests to the backend API:

| Frontend Route | Backend Endpoint | Method | Description |
|----------------|-----------------|--------|-------------|
| `/api/upload` | `/v1/extract` | POST | Extract and classify document |
| `/api/fraud/ingest` | `/v1/fraud/ingest_to_graph` | POST | Ingest data to Neo4j graph |
| `/api/fraud/analyze` | `/v1/fraud/analyze` | POST | LLM-based fraud analysis |
| `/api/chat` | `/v1/chat` | POST | Chatbot queries (future) |

---

## 8. Configuration

### Backend Github Link

Github  - https://github.com/Belide-Aakash/insurance-fraud-detection-graph-backend

### Backend URL

The frontend connects to the backend via the `BACKEND_URL` environment variable in `.env`:

```bash
BACKEND_URL=http://localhost:8080
```

If your backend runs on a different port or host, update this value.

### CORS

The backend is configured to accept requests from:
- `http://localhost:5001`
- `http://127.0.0.1:5001`

If you change the frontend port, update the backend's CORS settings in `app/main.py`.

---

## 9. Common Troubleshooting

| Issue | Solution |
|-------|----------|
| **"Connection refused"** | Ensure the backend is running on `http://localhost:8080` |
| **"Graph ingest failed"** | Make sure Neo4j is running and credentials are correct in backend `.env` |
| **Blank page after upload** | Check browser console (F12) for JavaScript errors |
| **Module not found** | Run `pip install -r requirements.txt` in your venv |
| **Port 5001 already in use** | Change the port in `main.py`: `app.run(debug=True, port=5002)` |

---

## 10. Development

### File Structure

- **`main.py`** - Flask routes and API proxy endpoints
- **`templates/`** - Jinja2 HTML templates with Tailwind CSS
- **`upload.html`** - Main fraud detection interface with 3-step pipeline

### Making Changes

1. **Update templates** in `templates/` folder
2. **Update API routes** in `main.py`
3. **Restart Flask server** to see changes (or use `--reload` flag)

### Adding New Pages

1. Create a new template in `templates/newpage.html`
2. Add a route in `main.py`:
```python
@app.route('/newpage')
def newpage():
    return render_template('newpage.html', page='newpage')
```
3. Add navigation link in `base.html`

---

## 11. Production Deployment (Optional)

### Using Gunicorn (Linux/Mac)

```bash
pip install gunicorn

gunicorn -w 4 -b 0.0.0.0:5001 main:app
```

### Using Docker

Create a `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV BACKEND_URL=http://backend:8080

CMD ["python", "main.py"]
```

Build and run:
```bash
docker build -t fraud-frontend .
docker run -p 5001:5001 --env-file .env fraud-frontend
```

---

## 12. Tech Stack Details

### Frontend Technologies

| Technology | Purpose |
|------------|---------|
| **Flask** | Python web framework for routing and templating |
| **Jinja2** | Template engine for dynamic HTML |
| **Tailwind CSS** | Utility-first CSS framework for styling |
| **Font Awesome** | Icon library |
| **Vanilla JavaScript** | Interactive components and API calls |

### UI Features

- **Responsive Design** - Works on desktop and mobile
- **Dark Mode** - Automatic theme switching
- **Real-time Loading States** - Progress indicators during analysis
- **Interactive Tabs** - Step-by-step result visualization
- **PDF Viewer** - Embedded document preview

---

## 13. System Requirements

### Minimum Requirements

- **OS:** macOS, Linux, or Windows
- **Python:** 3.11 or higher
- **RAM:** 2GB minimum
- **Browser:** Chrome, Firefox, Safari, or Edge (modern versions)

### Dependencies

```txt
flask>=3.0.0
python-dotenv>=1.0.0
requests>=2.31.0
```

---

## 14. Contributing

### Development Workflow

1. Create a new branch for your feature
2. Make changes and test locally
3. Ensure all pages load without errors
4. Submit a pull request with description

### Code Style

- Use **4 spaces** for indentation
- Follow **PEP 8** for Python code
- Use **meaningful variable names**
- Add comments for complex logic

---

## 15. Support

For issues or questions:

1. Check the **Troubleshooting** section above
2. Review backend logs for API errors
3. Check browser console (F12) for frontend errors
4. Contact the development team

---

## 16. License

MIT License

---

## Quick Start Checklist

- [ ] Backend is running on `http://localhost:8080`
- [ ] Neo4j database is running
- [ ] Virtual environment is activated
- [ ] Dependencies are installed (`pip install -r requirements.txt`)
- [ ] `.env` file is configured with `BACKEND_URL`
- [ ] Flask server is running (`python3 main.py`)
- [ ] Browser opened to `http://localhost:5001`

---

**Happy Fraud Detection! 🚀**
