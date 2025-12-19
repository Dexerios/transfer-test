import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ===============================
# CONFIG (same intent as before)
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
    return "OK", 200

# ===============================
# WRITE TO DATASTORE
# ===============================

@app.route("/upload", methods=["POST"])
def upload():
    payload = request.get_json(silent=True)

    if not payload:
        return jsonify({"error": "Invalid JSON"}), 400

    entry_key = payload.get("entryKey")
    data = payload.get("data")

    if not entry_key or data is None:
        return jsonify({
            "error": "entryKey and data are required"
        }), 400

    params = {
        "datastoreName": DATASTORE_NAME,
        "scope": "global",
        "entryKey": entry_key,
    }

    response = requests.put(
        ROBLOX_DATASTORE_URL,
        headers=HEADERS,
        params=params,
        json=data,
        timeout=15,
    )

    if not response.ok:
        return jsonify({
            "error": "Roblox API rejected the write",
            "status": response.status_code,
            "details": response.text,
        }), 502

    return jsonify({
        "success": True,
        "writtenKey": entry_key
    }), 200
