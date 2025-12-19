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

print("[BOOT] Flask app started")
print(f"[BOOT] Universe ID: {UNIVERSE_ID}")
print(f"[BOOT] Datastore: {DATASTORE_NAME}")

# ===============================
# HEALTH CHECK
# ===============================

@app.route("/", methods=["GET"])
def health():
    print("[HEALTH] Health check hit")
    return "OK", 200

# ===============================
# WRITE TO DATASTORE
# ===============================

@app.route("/upload", methods=["POST"])
def upload():
    print("\n[UPLOAD] Incoming request")

    payload = request.get_json(silent=True)

    if not payload:
        print("[UPLOAD][ERROR] Invalid or missing JSON body")
        return jsonify({"error": "Invalid JSON"}), 400

    print(f"[UPLOAD] Payload received: {payload}")

    entry_key = payload.get("entryKey")
    data = payload.get("data")

    if not entry_key or data is None:
        print("[UPLOAD][ERROR] Missing entryKey or data")
        print(f"[UPLOAD] entryKey: {entry_key}")
        print(f"[UPLOAD] data: {data}")
        return jsonify({
            "error": "entryKey and data are required"
        }), 400

    print(f"[UPLOAD] entryKey = {entry_key}")
    print(f"[UPLOAD] data size = {len(str(data))} bytes (approx)")

    params = {
        "datastoreName": DATASTORE_NAME,
        "scope": "global",
        "entryKey": entry_key,
        # add this if you want overwrite behavior
        # "exclusiveCreate": "false",
    }

    print("[ROBLOX] Sending PUT request to Datastore API")
    print(f"[ROBLOX] URL: {ROBLOX_DATASTORE_URL}")
    print(f"[ROBLOX] Params: {params}")

    response = requests.put(
        ROBLOX_DATASTORE_URL,
        headers=HEADERS,
        params=params,
        json=data,
        timeout=15,
    )

    print("[ROBLOX] Response received")
    print(f"[ROBLOX] Status code: {response.status_code}")
    print(f"[ROBLOX] Response body: {response.text}")

    if not response.ok:
        print("[ROBLOX][ERROR] Datastore write rejected")
        return jsonify({
            "error": "Roblox API rejected the write",
            "status": response.status_code,
            "details": response.text,
        }), 502

    print("[UPLOAD][SUCCESS] Datastore write succeeded")

    return jsonify({
        "success": True,
        "writtenKey": entry_key
    }), 200
