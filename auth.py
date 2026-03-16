import os
from growwapi import GrowwAPI
from dotenv import load_dotenv
import pyotp

load_dotenv()

def generate_access_token():
    """Generates an access token using API keys and TOTP."""
    api_key = os.getenv("GROWW_API_KEY")
    secret = os.getenv("GROWW_SECRET_KEY")
    totp_secret = os.getenv("GROWW_TOTP_SECRET")

    if not api_key:
        print("Warning: GROWW_API_KEY not set in .env")
        return None

    totp_code = None
    if totp_secret:
        try:
            totp_code = pyotp.TOTP(totp_secret).now()
        except Exception as e:
            print(f"Error generating TOTP: {e}")

    try:
        if totp_code:
            access_token = GrowwAPI.get_access_token(
                api_key=api_key,
                totp=totp_code
            )
        else:
            access_token = GrowwAPI.get_access_token(
                api_key=api_key,
                secret=secret
            )
        return access_token
    except Exception as e:
        print(f"Error fetching access token: {e}")
        return None

def get_groww_client():
    """Initializes and returns the GrowwAPI client."""
    # The SDK GrowwAPI takes the access_token in its constructor
    access_token = generate_access_token()
    return GrowwAPI(access_token)
