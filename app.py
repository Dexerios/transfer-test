import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ===============================
# CONFIG
# ===============================

ROBLOX_API_KEY = os.environ.get("ROBLOX_API_KEY")
UNIVERSE_ID = 3064619271
DATASTORE_NAME = "TransferStore"

if not ROBLOX_API_KEY:
    raise RuntimeError("ROBLOX_API_KEY is not set")

ROBLOX_DATASTORE_URL = (
    f"https://apis.roblox.com/datastores/v1/universes/"
    f"{UNIVERSE_ID}/standard-datastores/datastore/entries/entry"
)

HEADERS = {
    "x-api-key": ROBLOX_API_KEY,
    "Content-Type": "application/json",
}

# ===============================
# HEALTH CHECK
# ===============================

@app.route("/", methods=["GET"])
def health():
    print("[HEALTH] OK")
    return "OK", 200

# ===============================
# WRITE TO DATASTORE
# ===============================

@app.route("/upload", methods=["POST"])
def upload():
    print("\n[UPLOAD] Incoming request")

    print("[UPLOAD] Headers:", dict(request.headers))

    payload = request.get_json(silent=True)
    print("[UPLOAD] Parsed JSON payload:", payload)

    if not payload:
        print("[UPLOAD] ERROR: Invalid or empty JSON")
        return jsonify({"error": "Invalid JSON"}), 400

    entry_key = payload.get("entryKey")
    data = payload.get("data")

    print("[UPLOAD] entryKey:", entry_key)
    print("[UPLOAD] data:", data)

    if not entry_key or data is None:
        print("[UPLOAD] ERROR: Missing entryKey or data")
        return jsonify({
            "error": "entryKey and data are required"
        }), 400

    params = {
        "datastoreName": DATASTORE_NAME,
        "scope": "global",
        "entryKey": entry_key,
    }

    print("[ROBLOX] Writing to datastore")
    print("[ROBLOX] URL:", ROBLOX_DATASTORE_URL)
    print("[ROBLOX] Params:", params)
    print("[ROBLOX] Data payload:", data)

    try:
        response = requests.put(
            ROBLOX_DATASTORE_URL,
            headers=HEADERS,
            params=params,
            json=data,
            timeout=5,  # keep this short to avoid 502s
        )
    except Exception as e:
        print("[ROBLOX] EXCEPTION during request:", repr(e))
        return jsonify({
            "error": "Exception while calling Roblox API",
            "details": str(e),
        }), 502

    print("[ROBLOX] Response status:", response.status_code)
    print("[ROBLOX] Response body:", response.text)

    if not response.ok:
        print("[ROBLOX] ERROR: Roblox rejected the write")
        return jsonify({
            "error": "Roblox API rejected the write",
            "status": response.status_code,
            "details": response.text,
        }), 502

    print("[UPLOAD] SUCCESS")
    return jsonify({
        "success": True,
        "writtenKey": entry_key
    }), 200
