import os
from dotenv import load_dotenv
from growwapi import GrowwAPI

load_dotenv()

def get_groww_client():
    api_token = os.getenv("GROWW_API_TOKEN")
    if not api_token or api_token == "your_api_token_here":
        print("Warning: GROWW_API_TOKEN not set in .env")
    return GrowwAPI(api_token)
