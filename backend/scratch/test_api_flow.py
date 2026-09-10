import requests

BASE_URL = "http://localhost:8000"


# 1. Login as employee
auth_res = requests.post(f"{BASE_URL}/auth/token", data={"username": "employee@example.com", "password": "password123"})
print("Auth Status:", auth_res.status_code)
token = auth_res.json().get("access_token")
headers = {"Authorization": f"Bearer {token}"}

# 2. Create conversation
conv_res = requests.post(f"{BASE_URL}/conversations", headers=headers)
print("Create Conv Status:", conv_res.status_code)
conv_id = conv_res.json().get("id")

# 3. Send message matching KB article
msg_payload = {"content": "I did update my windows a moment ago and it just doesn't allow my VPN to get connected"}
msg_res = requests.post(f"{BASE_URL}/conversations/{conv_id}/messages", json=msg_payload, headers=headers)
print("Send Message Status:", msg_res.status_code)
print("Response JSON:")
print(msg_res.json())
