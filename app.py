import os
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from twilio.twiml.messaging_response import MessagingResponse

# -----------------------------
# Load environment variables
# -----------------------------
load_dotenv()

app = Flask(__name__)

VOICEFLOW_API_KEY = os.getenv("VOICEFLOW_API_KEY")
VOICEFLOW_VERSION_ID = os.getenv("VOICEFLOW_VERSION_ID")
VF_BASE = os.getenv("VOICEFLOW_RUNTIME_URL", "https://general-runtime.voiceflow.com")
RESPONDIO_SECRET = os.getenv("RESPONDIO_SECRET")  # optional

# =========================================================
# ✅ Respond.io webhook
# =========================================================
@app.route("/respondio-webhook", methods=["POST"])
def respondio_webhook():
    # Check secret header
    secret = request.headers.get("X-Respondio-Secret")
    if RESPONDIO_SECRET and secret != RESPONDIO_SECRET:
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json(force=True)
    print("📩 Respond.io payload:", data)

    contact = data.get("contact", {})
    contact_id = contact.get("id") or contact.get("phone") or "unknown_user"

    # Extract message text
    text = None
    if data.get("data"):
        text = data["data"].get("text")
    if not text and data.get("message"):
        text = data["message"].get("text")
    if not text:
        text = ""

    replies = get_voiceflow_replies(contact_id, text)

    response_payload = {"messages": [{"text": r} for r in replies]}
    print("↩️ Respond.io response payload:", response_payload)

    return jsonify(response_payload), 200


# =========================================================
# ✅ Twilio WhatsApp webhook
# =========================================================
@app.route("/twilio-webhook", methods=["POST"])
def twilio_webhook():
    data = request.form.to_dict()
    print("📩 Incoming Twilio WhatsApp:", data)

    user_msg = data.get("Body", "")
    user_id = data.get("From", "unknown_user")

    replies = get_voiceflow_replies(user_id, user_msg)

    # Build TwiML response
    resp = MessagingResponse()
    for r in replies:
        resp.message(r)

    print("↩️ Twilio response payload:", replies)
    return str(resp)


# =========================================================
# 🔹 Shared helper to query Voiceflow
# =========================================================
def get_voiceflow_replies(user_id: str, text: str):
    try:
        if VOICEFLOW_VERSION_ID:
            url = f"{VF_BASE}/state/{VOICEFLOW_VERSION_ID}/user/{user_id}/interact"
        else:
            url = f"{VF_BASE}/state/user/{user_id}/interact"

        vf_resp = requests.post(
            url,
            headers={"Authorization": VOICEFLOW_API_KEY, "Content-Type": "application/json"},
            json={"request": {"type": "text", "payload": text}},
            timeout=15,
        )
        vf_resp.raise_for_status()
        vf_data = vf_resp.json()
        print("🔵 Voiceflow raw reply:", vf_data)
    except Exception as e:
        print("❌ Voiceflow error:", e)
        return ["Sorry, I'm having trouble right now."]

    replies = []
    if isinstance(vf_data, list):
        for item in vf_data:
            if item.get("type") == "text":
                msg = item.get("payload", {}).get("message") or item.get("message")
                if msg:
                    replies.append(msg)

    if not replies:
        replies = ["Sorry, I don’t have an answer for that right now."]

    return replies


# =========================================================
if __name__ == "__main__":
    app.run(port=5000, debug=True)
