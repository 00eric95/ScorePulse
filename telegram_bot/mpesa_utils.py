import requests
import json
import base64
from datetime import datetime

# --- CONFIGURATION (USE SANDBOX CREDENTIALS FOR NOW) ---
# Go to https://developer.safaricom.co.ke/ to get these
CONSUMER_KEY = "YOUR_CONSUMER_KEY"
CONSUMER_SECRET = "YOUR_CONSUMER_SECRET"
PASSKEY = "bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919" # Sandbox Passkey
BUSINESS_SHORTCODE = "174379" # Sandbox Paybill

def get_access_token():
    api_url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    r = requests.get(api_url, auth=(CONSUMER_KEY, CONSUMER_SECRET))
    try:
        return r.json()['access_token']
    except:
        return None

def initiate_stk_push(phone_number, amount=50):
    access_token = get_access_token()
    if not access_token:
        return {"error": "Failed to authenticate with M-Pesa"}

    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    password = base64.b64encode((BUSINESS_SHORTCODE + PASSKEY + timestamp).encode('ascii')).decode('utf-8')
    
    # Sanitize phone number (Must be 2547...)
    if phone_number.startswith('0'):
        phone_number = '254' + phone_number[1:]
    elif phone_number.startswith('+'):
        phone_number = phone_number[1:]

    payload = {
        "BusinessShortCode": BUSINESS_SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": amount,
        "PartyA": phone_number, # Customer Phone
        "PartyB": BUSINESS_SHORTCODE, # Your Paybill
        "PhoneNumber": phone_number,
        "CallBackURL": "https://mydomain.com/path", # Need a live server for this
        "AccountReference": "ScorePulse",
        "TransactionDesc": "Premium Predictions"
    }

    api_url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
    headers = { "Authorization": f"Bearer {access_token}" }
    
    try:
        r = requests.post(api_url, json=payload, headers=headers)
        return r.json()
    except Exception as e:
        return {"error": str(e)}