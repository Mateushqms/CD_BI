import os
import sys
import requests
from pathlib import Path

TENANT_ID = os.environ["TENANT_ID"]
CLIENT_ID = os.environ["CLIENT_ID"]
CLIENT_SECRET = os.environ["CLIENT_SECRET"]
USER_ID = os.environ["ONEDRIVE_USER_ID"]
FOLDER_PATH = os.environ.get("ONEDRIVE_FOLDER_PATH", "PBIP_Deploy")

EXCLUDED_FILES = {"localSettings.json", "cache.abf", ".gitignore"}
GRAPH = "https://graph.microsoft.com/v1.0"


def get_access_token() -> str:
    url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    resp = requests.post(url, data={
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": "https://graph.microsoft.com/.default",
    })
    resp.raise_for_status()
    return resp.json()["access_token"]


def check_drive(token: str) -> dict:
    url = f"{GRAPH}/users/{USER_ID}/drive"
    resp = requests.get(url, headers={"Authorization": f"Bearer {token}"})

    if resp.status_code == 404:
        print("\nERROR: OneDrive not found (404). Possible causes:", file=sys.stderr)
        print("  1. ONEDRIVE_USER_ID is wrong — use the user's email (UPN) ex: user@empresa.com", file=sys.stderr)
        print("  2. OneDrive was never opened/provisioned for this user", file=sys.stderr)
        print("  3. The user does not have a OneDrive license", file=sys.stderr)
        sys.exit(1)

    if resp.status_code == 403:
        print("\nERROR: Access denied (403). Possible causes:", file=sys.stderr)
        print("  1. The App Registration is missing 'Files.ReadWrite.All' (Application permission)", file=sys.stderr)
        print("  2. Admin consent was NOT granted in Azure Portal", file=sys.stderr)
        print("     Go to: App Registration → API permissions → Grant admin consent", file=sys.stderr)
        sys.exit(1)

    resp.raise_for_status()
    drive = resp.json()
    print(f"Drive found: {drive.get('name', 'OneDrive')} ({drive.get('driveType', '?')})")
    return drive


def upload_file(token: str, local_path: Path, remote_path: str) -> None:
    url = f"{GRAPH}/users/{USER_ID}/drive/items/root:/{remote_path}:/content"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/octet-stream",
    }
    with open(local_path, "rb") as f:
        resp = requests.put(url, headers=headers, data=f)
    resp.raise_for_status()
    print(f"  OK  {remote_path}")


def main() -> None:
    print("Authenticating with Microsoft Graph...")
    token = get_access_token()
    print("Token obtained.")

    print(f"\nChecking OneDrive for user '{USER_ID}'...")
    check_drive(token)

    pbip_dir = Path("PBIP")
    if not pbip_dir.exists():
        print("ERROR: PBIP directory not found.", file=sys.stderr)
        sys.exit(1)

    files = [f for f in pbip_dir.rglob("*") if f.is_file() and f.name not in EXCLUDED_FILES]
    print(f"\nUploading {len(files)} file(s) to OneDrive folder '{FOLDER_PATH}'...\n")

    errors = []
    for file_path in files:
        relative = file_path.relative_to(pbip_dir.parent)
        remote_path = f"{FOLDER_PATH}/{relative}"
        try:
            upload_file(token, file_path, remote_path)
        except requests.HTTPError as e:
            print(f"  FAIL {remote_path} — {e}", file=sys.stderr)
            errors.append(remote_path)

    print(f"\nDone. {len(files) - len(errors)}/{len(files)} files uploaded successfully.")
    if errors:
        print(f"\nFailed files ({len(errors)}):", file=sys.stderr)
        for f in errors:
            print(f"  - {f}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
