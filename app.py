import os
import json
import logging
import requests
from flask import Flask, request, jsonify

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

# ===============================
# CONFIG
# ===============================

API_KEY = os.getenv("ROBLOX_API_KEY")  # REQUIRED
NEW_UNIVERSE = 3064619271
NEW_DATASTORE = "TransferStore"

if not API_KEY:
    raise RuntimeError("ROBLOX_API_KEY not set")

# ===============================
# Roblox Datastore Write
# ===============================

def write_to_datastore(entry_key, data):
    url = (
        f"https://apis.roblox.com/datastores/v1/universes/"
        f"{NEW_UNIVERSE}/standard-datastores/datastore/entries/entry"
    )

    headers = {
        "x-api-key": API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    params = {
        "datastoreName": NEW_DATASTORE,
        "scope": "global",
        "entryKey": entry_key,
    }

    response = requests.post(
        url,
        headers=headers,
        params=params,
        data=json.dumps(data),
        timeout=10,
    )

    response.raise_for_status()

# ===============================
# Health Check
# ===============================

@app.route("/", methods=["GET"])
def health():
    return "OK", 200

# ===============================
# RECEIVE DATA FROM OLD GAME
# ===============================

@app.route("/upload", methods=["POST"])
def upload():
    try:
        payload = request.get_json(force=True)

        entry_key = payload.get("entryKey")
        data = payload.get("data")

        if not entry_key or data is None:
            return jsonify({
                "success": False,
                "error": "entryKey and data are required"
            }), 400

        write_to_datastore(entry_key, data)

        return jsonify({
            "success": True,
            "writtenKey": entry_key
        }), 200

    except requests.HTTPError as e:
        return jsonify({
            "success": False,
            "error": "Roblox API error",
            "details": str(e)
        }), 502

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
