import os
import sys
import requests
from pathlib import Path

CLIENT_ID = os.environ["CLIENT_ID"]
REFRESH_TOKEN = os.environ["ONEDRIVE_REFRESH_TOKEN"]
FOLDER_PATH = os.environ.get("ONEDRIVE_FOLDER_PATH", "PBIP_Deploy")

EXCLUDED_FILES = {"localSettings.json", "cache.abf", ".gitignore"}
GRAPH = "https://graph.microsoft.com/v1.0"
TENANT = "consumers"


def get_access_token() -> str:
    resp = requests.post(
        f"https://login.microsoftonline.com/{TENANT}/oauth2/v2.0/token",
        data={
            "grant_type": "refresh_token",
            "client_id": CLIENT_ID,
            "refresh_token": REFRESH_TOKEN,
            "scope": "Files.ReadWrite offline_access",
        },
    )
    if resp.status_code == 400:
        print("\nERROR: Refresh token inválido ou expirado (400).", file=sys.stderr)
        print("  Rode novamente: python .github/scripts/get_token.py", file=sys.stderr)
        print("  E atualize o secret ONEDRIVE_REFRESH_TOKEN no GitHub.", file=sys.stderr)
        sys.exit(1)
    resp.raise_for_status()
    return resp.json()["access_token"]


def check_drive(token: str) -> None:
    resp = requests.get(
        f"{GRAPH}/me/drive",
        headers={"Authorization": f"Bearer {token}"},
    )
    if resp.status_code != 200:
        print(f"\nERROR: Não foi possível acessar o OneDrive ({resp.status_code}).", file=sys.stderr)
        sys.exit(1)
    drive = resp.json()
    print(f"Drive encontrado: {drive.get('name', 'OneDrive')} ({drive.get('driveType', '?')})")


def upload_file(token: str, local_path: Path, remote_path: str) -> None:
    url = f"{GRAPH}/me/drive/items/root:/{remote_path}:/content"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/octet-stream",
    }
    with open(local_path, "rb") as f:
        resp = requests.put(url, headers=headers, data=f)
    resp.raise_for_status()
    print(f"  OK  {remote_path}")


def main() -> None:
    print("Autenticando com Microsoft Graph...")
    token = get_access_token()
    print("Token obtido.")

    print("\nVerificando OneDrive pessoal...")
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
