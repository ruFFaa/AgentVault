# submit_card.py
import httpx
import json

REGISTRY_URL = "http://localhost:8000" # Adjust if needed
API_KEY = "avreg_manualtestkey123" # <--- !!! REPLACE THIS with your key !!!
CARD_FILE = "initial-card.json" # <--- Make sure this matches the filename

try:
    with open(CARD_FILE, 'r') as f:
        card_data = json.load(f)

    headers = {"X-Api-Key": API_KEY, "Content-Type": "application/json"}
    payload = {"card_data": card_data}

    print(f"Submitting card from {CARD_FILE} using key starting with {API_KEY[:10]}...")
    response = httpx.post(f"{REGISTRY_URL}/api/v1/agent-cards/", json=payload, headers=headers)
    response.raise_for_status() # Raise error for non-2xx status

    print("\nCard Submitted Successfully!")
    print(json.dumps(response.json(), indent=2)) # Pretty print response

except FileNotFoundError:
    print(f"Error: {CARD_FILE} not found in current directory.")
except httpx.HTTPStatusError as e:
    print(f"\nError submitting card: {e.response.status_code}")
    print(f"Response: {e.response.text}")
except Exception as e:
    print(f"\nAn error occurred: {e}")