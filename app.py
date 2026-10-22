import os
import re
import hmac
import json
import time
import logging
import requests
from flask import Flask, request, jsonify
from werkzeug.exceptions import RequestEntityTooLarge

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("transfer")

app = Flask(__name__)

# ===============================
# CONFIG
# ===============================

API_KEY = os.getenv("ROBLOX_API_KEY")  # REQUIRED
UPLOAD_SECRET = os.getenv("TRANSFER_UPLOAD_SECRET")
PREVIOUS_UPLOAD_SECRET = os.getenv("TRANSFER_UPLOAD_SECRET_PREVIOUS")
NEW_UNIVERSE = 3064619271
NEW_DATASTORE = "TransferStore"
ENTRY_KEY_PATTERN = re.compile(r"^Player_[1-9][0-9]{0,19}$")
MAX_ENTRY_BYTES = 3_500_000  # datastore entries are capped at 4MB
app.config["MAX_CONTENT_LENGTH"] = 4_194_304

if not API_KEY:
    raise RuntimeError("ROBLOX_API_KEY not set")

if not UPLOAD_SECRET:
    raise RuntimeError("TRANSFER_UPLOAD_SECRET not set")

UPLOAD_SECRETS = [UPLOAD_SECRET.encode()]
if PREVIOUS_UPLOAD_SECRET:
    UPLOAD_SECRETS.append(PREVIOUS_UPLOAD_SECRET.encode())

# ===============================
# Roblox Datastore Write
# ===============================

def write_to_datastore(entry_key, body):
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

    # retry rate limits / Roblox outages a couple times before failing the upload
    for attempt in range(3):
        response = requests.post(
            url,
            headers=headers,
            params=params,
            data=body,
            timeout=10,
        )
        if (response.status_code == 429 or response.status_code >= 500) and attempt < 2:
            time.sleep(2 ** attempt)
            continue
        response.raise_for_status()
        return

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
        provided = request.headers.get("X-Transfer-Secret", "").encode()
        if not any(hmac.compare_digest(provided, secret) for secret in UPLOAD_SECRETS):
            log.warning("rejected upload with a bad secret from %s", request.remote_addr)
            return jsonify({
                "success": False,
                "error": "unauthorized"
            }), 401

        payload = request.get_json(force=True, silent=True)
        if not isinstance(payload, dict):
            return jsonify({
                "success": False,
                "error": "body must be a JSON object"
            }), 400

        entry_key = payload.get("entryKey")
        data = payload.get("data")

        if not isinstance(entry_key, str) or not ENTRY_KEY_PATTERN.fullmatch(entry_key):
            return jsonify({
                "success": False,
                "error": "entryKey must look like Player_<UserId>"
            }), 400

        if not isinstance(data, (dict, list)):
            return jsonify({
                "success": False,
                "error": "data must be a table of slots"
            }), 400

        body = json.dumps(data)
        if len(body) > MAX_ENTRY_BYTES:
            return jsonify({
                "success": False,
                "error": "data too large"
            }), 413

        write_to_datastore(entry_key, body)
        log.info("wrote %s (%d bytes, %d slots)", entry_key, len(body), len(data))

        return jsonify({
            "success": True,
            "writtenKey": entry_key
        }), 200

    except RequestEntityTooLarge:
        return jsonify({
            "success": False,
            "error": "request body too large"
        }), 413

    except requests.RequestException as e:
        log.error("roblox api error for upload: %s", e)
        return jsonify({
            "success": False,
            "error": "Roblox API error"
        }), 502

    except Exception:
        log.exception("upload failed")
        return jsonify({
            "success": False,
            "error": "upload failed"
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
