"""
Run this script ONCE locally to generate the ONEDRIVE_REFRESH_TOKEN secret.

    pip install requests
    python .github/scripts/get_token.py
"""

import time
import requests

CLIENT_ID = input("Paste your CLIENT_ID: ").strip()
TENANT = "consumers"
SCOPE = "Files.ReadWrite offline_access"

resp = requests.post(
    f"https://login.microsoftonline.com/{TENANT}/oauth2/v2.0/devicecode",
    data={"client_id": CLIENT_ID, "scope": SCOPE},
)
resp.raise_for_status()
device = resp.json()

print(f"\n{device['message']}\n")

interval = int(device.get("interval", 5))
while True:
    time.sleep(interval)
    token_resp = requests.post(
        f"https://login.microsoftonline.com/{TENANT}/oauth2/v2.0/token",
        data={
            "client_id": CLIENT_ID,
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "device_code": device["device_code"],
        },
    )
    data = token_resp.json()

    if "refresh_token" in data:
        print("\n=== Salve isso no GitHub Secrets como: ONEDRIVE_REFRESH_TOKEN ===")
        print(data["refresh_token"])
        print("=================================================================")
        break
    elif data.get("error") == "authorization_pending":
        print("Aguardando login...", end="\r")
    elif data.get("error") == "slow_down":
        interval += 5
    else:
        print(f"\nErro: {data.get('error')}: {data.get('error_description')}")
        break
