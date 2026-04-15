import os
import logging

import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

APP_ID = os.getenv("APP_ID")
APP_SECRET = os.getenv("APP_SECRET")

tokens = {
    "access_token": os.getenv("OA_ACCESS_TOKEN"),
    "refresh_token": os.getenv("OA_REFRESH_TOKEN"),
}

ZALO_MESSAGE_API = "https://openapi.zalo.me/v3.0/oa/message/cs"
ZALO_TOKEN_API = "https://oauth.zaloapp.com/v4/oa/access_token"


def refresh_access_token():
    """Exchange the current refresh token for a new access + refresh token pair."""
    resp = requests.post(
        ZALO_TOKEN_API,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "secret_key": APP_SECRET,
        },
        data={
            "app_id": APP_ID,
            "grant_type": "refresh_token",
            "refresh_token": tokens["refresh_token"],
        },
        timeout=10,
    )
    data = resp.json()

    if "access_token" in data:
        tokens["access_token"] = data["access_token"]
        tokens["refresh_token"] = data["refresh_token"]
        logger.info("Access token refreshed successfully")
    else:
        logger.error("Token refresh failed: %s", data)


def _is_token_invalid(resp: requests.Response, data: dict) -> bool:
    return resp.status_code == 401 or data.get("error") == -201


def _send_message(user_id: str, text: str) -> tuple[requests.Response, dict]:
    resp = requests.post(
        ZALO_MESSAGE_API,
        headers={
            "Content-Type": "application/json",
            "access_token": tokens["access_token"],
        },
        json={
            "recipient": {"user_id": user_id},
            "message": {"text": text},
        },
        timeout=10,
    )
    return resp, resp.json()


def send_reply(user_id: str, text: str):
    """Send a text message to a Zalo user, refreshing the token on auth errors."""
    resp, data = _send_message(user_id, text)

    if _is_token_invalid(resp, data):
        logger.warning("Access token invalid (HTTP %s, error %s), refreshing…",
                        resp.status_code, data.get("error"))
        try:
            refresh_access_token()
        except Exception:
            logger.exception("Token refresh failed")
            return data
        resp, data = _send_message(user_id, text)

    if data.get("error") != 0:
        logger.error("Failed to send message: %s", data)
    else:
        logger.info("Replied to user %s", user_id)
    return data


@app.route("/webhook", methods=["POST"])
def webhook():
    payload = request.get_json(silent=True) or {}
    event = payload.get("event_name")

    if event == "user_send_text":
        user_id = payload.get("sender", {}).get("id")
        message_text = payload.get("message", {}).get("text", "")
        logger.info("Received message from %s: %s", user_id, message_text)

        if user_id:
            send_reply(user_id, "Hello!")

    return jsonify({"status": "ok"}), 200


@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "running"}), 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", 3000))
    logger.info("Starting server on port %d", port)
    app.run(host="0.0.0.0", port=port)
