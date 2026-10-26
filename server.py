import os
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Dial, Sip
from dotenv import load_dotenv
import urllib.parse

# Load environment variables
load_dotenv()

app = FastAPI(title="Telephony SIP Bridge")

# Initialize Twilio Client
twilio_client = Client(
    os.getenv("TWILIO_ACCOUNT_SID"), 
    os.getenv("TWILIO_AUTH_TOKEN")
)
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
LIVEKIT_SIP_DOMAIN = os.getenv("LIVEKIT_SIP_DOMAIN")
PUBLIC_SERVER_URL = os.getenv("PUBLIC_SERVER_URL")

class InterviewRequest(BaseModel):
    customer_phone_number: str
    interview_instance_id: str

@app.post("/start-interview")
async def start_interview(request: InterviewRequest):
    """
    Trigger API to dial the customer and link them to the Twilio Webhook.
    """
    try:
        # URL encode the interview ID just in case it contains special characters
        encoded_id = urllib.parse.quote(request.interview_instance_id)
        
        # The webhook Twilio will call when the customer answers
        webhook_url = f"{PUBLIC_SERVER_URL}/twilio-webhook?interview_instance_id={encoded_id}"

        # Initiate the outbound call
        call = twilio_client.calls.create(
            to=request.customer_phone_number,
            from_=TWILIO_PHONE_NUMBER,
            url=webhook_url
            # Removed method="POST" to satisfy trial account parameter limits
        )
        
        return {
            "status": "Call initiated",
            "call_sid": call.sid,
            "interview_instance_id": request.interview_instance_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/twilio-webhook")
async def twilio_webhook(
    request: Request,
    interview_instance_id: str = None
):
    """
    Webhook triggered by Twilio when the customer answers the phone.
    Returns TwiML to SIP-dial into the LiveKit room.
    """
    if not interview_instance_id:
        # Fallback if the query param was somehow lost
        interview_instance_id = "default_room"

    # Construct the LiveKit SIP URI
    # Format: sip:{room_name}@{livekit_sip_domain}
    sip_uri = f"sip:{interview_instance_id}@{LIVEKIT_SIP_DOMAIN}"

    # Build the TwiML response
    response = VoiceResponse()
    dial = Dial()
    dial.sip(sip_uri)
    response.append(dial)

    # Return valid XML for Twilio
    return Response(content=str(response), media_type="application/xml")