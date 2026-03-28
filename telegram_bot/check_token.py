"""
A diagnostic utility script designed to verify the validity of the Telegram Bot API token before deployment.
It performs a direct 'getMe' request to the Telegram API to confirm connectivity and retrieve the bot's identity metadata.
The script provides clear visual feedback, identifying whether a token is valid, revoked, or incorrectly formatted.
This serves as a critical pre-flight check to prevent 'Unauthorized' errors during the main application startup.
It includes basic network exception handling to distinguish between invalid credentials and local internet connectivity issues.
"""

import requests
import sys

TOKEN = "8379170828:AAF3PpY_TDosvr-gfBasP-0igTdJ4f3UnZ4"
print(f"Testing token: {TOKEN[:10]}...")

url = f"https://api.telegram.org/bot{TOKEN}/getMe"

try:
    response = requests.get(url, timeout=10)
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print("✅ Token is VALID!")
        print(f"Bot: @{data['result']['username']}")
        print(f"Name: {data['result']['first_name']}")
        print(f"ID: {data['result']['id']}")
    elif response.status_code == 401:
        print("❌ Token is INVALID or REVOKED")
        print("Error: Unauthorized - Token rejected by Telegram")
    elif response.status_code == 404:
        print("❌ Token NOT FOUND")
        print("Check if token format is correct")
    else:
        print(f"⚠️ Unexpected error: {response.status_code}")
        print(f"Response: {response.text[:200]}")
        
except requests.exceptions.RequestException as e:
    print(f"❌ Network error: {e}")
except Exception as e:
    print(f"❌ Unexpected error: {e}")