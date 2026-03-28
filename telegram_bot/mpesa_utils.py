"""
A specialized utility module for handling Safaricom M-Pesa API integrations, including OAuth token generation and STK Push.
It supports both Sandbox and Production environments, dynamically switching URLs based on the project's environment variables.
The module generates the required security credentials, such as the Base64-encoded password and the timestamped M-Pesa password.
It includes functions for initiating push notifications to users' phones and querying the final status of a transaction.
A built-in test suite allows developers to simulate and debug connectivity without requiring a full purchase cycle in the main bot.
"""

import os
import requests
import json
import base64
import logging
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- CONFIGURATION ---
# Use environment variables for security, with fallback to sandbox for testing
MPESA_ENVIRONMENT = os.getenv('MPESA_ENVIRONMENT', 'sandbox').lower()  # 'sandbox' or 'production'
CONSUMER_KEY = os.getenv('MPESA_CONSUMER_KEY', 'YOUR_CONSUMER_KEY')
CONSUMER_SECRET = os.getenv('MPESA_CONSUMER_SECRET', 'YOUR_CONSUMER_SECRET')
PASSKEY = os.getenv('MPESA_PASSKEY', 'PASSKEY')
BUSINESS_SHORTCODE = os.getenv('MPESA_BUSINESS_SHORTCODE', '6789655')
CALLBACK_URL = os.getenv('MPESA_CALLBACK_URL', 'https://yourdomain.com/callback')

# Set URLs based on environment
if MPESA_ENVIRONMENT == 'production':
    TOKEN_URL = "https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    STK_PUSH_URL = "https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
else:
    TOKEN_URL = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    STK_PUSH_URL = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MpesaPaymentError(Exception):
    """Custom exception for M-Pesa payment errors"""
    pass

def get_access_token():
    """
    Get OAuth access token from Safaricom API
    """
    try:
        logger.info(f"Requesting M-Pesa access token from {MPESA_ENVIRONMENT}...")
        response = requests.get(
            TOKEN_URL, 
            auth=(CONSUMER_KEY, CONSUMER_SECRET),
            timeout=30
        )
        response.raise_for_status()
        
        token_data = response.json()
        access_token = token_data.get('access_token')
        
        if access_token:
            logger.info("✅ M-Pesa access token obtained successfully")
            return access_token
        else:
            error_msg = token_data.get('error_description', 'Unknown error')
            logger.error(f"❌ Failed to get access token: {error_msg}")
            return None
            
    except requests.exceptions.Timeout:
        logger.error("❌ Token request timed out")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Network error during token request: {e}")
        return None
    except json.JSONDecodeError:
        logger.error("❌ Invalid JSON response from token endpoint")
        return None

def format_phone_number(phone_number):
    """
    Format phone number to 254XXXXXXXXX format
    """
    if not phone_number:
        raise ValueError("Phone number cannot be empty")
    
    # Remove any spaces, dashes, or plus signs
    phone = phone_number.strip().replace(" ", "").replace("-", "").replace("+", "")
    
    # Format to 254XXXXXXXXX
    if phone.startswith("0") and len(phone) == 10:
        return "254" + phone[1:]
    elif phone.startswith("254") and len(phone) == 12:
        return phone
    elif phone.startswith("7") and len(phone) == 9:
        return "254" + phone
    else:
        raise ValueError(f"Invalid phone number format: {phone_number}")

def initiate_stk_push(phone_number, amount=50, description="Premium Predictions"):
    """
    Initiate M-Pesa STK Push payment request
    
    Args:
        phone_number: Customer phone number
        amount: Amount in KES
        description: Transaction description
    
    Returns:
        dict: Response from M-Pesa API
    """
    # Validate inputs
    if amount <= 0 or amount > 100000:  # M-Pesa limit
        return {
            "error": True,
            "message": f"Invalid amount: KES {amount}. Must be between 1 and 100,000"
        }
    
    try:
        # Format phone number
        formatted_phone = format_phone_number(phone_number)
        logger.info(f"Processing payment for {formatted_phone}, Amount: KES {amount}")
        
        # Get access token
        access_token = get_access_token()
        if not access_token:
            return {
                "error": True,
                "message": "Failed to authenticate with M-Pesa. Please try again later."
            }
        
        # Prepare STK Push request
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        password = base64.b64encode(
            (BUSINESS_SHORTCODE + PASSKEY + timestamp).encode('ascii')
        ).decode('utf-8')
        
        payload = {
            "BusinessShortCode": BUSINESS_SHORTCODE,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": int(amount),
            "PartyA": formatted_phone,
            "PartyB": BUSINESS_SHORTCODE,
            "PhoneNumber": formatted_phone,
            "CallBackURL": CALLBACK_URL,
            "AccountReference": "ScorePulse",
            "TransactionDesc": description[:20]  # Max 20 chars
        }
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        # Make STK Push request
        logger.info(f"Sending STK Push request for KES {amount} to {formatted_phone}")
        response = requests.post(
            STK_PUSH_URL,
            json=payload,
            headers=headers,
            timeout=30
        )
        
        response_data = response.json()
        
        # Log the response
        if response.status_code == 200:
            logger.info(f"✅ STK Push initiated successfully. Response: {response_data}")
            
            # Check if request was successful
            response_code = response_data.get('ResponseCode', '')
            if response_code == '0':
                return {
                    "error": False,
                    "success": True,
                    "message": "Payment request sent to your phone. Please check for an M-Pesa prompt.",
                    "response_code": response_code,
                    "customer_message": response_data.get('CustomerMessage', ''),
                    "checkout_request_id": response_data.get('CheckoutRequestID', ''),
                    "merchant_request_id": response_data.get('MerchantRequestID', '')
                }
            else:
                error_msg = response_data.get('errorMessage', response_data.get('CustomerMessage', 'Payment failed'))
                logger.error(f"❌ STK Push failed: {error_msg}")
                return {
                    "error": True,
                    "message": f"Payment failed: {error_msg}",
                    "response_code": response_code
                }
        else:
            logger.error(f"❌ HTTP Error {response.status_code}: {response_data}")
            return {
                "error": True,
                "message": f"Payment service error (HTTP {response.status_code}). Please try again.",
                "details": response_data
            }
            
    except ValueError as e:
        logger.error(f"❌ Invalid input: {e}")
        return {
            "error": True,
            "message": f"Invalid phone number: {str(e)}"
        }
    except requests.exceptions.Timeout:
        logger.error("❌ Payment request timed out")
        return {
            "error": True,
            "message": "Payment request timed out. Please try again."
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Network error: {e}")
        return {
            "error": True,
            "message": "Network error. Please check your internet connection and try again."
        }
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        return {
            "error": True,
            "message": f"An unexpected error occurred: {str(e)}"
        }

def check_payment_status(checkout_request_id):
    """
    Check status of an STK Push transaction
    Note: This requires a valid callback URL setup
    """
    try:
        access_token = get_access_token()
        if not access_token:
            return {"error": "Failed to authenticate"}
        
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        password = base64.b64encode(
            (BUSINESS_SHORTCODE + PASSKEY + timestamp).encode('ascii')
        ).decode('utf-8')
        
        payload = {
            "BusinessShortCode": BUSINESS_SHORTCODE,
            "Password": password,
            "Timestamp": timestamp,
            "CheckoutRequestID": checkout_request_id
        }
        
        headers = {"Authorization": f"Bearer {access_token}"}
        
        # Note: This endpoint is different for sandbox vs production
        query_url = "https://sandbox.safaricom.co.ke/mpesa/stkpushquery/v1/query"
        if MPESA_ENVIRONMENT == 'production':
            query_url = "https://api.safaricom.co.ke/mpesa/stkpushquery/v1/query"
        
        response = requests.post(query_url, json=payload, headers=headers)
        return response.json()
        
    except Exception as e:
        logger.error(f"Error checking payment status: {e}")
        return {"error": str(e)}

# Test function (for debugging)
def test_mpesa_connection():
    """Test M-Pesa API connectivity"""
    print("🧪 Testing M-Pesa Connection...")
    print(f"Environment: {MPESA_ENVIRONMENT}")
    print(f"Business Shortcode: {BUSINESS_SHORTCODE}")
    
    # Test token retrieval
    token = get_access_token()
    if token:
        print("✅ Token retrieval: SUCCESS")
        
        # Test STK Push with dummy number
        test_phone = "254708374149"  # Safaricom test number
        test_amount = 1  # 1 KES for testing
        
        print(f"\nTesting STK Push to {test_phone}...")
        result = initiate_stk_push(test_phone, test_amount, "Test Payment")
        
        if result.get('success'):
            print("✅ STK Push: SUCCESS")
            print(f"Message: {result.get('message')}")
        else:
            print("❌ STK Push: FAILED")
            print(f"Error: {result.get('message')}")
    else:
        print("❌ Token retrieval: FAILED")
        print("Please check your CONSUMER_KEY and CONSUMER_SECRET")
    
    return token is not None

if __name__ == "__main__":
    # Run tests if script is executed directly
    test_mpesa_connection()