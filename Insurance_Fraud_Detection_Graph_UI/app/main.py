from flask import Flask, render_template, request, jsonify, Response, stream_with_context
import os
import requests
from dotenv import load_dotenv
import random
from datetime import datetime, timedelta
import json

load_dotenv()

app = Flask(__name__)
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8080")

# --- Mock Data Helpers (Keep for Dashboard for now) ---
def get_dashboard_data(timeline_days=None, alerts_limit=None):
    """Fetch dashboard analytics from backend with graceful fallback."""
    params = {}
    if timeline_days:
        params["timeline_days"] = timeline_days
    if alerts_limit:
        params["alerts_limit"] = alerts_limit

    fallback_timeline_days = timeline_days or 30
    fallback_timeline = []
    for i in range(fallback_timeline_days - 1, -1, -1):
        fallback_timeline.append({
            "date": (datetime.today() - timedelta(days=i)).strftime("%Y-%m-%d"),
            "legitimate": random.randint(30, 60),
            "fraudulent": random.randint(0, 5)
        })

    fallback_data = {
        "metrics": {
            "total_claims": 1245,
            "fraud_detected": 84,
            "estimated_fraud_value": 450000.0,
            "avg_processing_time": 1.2
        },
        "charts": {
            "claims_timeline": fallback_timeline,
            "risk_distribution": {
                "low": 1050,
                "medium": 111,
                "high": 84
            }
        },
        "high_risk_alerts": [
            {
                "claim_id": "CLM-9921",
                "type": "Auto Accident",
                "risk_score": 0.92,
                "date": (datetime.today() - timedelta(days=2)).strftime("%Y-%m-%d"),
                "status": "Review"
            },
            {
                "claim_id": "CLM-9918",
                "type": "Medical",
                "risk_score": 0.65,
                "date": (datetime.today() - timedelta(days=3)).strftime("%Y-%m-%d"),
                "status": "Review"
            }
        ],
        "metadata": {
            "timeline_days": fallback_timeline_days,
            "alerts_shown": 2,
            "data_sources": {
                "graph": "neo4j",
                "metrics": "snowflake"
            }
        }
    }

    try:
        resp = requests.get(f"{BACKEND_URL}/v1/dashboard", params=params, timeout=30)
        resp.raise_for_status()
        payload = resp.json()

        # Merge payload with fallback to guarantee template expectations
        return {
            "metrics": {**fallback_data["metrics"], **payload.get("metrics", {})},
            "charts": {
                "claims_timeline": payload.get("charts", {}).get("claims_timeline", fallback_data["charts"]["claims_timeline"]),
                "risk_distribution": {
                    **fallback_data["charts"]["risk_distribution"],
                    **payload.get("charts", {}).get("risk_distribution", {})
                }
            },
            "high_risk_alerts": payload.get("high_risk_alerts", fallback_data["high_risk_alerts"]),
            "metadata": {**fallback_data["metadata"], **payload.get("metadata", {})}
        }
    except requests.exceptions.RequestException as e:
        print(f"Dashboard backend failed: {e}")
        return fallback_data

# --- Routes ---


@app.route('/')
def dashboard():
    timeline_days = request.args.get('timeline_days', type=int)
    alerts_limit = request.args.get('alerts_limit', type=int)
    data = get_dashboard_data(timeline_days, alerts_limit)
    return render_template('dashboard.html', page='dashboard', data=data)

@app.route('/upload')
def upload():
    return render_template('upload.html', page='upload')


@app.route('/chat')
def chat():
    return render_template('chat.html', page='chat')

@app.route('/monitoring')
def monitoring():
    return render_template('monitoring.html', page='monitoring')

@app.route('/evaluation')
def evaluation():
    return render_template('evaluation.html', page='evaluation')

# --- API Endpoints ---

@app.route('/api/upload', methods=['POST'])
def api_upload():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    doc_type = request.form.get('doc_type')
    classify_if_missing = request.form.get('classify_if_missing', 'true')

    # Prepare request to FastAPI backend
    url = f"{BACKEND_URL}/v1/extract"
    params = {"classify_if_missing": classify_if_missing}
    if doc_type and doc_type != "Auto-Detect":
        params["doc_type"] = doc_type

    files = {'file': (file.filename, file.stream, file.content_type)}

    try:
        # Forward to backend
        resp = requests.post(url, params=params, files=files, timeout=60)
        resp.raise_for_status()
        return jsonify(resp.json())
    except requests.exceptions.RequestException as e:
        # Fallback for demo if backend is offline
        print(f"Backend connection failed: {e}")
        return jsonify({
            "error": "Backend connection failed", 
            "details": str(e),
            # Mock response for UI testing if backend is down
            "mock_fallback": True,
            "doc_type": "Medical Bill",
            "result": {
                "fraud_score": 0.85,
                "summary": "High mismatch in service codes vs diagnosis.",
                "extracted_fields": {
                    "Patient": "John Doe",
                    "Amount": "$45,000",
                    "Date": "2025-10-12"
                },
                "fraud_analysis": [
                    "Provider is flagged in 3 other fraud cases.",
                    "Service date overlaps with another claim in a different state."
                ]
            }
        }), 503
    
@app.route('/api/fraud/ingest', methods=['POST'])
def api_fraud_ingest():
    """Forward extracted data to graph ingestion endpoint"""
    try:
        data = request.get_json()
        url = f"{BACKEND_URL}/v1/fraud/ingest_to_graph"
        
        resp = requests.post(url, json=data, timeout=120)
        resp.raise_for_status()
        return jsonify(resp.json())
    except requests.exceptions.RequestException as e:
        print(f"Graph ingestion failed: {e}")
        return jsonify({
            "error": "Graph ingestion failed",
            "details": str(e)
        }), 503

@app.route('/api/fraud/analyze', methods=['POST'])
def api_fraud_analyze():
    """Forward graph data to LLM analysis endpoint"""
    try:
        data = request.get_json()
        url = f"{BACKEND_URL}/v1/fraud/analyze"
        
        resp = requests.post(url, json=data, timeout=120)
        resp.raise_for_status()
        return jsonify(resp.json())
    except requests.exceptions.RequestException as e:
        print(f"Fraud analysis failed: {e}")
        return jsonify({
            "error": "Fraud analysis failed",
            "details": str(e)
        }), 503

@app.route('/api/monitoring/metrics')
def api_monitoring_metrics():
    """Fetch monitoring metrics from backend and expose to UI"""
    fallback = {
        "tokens_used": 0,
        "api_cost": 0.0,
        "avg_time": 0.0,
        "total_requests": 0,
        "fallback": True
    }

    try:
        resp = requests.get(f"{BACKEND_URL}/v1/monitoring/metrics", timeout=15)
        resp.raise_for_status()
        return jsonify(resp.json())
    except requests.exceptions.RequestException as e:
        print(f"Monitoring metrics failed: {e}")
        return jsonify(fallback)

@app.route('/api/monitoring/token_usage')
def api_monitoring_token_usage():
    """Fetch token usage timeline for monitoring chart"""
    days = request.args.get('days', default=7, type=int)
    fallback_timeline = []
    total_tokens = 0
    total_cost = 0.0
    for hour in range(days * 24):
        tokens = random.randint(500, 2500)
        cost = round(tokens * 0.00005, 4)
        total_tokens += tokens
        total_cost += cost
        timestamp = (datetime.utcnow() - timedelta(hours=(days * 24 - hour))).strftime("%Y-%m-%d %H:00:00")
        fallback_timeline.append({
            "timestamp": timestamp,
            "tokens": tokens,
            "cost": cost
        })

    fallback = {
        "timeline": fallback_timeline,
        "metadata": {
            "days": days,
            "data_points": len(fallback_timeline),
            "total_tokens": total_tokens,
            "total_cost": round(total_cost, 4)
        },
        "fallback": True
    }

    try:
        resp = requests.get(f"{BACKEND_URL}/v1/monitoring/token-usage", params={"days": days}, timeout=30)
        resp.raise_for_status()
        return jsonify(resp.json())
    except requests.exceptions.RequestException as e:
        print(f"Monitoring token usage failed: {e}")
        return jsonify(fallback)

@app.route('/api/monitoring/logs')
def api_monitoring_logs():
    """Fetch recent logs from backend (polling-based)"""
    limit = request.args.get('limit', default=50, type=int)
    
    fallback = {
        "logs": [{
            "timestamp": datetime.utcnow().isoformat(),
            "level": "INFO",
            "message": "No logs available",
            "location": ""
        }],
        "count": 1,
        "fallback": True
    }

    try:
        resp = requests.get(f"{BACKEND_URL}/v1/monitoring/logs", params={"limit": limit}, timeout=10)
        resp.raise_for_status()
        return jsonify(resp.json())
    except requests.exceptions.RequestException as e:
        print(f"Monitoring logs failed: {e}")
        return jsonify(fallback)


@app.route('/api/chat', methods=['POST'])
def api_chat():
    payload = request.get_json() or {}
    mode = payload.get('mode', 'rag')
    user_message = payload.get('message', '').strip()
    session_id = payload.get('session_id')
    include_history = payload.get('include_history', True)

    if not user_message:
        return jsonify({"error": "Message is required"}), 400

    if mode == 'graph':
        url = f"{BACKEND_URL}/v1/graph-chat/query"
    else:
        url = f"{BACKEND_URL}/v1/rag/query"

    request_body = {
        "user_message": user_message,
        "include_history": include_history
    }
    if session_id:
        request_body["session_id"] = session_id
    
    try:
        resp = requests.post(url, json=request_body, timeout=60)
        resp.raise_for_status()
        return jsonify(resp.json())
    except requests.exceptions.RequestException as e:
        print(f"Chat backend failed: {e}")
        return jsonify({
            "success": False,
            "answer": "I'm having trouble connecting to the retrieval service right now.",
            "error": str(e)
        }), 503

@app.route('/api/evaluate', methods=['POST'])
def api_evaluate():
    """Run model evaluation on sample claims"""
    try:
        data = request.get_json()
        sample_size = data.get('sample_size', 500)
        
        url = f"{BACKEND_URL}/v1/evaluate"
        
        resp = requests.post(url, params={'sample_size': sample_size}, timeout=300)
        resp.raise_for_status()
        return jsonify(resp.json())
    except requests.exceptions.RequestException as e:
        print(f"Evaluation failed: {e}")
        return jsonify({
            "error": "Evaluation failed",
            "details": str(e)
        }), 503

if __name__ == '__main__':
    app.run(debug=True, port=5001)
