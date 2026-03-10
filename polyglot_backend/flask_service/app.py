import os

import requests
from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO

load_dotenv()

FASTAPI_URL = os.getenv("FASTAPI_URL", "http://fastapi:8001")
INTERNAL_EVENT_TOKEN = os.getenv("INTERNAL_EVENT_TOKEN", "internal-token")
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,https://canteen-admin.vercel.app,https://canteen-admin-kappa.vercel.app,https://canteen-student.vercel.app",
    ).split(",")
    if origin.strip()
]

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "change-me")

CORS(app, resources={r"/*": {"origins": CORS_ORIGINS}}, supports_credentials=True)
socketio = SocketIO(app, cors_allowed_origins=CORS_ORIGINS)


def _filter_response_headers(headers: requests.structures.CaseInsensitiveDict):
    blocked = {"content-encoding", "transfer-encoding", "connection", "content-length"}
    return [(k, v) for k, v in headers.items() if k.lower() not in blocked]


@app.get("/health")
def health():
    return jsonify({"success": True, "message": "healthcheck", "data": {"service": "flask", "status": "healthy"}})


@app.route("/api", defaults={"path": ""}, methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
@app.route("/api/<path:path>", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
def proxy_api(path: str):
    target = f"{FASTAPI_URL.rstrip('/')}/api/{path}" if path else f"{FASTAPI_URL.rstrip('/')}/api"

    headers = {k: v for k, v in request.headers if k.lower() != "host"}
    try:
        resp = requests.request(
            method=request.method,
            url=target,
            headers=headers,
            params=request.args,
            data=request.get_data(),
            cookies=request.cookies,
            timeout=20,
            allow_redirects=False,
        )
    except requests.RequestException:
        return jsonify({"success": False, "message": "Upstream API unavailable", "code": "upstream_unavailable"}), 503

    response = Response(resp.content, resp.status_code)
    for key, value in _filter_response_headers(resp.headers):
        response.headers[key] = value
    return response


@app.post("/internal/events/<event_name>")
def internal_event(event_name: str):
    token = request.headers.get("x-internal-token")
    if token != INTERNAL_EVENT_TOKEN:
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    payload = request.get_json(silent=True) or {}

    if event_name == "order_created":
        socketio.emit("order_created", payload)
    elif event_name == "order_status_updated":
        socketio.emit("order_status_updated", payload)
    else:
        return jsonify({"success": False, "message": "Unknown event"}), 400

    return jsonify({"success": True, "message": "Event emitted", "data": {"event": event_name}})


@socketio.on("connect")
def on_connect():
    socketio.emit("connected", {"message": "Socket connected"})


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8002"))
    socketio.run(app, host="0.0.0.0", port=port)