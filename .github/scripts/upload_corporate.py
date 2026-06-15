"""
Upload PBIP to OneDrive for Business using Client Credentials Flow.

Required GitHub Secrets:
  TENANT_ID            - Azure AD tenant ID
  CLIENT_ID            - App Registration client ID
  CLIENT_SECRET        - App Registration client secret
  ONEDRIVE_USER_ID     - Target user email (UPN), e.g. user@empresa.com

Optional GitHub Variable:
  ONEDRIVE_FOLDER_PATH - Destination folder in OneDrive (default: PBIP_Deploy)
"""

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
    resp = requests.post(
        f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token",
        data={
            "grant_type": "client_credentials",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "scope": "https://graph.microsoft.com/.default",
        },
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def check_drive(token: str) -> None:
    resp = requests.get(
        f"{GRAPH}/users/{USER_ID}/drive",
        headers={"Authorization": f"Bearer {token}"},
    )
    if resp.status_code == 404:
        print("\nERROR: OneDrive não encontrado (404). Verifique:", file=sys.stderr)
        print("  1. ONEDRIVE_USER_ID deve ser o email corporativo: user@empresa.com", file=sys.stderr)
        print("  2. O usuário precisa ter acessado o OneDrive ao menos uma vez", file=sys.stderr)
        print("  3. O App precisa de 'Files.ReadWrite.All' (Application) com admin consent", file=sys.stderr)
        sys.exit(1)
    if resp.status_code == 403:
        print("\nERROR: Acesso negado (403). Verifique:", file=sys.stderr)
        print("  1. Permissão 'Files.ReadWrite.All' (Application) adicionada", file=sys.stderr)
        print("  2. Admin consent concedido no Azure Portal", file=sys.stderr)
        sys.exit(1)
    resp.raise_for_status()
    drive = resp.json()
    print(f"Drive encontrado: {drive.get('name', 'OneDrive')} ({drive.get('driveType', '?')})")


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
    print("Autenticando com Microsoft Graph (conta corporativa)...")
    token = get_access_token()
    print("Token obtido.")

    print(f"\nVerificando OneDrive de '{USER_ID}'...")
    check_drive(token)

    pbip_dir = Path("PBIP")
    if not pbip_dir.exists():
        print("ERROR: Pasta PBIP não encontrada.", file=sys.stderr)
        sys.exit(1)

    files = [f for f in pbip_dir.rglob("*") if f.is_file() and f.name not in EXCLUDED_FILES]
    print(f"\nEnviando {len(files)} arquivo(s) para '{FOLDER_PATH}'...\n")

    errors = []
    for file_path in files:
        relative = file_path.relative_to(pbip_dir.parent)
        remote_path = f"{FOLDER_PATH}/{relative}"
        try:
            upload_file(token, file_path, remote_path)
        except requests.HTTPError as e:
            print(f"  FAIL {remote_path} — {e}", file=sys.stderr)
            errors.append(remote_path)

    print(f"\nConcluído. {len(files) - len(errors)}/{len(files)} arquivos enviados.")
    if errors:
        print(f"\nFalhas ({len(errors)}):", file=sys.stderr)
        for f in errors:
            print(f"  - {f}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
